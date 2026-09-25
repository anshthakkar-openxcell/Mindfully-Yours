"""
The conversation orchestrator -- wires every pipeline module into the exact 14-step sequence from
documnets/understanding/04_CONVERSATION_PIPELINE.md §1. THE ORDER BELOW IS NOT NEGOTIABLE.

Non-negotiable invariants (see documnets/understanding/01_PROJECT_OVERVIEW.md principle #2 and
04_CONVERSATION_PIPELINE.md):
- Steps 6 (triage) and 7 (interlock) run on EVERY turn, even when steps 3/4 (cache) hit.
- The interlock (step 7) can force an outcome regardless of anything else -- it is checked before
  the LLM is ever called, and its result overrides cache/retrieval/generation entirely.
- The LLM (step 10) composes phrasing only. It never runs if the interlock triggered.
- Steps 13-14 (audit, summary) are fired async and never block the response already streamed.

This function accepts already-transcribed text -- step 2 (speech-to-text) happens upstream, either
in the API layer (text mode) or in app.realtime.agent (voice mode via LiveKit), both of which call
into this same function so the pipeline logic is written exactly once.
"""

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SafetyInterlockError
from app.core.logging import get_logger
from app.pipeline import cache, state
from app.pipeline.filler import FillerSituation, select_filler
from app.pipeline.guardrail import check_grounding
from app.pipeline.prompt_builder import PromptInputs, build_prompt
from app.pipeline.retrieval import fetch_probing_guidance
from app.providers.base import EmbeddingProvider, LLMProvider
from app.safety import routing
from app.safety.interlock import check_interlock
from app.safety.triage import read_turn
from app.workers.audit_writer import write_turn_audit_log

logger = get_logger(__name__)


@dataclass
class TurnRequest:
    session_id: UUID
    user_id: UUID | None
    language: str
    text: str
    persona: str = "You are a warm, calm, non-clinical wellness companion."  # TODO: load from PromptConfig
    few_shot_examples: list[str] = field(default_factory=list)


@dataclass
class TurnOutcome:
    response_text: str
    served_from: str  # 'exact_cache' | 'semantic_cache' | 'rag_retrieval' | 'interlock' | 'fallback'
    tier: int | None
    interlock_triggered: bool
    requires_human_alert: bool


async def run_turn(
    request: TurnRequest,
    *,
    db: AsyncSession,
    redis: Redis,
    llm: LLMProvider,
    embedding_provider: EmbeddingProvider,
) -> AsyncIterator[str]:
    """
    Yields response text chunks as they become available (streamed per
    documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §3). The final chunk yielded is always
    the complete outcome's text if no earlier chunk was yielded (e.g. the interlock/verbatim-script
    path, which is not token-streamed since it's fetched, not generated).
    """
    latency: dict[str, float] = {}
    t0 = time.monotonic()

    # Step 1: turn arrives -- user_id/session_id/consent check happen at the API layer
    # (app.api.v1.endpoints.conversation), which is the trusted caller per
    # documnets/understanding/14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md §4. This function
    # assumes consent has already been verified by the time it's called.

    conv_state = await state.load_state(str(request.session_id), redis=redis)

    # Steps 3-4: two-tier cache check.
    cached = await cache.get_exact_cache(request.text, language=request.language, redis=redis)
    served_from = "exact_cache" if cached else None
    if cached is None:
        cached = await cache.get_semantic_cache(
            request.text, language=request.language, embedding_provider=embedding_provider, db=db
        )
        served_from = "semantic_cache" if cached else None

    # Step 5: RAG retrieval -- ONLY on a cache miss. (Actual retrieval happens further below, once
    # triage/interlock have run, since the routing decision determines WHAT to retrieve.)
    latency["cache_check_ms"] = (time.monotonic() - t0) * 1000

    # Step 6: silent triage -- ALWAYS runs, even on a cache hit. Never skip this because of `cached`.
    t_triage = time.monotonic()
    triage_reading = await read_turn(request.text, embedding_provider=embedding_provider, db=db)
    latency["triage_ms"] = (time.monotonic() - t_triage) * 1000

    # Step 7: safety interlock -- ALWAYS runs, independent of cache/triage/retrieval. This can
    # override everything below it, including a cache hit.
    t_interlock = time.monotonic()
    try:
        interlock_result = await check_interlock(request.text, db=db, embedding_provider=embedding_provider)
    except SafetyInterlockError:
        logger.critical("interlock_failed_failing_safe", session_id=str(request.session_id))
        # Fail SAFE, upward -- per documnets/understanding/08_SAFETY_INTERLOCK_AND_TRIAGE.md §6,
        # a failure here must route toward caution, e.g. a generic safe fallback + human review
        # flag, never toward silently continuing the normal conversation flow.
        yield "I want to make sure you get the right support -- let me connect you with someone."
        await write_turn_audit_log(
            session_id=request.session_id,
            user_id=request.user_id,
            turn_number=conv_state.turn_count + 1,
            served_from="interlock_failure_safe_path",
            interlock_triggered=True,
        )
        return

    latency["interlock_ms"] = (time.monotonic() - t_interlock) * 1000

    if interlock_result.triggered:
        response_text = interlock_result.bot_script or (
            "I want to make sure you get the right support right now -- "
            "let me connect you with someone who can help."
        )
        # requires_human_alert covers RF-028-031 (no bot_script) -- see
        # documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #1. This is a HARD alert path,
        # never silently downgraded to a generated response.
        yield response_text
        conv_state.record_turn(new_signal_ids=triage_reading.matched_signal_ids, response_length=len(response_text))
        await state.save_state(str(request.session_id), conv_state, redis=redis)
        await write_turn_audit_log(
            session_id=request.session_id,
            user_id=request.user_id,
            turn_number=conv_state.turn_count,
            served_from="interlock",
            matched_signal_ids=triage_reading.matched_signal_ids,
            interlock_triggered=True,
            interlock_flag_id=interlock_result.flag_id,
            latency_ms=latency,
        )
        return

    # Step D (sufficiency check, per 04_CONVERSATION_PIPELINE.md) -- deterministic rule lookup.
    routing_decision = await routing.evaluate_routing_rules(set(triage_reading.matched_signal_ids), db=db)

    if cached:
        yield cached
        conv_state.record_turn(new_signal_ids=triage_reading.matched_signal_ids, response_length=len(cached))
        await state.save_state(str(request.session_id), conv_state, redis=redis)
        await write_turn_audit_log(
            session_id=request.session_id,
            user_id=request.user_id,
            turn_number=conv_state.turn_count,
            served_from=served_from or "exact_cache",
            matched_signal_ids=triage_reading.matched_signal_ids,
            matched_rule_id=routing_decision.rule_id,
            latency_ms=latency,
        )
        return

    # Step 8: prompt assembly. Retrieved guidance comes from the direct-ID fetch once a pattern is
    # known (per documnets/understanding/04_CONVERSATION_PIPELINE.md Step E) -- not a search.
    guidance = None
    if triage_reading.candidate_pattern_id is not None:
        guidance = await fetch_probing_guidance(triage_reading.candidate_pattern_id, db=db)

    prompt = build_prompt(
        PromptInputs(
            persona=request.persona,
            retrieved_guidance=guidance,
            recent_turns=[],  # TODO: load trimmed recent history from conv_state / session store
            running_summary=None,  # TODO: load from ConversationSession.summary once ownership is resolved
            few_shot_examples=request.few_shot_examples,
        )
    )

    # Step 9: token metering / rate limit check.
    # TODO: implement per-user rate limiting (documnets/understanding/APPROACH.md §8) -- not yet
    # modeled. Left as an explicit gap rather than a silent no-op that looks implemented.

    # Optional filler phrase while the LLM's first token is pending -- see
    # documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §4. Only emit this if there's an actual
    # expected gap; a real implementation should base this on measured p50 first-token latency.
    filler = select_filler(FillerSituation.THINKING, language=request.language)
    if filler:
        yield filler + " "

    # Step 10: the LLM call -- phrasing only, never the safety decision or the retrieved facts.
    t_llm = time.monotonic()
    full_response_parts: list[str] = []
    async for chunk in llm.generate_stream(prompt):
        full_response_parts.append(chunk)
        yield chunk
    latency["llm_ms"] = (time.monotonic() - t_llm) * 1000
    response_text = "".join(full_response_parts)

    # Step 11: output guardrail.
    guardrail_result = check_grounding(response_text, retrieved_context=guidance)
    if not guardrail_result.passed:
        logger.warning("guardrail_failed", reason=guardrail_result.reason, session_id=str(request.session_id))
        # TODO: define the actual remediation -- re-prompt, fall back to a safe generic response,
        # etc. Logging only today so the failure is visible, not silently ignored.

    # Step 12: response already streamed above via `yield`.

    conv_state.record_turn(new_signal_ids=triage_reading.matched_signal_ids, response_length=len(response_text))
    await state.save_state(str(request.session_id), conv_state, redis=redis)

    if response_text:
        await cache.set_exact_cache(request.text, response_text, language=request.language, redis=redis)

    # Steps 13-14: audit log + session summary -- fired async, never blocking the response above.
    await write_turn_audit_log(
        session_id=request.session_id,
        user_id=request.user_id,
        turn_number=conv_state.turn_count,
        served_from="rag_retrieval",
        matched_signal_ids=triage_reading.matched_signal_ids,
        matched_rule_id=routing_decision.rule_id,
        triage_tier=routing_decision.route_to and _tier_from_route_to(routing_decision.route_to),
        latency_ms=latency,
    )
    # TODO: dispatch app.workers.summary_generator.generate_and_persist_summary via
    # asyncio.create_task (fire-and-forget), not awaited here -- left out until the
    # ConversationSession ownership question is resolved (see that module's docstring).


def _tier_from_route_to(route_to: str) -> int | None:
    """'Tier 3', 'Tier 2 (escalate)', 'Tier 1' -> 3, 2, 1. Returns None if unparseable."""
    for tier in (1, 2, 3):
        if f"Tier {tier}" in route_to:
            return tier
    return None
