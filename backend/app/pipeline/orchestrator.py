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
- If this generator is cancelled mid-stream (voice barge-in: the LiveKit Agent cancels the task
  backing this call when the user interrupts, per documnets/understanding/
  31_CONVERSATION_LAYER_IMPLEMENTATION_PLAN.md Phase 5), steps 12-14 (state save, cache, audit log)
  still run on whatever partial response was generated before the cut-off -- see the `finally`
  block around step 10 below. An interrupted turn losing its audit trail entirely would be a real
  gap in the record this design otherwise guarantees on every turn, cache hit or not.

This function accepts already-transcribed text -- step 2 (speech-to-text) happens upstream, either
in the API layer (text mode) or in app.realtime.agent (voice mode via LiveKit), both of which call
into this same function so the pipeline logic is written exactly once.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import SafetyInterlockError
from app.core.logging import get_logger
from app.pipeline import cache, state, tier_scoring
from app.pipeline.curated_match import (
    MIN_CLARIFY_WORDS,
    CuratedMatch,
    find_clarifying_question,
    find_curated_match,
)
from app.pipeline.guardrail import check_grounding, check_rephrase_faithful
from app.pipeline.language_hint import detect_language_style, language_instruction
from app.pipeline.localize import localize_reply

# from app.pipeline.filler import FillerSituation, select_filler  -- see the disabled call site below
from app.pipeline.prompt_builder import PromptInputs, build_prompt, build_rephrase_prompt
from app.pipeline.retrieval import fetch_probing_guidance, search_self_care_content
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.factory import get_translator
from app.safety import routing
from app.safety.interlock import NON_DANGER_SOFT_ZONE_FLAGS, check_interlock
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
    served_from: str  # 'exact_cache' | 'semantic_cache' | 'rag_retrieval' | 'interlock' | 'interlock_possible_concern' | 'fallback'
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

    # ONE embedding call for the whole turn, reused across interlock + triage + retrieval below --
    # NOT a stylistic choice, a latency-critical one. Measured live: a single embedding call costs
    # ~300-400ms (network round-trip to OpenAI, not model compute). Before this fix, interlock and
    # any future triage/retrieval implementation would each independently re-embed the identical
    # text, stacking 2-4 sequential ~300-400ms calls onto one turn -- easily 1-1.5s just in
    # redundant embeddings, before the LLM even starts, against a 1.5-2.5s TOTAL turn budget. See
    # app.providers.embeddings.openai_embeddings's "FUTURE RISK" docstring note -- this is that risk,
    # resolved by computing the vector once here and passing it to every check that needs it.
    settings = get_settings()

    # Hindi / Hinglish / mixed users (doc 34): translate their message to English ONCE, up front, and run the
    # whole pipeline on the English text -- the safety interlock, triage, therapist match and self-care search
    # are all English-only, and a Hindi crisis message scored ~0.2 against the English red flags (missed)
    # until this existed. The original text is kept for the LLM prompt and the conversation record. ~0.7 s,
    # paid only by non-English turns; English turns skip it entirely. If translation fails the original text
    # is used (as before) and the English-only therapist steps are skipped for that turn.
    language_style = detect_language_style(request.text)
    text_en = request.text
    translated_ok = language_style == "en"
    if language_style != "en" and settings.translation_enabled:
        t_translate = time.monotonic()
        try:
            text_en = await get_translator().to_english(request.text)
            translated_ok = True
        except Exception as exc:  # noqa: BLE001 -- never lose the turn over a translation failure
            logger.error("input_translation_failed", error=str(exc), session_id=str(request.session_id))
        latency["translate_in_ms"] = (time.monotonic() - t_translate) * 1000

    async def _out(text_in_english: str, kind: str) -> str:
        """A fixed English reply, in the user's own language (instant lookup of a pre-translated copy)."""
        return await localize_reply(text_in_english, language_style, kind=kind)

    t_embed = time.monotonic()
    try:
        [query_embedding] = await embedding_provider.embed([text_en])
    except Exception as exc:  # noqa: BLE001 -- fail SAFE, same as interlock's own embedding-failure
        # handling used to do before this call moved up here -- a failed embedding must route
        # toward caution, never crash past this boundary or silently skip the safety interlock.
        logger.critical("turn_embedding_failed_failing_safe", session_id=str(request.session_id), error=str(exc))
        yield await _out("I want to make sure you get the right support -- let me connect you with someone.", "fixed_message")
        await write_turn_audit_log(
            session_id=request.session_id,
            user_id=request.user_id,
            turn_number=conv_state.turn_count + 1,
            served_from="interlock_failure_safe_path",
            interlock_triggered=True,
        )
        return
    latency["embed_ms"] = (time.monotonic() - t_embed) * 1000

    # Therapist-first lookup (doc 32): started NOW as a background task so it overlaps with triage,
    # tier scoring and the interlock below instead of adding to them -- it reuses the embedding above
    # (no extra embedding call) and uses its own DB session (see app.pipeline.curated_match). It is
    # only AWAITED once the interlock has had its say; the interlock can still override it entirely.
    # The therapist library is English-only (doc 13). English text (typed in English, or a Hindi/Hinglish
    # message successfully translated above) can use it; its replies are then localised on the way out. If a
    # non-English message could NOT be translated, skip it and let the LLM answer in the user's language.
    use_therapist_library = settings.curated_match_enabled and translated_ok
    curated_task: asyncio.Task[CuratedMatch | None] | None = None
    if use_therapist_library:
        curated_task = asyncio.create_task(find_curated_match(query_embedding, language=request.language))

    # Steps 3-4: two-tier cache check.
    t_cache = time.monotonic()
    cached = await cache.get_exact_cache(request.text, language=request.language, redis=redis)
    served_from = "exact_cache" if cached else None
    if cached is None:
        cached = await cache.get_semantic_cache(
            request.text, language=request.language, embedding_provider=embedding_provider, db=db
        )
        served_from = "semantic_cache" if cached else None

    # Step 5: RAG retrieval -- ONLY on a cache miss. (Actual retrieval happens further below, once
    # triage/interlock have run, since the routing decision determines WHAT to retrieve.)
    # FIXED: this used to measure from t0 (function entry), which by this point in the code also
    # silently included embed_ms -- double-counting that time under two different labels. Now
    # measures only the cache step itself, from its own start point.
    latency["cache_check_ms"] = (time.monotonic() - t_cache) * 1000

    # Step 6: silent triage -- ALWAYS runs, even on a cache hit. Never skip this because of `cached`.
    t_triage = time.monotonic()
    triage_reading = await read_turn(
        text_en, embedding_provider=embedding_provider, db=db, query_embedding=query_embedding
    )
    latency["triage_ms"] = (time.monotonic() - t_triage) * 1000
    if triage_reading.candidate_pattern_id is not None:
        # Persisted across turns, not just this one -- once a candidate pattern is recognized, it
        # should stick for follow-up probing even if a later turn's own match is weaker or absent.
        conv_state.candidate_pattern_id = triage_reading.candidate_pattern_id

    # Running tier score -- ALWAYS updates, same "every turn, no exceptions" posture as triage
    # above, so it reflects the whole conversation rather than only the turns that reach the LLM.
    # See app.pipeline.tier_scoring's module docstring and
    # documnets/understanding/28_TIER_SCORING_APPROACH.md for the design. Computed against only the
    # NEW signals this turn contributed (not already observed) -- record_turn() below is what
    # actually adds them to conv_state.observed_signal_ids, so this must run before that.
    new_signal_ids = [sid for sid in triage_reading.matched_signal_ids if sid not in conv_state.observed_signal_ids]
    t_tier_score = time.monotonic()
    await tier_scoring.update_score(text_en, new_signal_ids, conv_state, db=db, llm=llm)
    # Only non-trivial on turns that still need the duration/impact LLM check -- it's skipped
    # entirely once both are already established, so this cost naturally drops to ~0 later in a
    # conversation. See app.pipeline.tier_scoring._detect_duration_and_impact_llm.
    latency["tier_score_ms"] = (time.monotonic() - t_tier_score) * 1000
    score_tier = tier_scoring.tier_from_score(conv_state.confidence_score)
    redirect_ready = tier_scoring.should_redirect_to_booking(conv_state)

    # Step 7: safety interlock -- ALWAYS runs, independent of cache/triage/retrieval. This can
    # override everything below it, including a cache hit.
    t_interlock = time.monotonic()
    try:
        interlock_result = await check_interlock(
            text_en, db=db, embedding_provider=embedding_provider, query_embedding=query_embedding
        )
    except SafetyInterlockError:
        if curated_task is not None:
            curated_task.cancel()
        logger.critical("interlock_failed_failing_safe", session_id=str(request.session_id))
        # Fail SAFE, upward -- per documnets/understanding/08_SAFETY_INTERLOCK_AND_TRIAGE.md §6,
        # a failure here must route toward caution, e.g. a generic safe fallback + human review
        # flag, never toward silently continuing the normal conversation flow.
        yield await _out("I want to make sure you get the right support -- let me connect you with someone.", "fixed_message")
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
        if curated_task is not None:
            curated_task.cancel()  # the red-flag script is served instead; a therapist match is moot
        response_text = interlock_result.bot_script or (
            "I want to make sure you get the right support right now -- "
            "let me connect you with someone who can help."
        )
        # requires_human_alert covers RF-028-031 (no bot_script) -- see
        # documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #1. This is a HARD alert path,
        # never silently downgraded to a generated response.
        # The verbatim script, in the user's own language (a pre-translated copy -- instant). A Hindi speaker
        # in crisis is better served by a translated script than an English one; machine translations are
        # marked reviewed=False in kb_translations until a clinician signs them off.
        response_text = await _out(response_text, "red_flag_script")
        yield response_text
        conv_state.record_turn(
            new_signal_ids=triage_reading.matched_signal_ids,
            user_text=request.text,
            response_text=response_text,
        )
        await state.save_state(str(request.session_id), conv_state, redis=redis)
        await write_turn_audit_log(
            session_id=request.session_id,
            user_id=request.user_id,
            turn_number=conv_state.turn_count,
            served_from="interlock",
            matched_signal_ids=triage_reading.matched_signal_ids,
            confidence_score=conv_state.confidence_score,
            score_tier=score_tier,
            redirect_ready=redirect_ready,
            interlock_triggered=True,
            interlock_flag_id=interlock_result.flag_id,
            latency_ms=latency,
        )
        return

    # Step D (sufficiency check, per 04_CONVERSATION_PIPELINE.md) -- deterministic rule lookup.
    # Evaluated against the ACCUMULATED signal set (this conversation's history + this turn's new
    # matches), not just this turn's alone -- a rule needing evidence from 2 separate turns must
    # still be able to fire once both have been seen.
    all_signal_ids = set(conv_state.observed_signal_ids) | set(triage_reading.matched_signal_ids)
    routing_decision = await routing.evaluate_routing_rules(all_signal_ids, db=db)
    tier = routing_decision.route_to and _tier_from_route_to(routing_decision.route_to)

    # Therapist-first (doc 32): the interlock above has already run and did not trigger. A soft-zone
    # "possible concern" turn keeps its doctor-written follow-up question, so no curated match then.
    curated: CuratedMatch | None = None
    if curated_task is not None:
        # Non-danger soft-zone flags (RF-007) keep the therapist match -- the therapists' own reply is
        # the better answer there. Every other possible-concern flag (RF-028) skips it and keeps its
        # doctor-written follow-up question.
        if interlock_result.possible_concern and interlock_result.flag_id not in NON_DANGER_SOFT_ZONE_FLAGS:
            curated_task.cancel()
        else:
            t_curated = time.monotonic()
            curated = await curated_task
            latency["curated_wait_ms"] = (time.monotonic() - t_curated) * 1000

    if curated is not None and (
        curated.band == "strong" or (curated.band == "partial" and settings.curated_partial_mode == "verbatim")
    ):
        # The therapist's own reply, exactly as written -- no LLM call at all.
        served = "therapist_verbatim" if curated.band == "strong" else "therapist_partial_verbatim"
        reply_out = await _out(curated.reply_text, "therapist_reply")
        yield reply_out
        conv_state.clarifications_asked = 0
        conv_state.record_turn(
            new_signal_ids=triage_reading.matched_signal_ids, user_text=request.text, response_text=reply_out
        )
        await state.save_state(str(request.session_id), conv_state, redis=redis)
        await write_turn_audit_log(
            session_id=request.session_id,
            user_id=request.user_id,
            turn_number=conv_state.turn_count,
            served_from=served,
            retrieved_chunk_ids=[f"therapist_turn:{curated.turn_id}"],
            matched_signal_ids=triage_reading.matched_signal_ids,
            matched_rule_id=routing_decision.rule_id,
            triage_tier=tier,
            confidence_score=conv_state.confidence_score,
            score_tier=score_tier,
            redirect_ready=redirect_ready,
            latency_ms={**latency, "curated_similarity": round(curated.similarity, 4)},
        )
        return

    if cached:
        yield cached
        conv_state.record_turn(
            new_signal_ids=triage_reading.matched_signal_ids, user_text=request.text, response_text=cached
        )
        await state.save_state(str(request.session_id), conv_state, redis=redis)
        await write_turn_audit_log(
            session_id=request.session_id,
            user_id=request.user_id,
            turn_number=conv_state.turn_count,
            served_from=served_from or "exact_cache",
            matched_signal_ids=triage_reading.matched_signal_ids,
            matched_rule_id=routing_decision.rule_id,
            triage_tier=tier,  # FIXED: this branch never logged tier before, hiding routing/triage
            # results on the (common) cache-hit path even though both still genuinely ran.
            confidence_score=conv_state.confidence_score,
            score_tier=score_tier,
            redirect_ready=redirect_ready,
            latency_ms=latency,
        )
        return

    if curated is not None and curated.band == "partial":
        # PARTIAL therapist match, "rephrase" mode (verbatim mode returned above): the LLM may lightly
        # reword the therapist's reply and nothing else. The output is BUFFERED (it is one or two
        # sentences) so it can be checked BEFORE the user sees any of it -- if it drifts from the
        # therapist's wording, the therapist's own reply is served instead. A failed rewording is
        # never shown. Small prompt, no clinical-markers table -> fast.
        shown = curated.examples or []
        rephrase_prompt = build_rephrase_prompt(
            persona=request.persona,
            user_message=request.text,
            examples=[(e.user_text, e.reply_text) for e in shown] or [("", curated.reply_text)],
            recent_turns=conv_state.recent_turns,
            language_instruction=language_instruction(language_style),
        )
        # The reword may draw on ANY of the shown replies, so it is checked against all of them
        # together; if it fails, only the single best reply is ever served as the fallback.
        allowed_text = " ".join(e.reply_text for e in shown) or curated.reply_text
        t_llm = time.monotonic()
        final_text = ""
        served = "therapist_adapted"
        interrupted = False
        try:
            try:
                adapted = "".join([c async for c in llm.generate_stream(rephrase_prompt)]).strip()
                # For a Hindi/Hinglish user the LLM writes the reply directly in their language from the
                # English examples, so the word-overlap test can't apply (different language) -- only the
                # numbers/links/length checks do. The English path keeps the full check.
                verdict = check_rephrase_faithful(
                    adapted, original=allowed_text, check_overlap=language_style == "en"
                )
                if verdict.passed:
                    final_text = adapted
                else:
                    logger.warning("rephrase_rejected_serving_verbatim", reason=verdict.reason)
                    final_text, served = await _out(curated.reply_text, "therapist_reply"), "therapist_verbatim_fallback"
            except Exception as exc:  # noqa: BLE001 -- an LLM failure must never cost the user the reply
                logger.error("rephrase_llm_failed_serving_verbatim", error=str(exc))
                final_text, served = await _out(curated.reply_text, "therapist_reply"), "therapist_verbatim_fallback"
            yield final_text
        except (asyncio.CancelledError, GeneratorExit):
            interrupted = True
            raise
        finally:
            latency["llm_ms"] = (time.monotonic() - t_llm) * 1000
            latency["total_ms"] = (time.monotonic() - t0) * 1000
            conv_state.clarifications_asked = 0
            conv_state.record_turn(
                new_signal_ids=triage_reading.matched_signal_ids, user_text=request.text, response_text=final_text
            )
            await state.save_state(str(request.session_id), conv_state, redis=redis)
            await write_turn_audit_log(
                session_id=request.session_id,
                user_id=request.user_id,
                turn_number=conv_state.turn_count,
                served_from=f"{served}_interrupted" if interrupted else served,
                retrieved_chunk_ids=[f"therapist_turn:{e.turn_id}" for e in shown] or [f"therapist_turn:{curated.turn_id}"],
                matched_signal_ids=triage_reading.matched_signal_ids,
                matched_rule_id=routing_decision.rule_id,
                triage_tier=tier,
                confidence_score=conv_state.confidence_score,
                score_tier=score_tier,
                redirect_ready=redirect_ready,
                latency_ms={**latency, "curated_similarity": round(curated.similarity, 4)},
            )
        return

    # Step 8: prompt assembly. `guidance` is GATED content, never a raw signal/symptom label handed
    # to the LLM as if it were fact (see app.pipeline.retrieval's confidence-threshold docstring and
    # the accuracy discussion this design is built from) -- exactly one of:
    #   1. A confirmed Tier 1 self-care recommendation (genuine search, confidence-gated), or
    #   2. Doctor-written probing guidance for the closest candidate pattern -- an INSTRUCTION for
    #      what to ask next, never the pattern's clinical name/diagnosis itself.
    # Self-care is tried first because it only applies once tier is actually confirmed via a real
    # routing match; probing guidance is the fallback for "not enough evidence yet."
    retrieved_chunk_ids: list[str] = []
    guidance = None
    served_from_label = "rag_retrieval"
    if interlock_result.possible_concern:
        # Soft-zone match (see app.safety.interlock.SOFT_ZONE_ELIGIBLE_FLAGS) -- not dangerous
        # enough to hard-escalate, but worth a real, doctor-written gentle follow-up question
        # rather than either silently ignoring it or firing an alarming crisis script at what's
        # very likely an ordinary message. Takes priority over the usual self-care/probing lookup
        # below -- a possible safety-adjacent concern outranks a routine recommendation.
        guidance = (
            f"The user's message touched on something that might be worth gently checking on "
            f"(possible concern: {interlock_result.clinical_meaning}), but it's far from certain "
            f"this is actually serious -- do NOT assume anything is wrong or mention any clinical "
            f"concept. Simply, naturally, weave in this real follow-up question: "
            f"\"{interlock_result.clarifying_guidance}\""
        )
        served_from_label = "interlock_possible_concern"
    elif score_tier >= 2 and redirect_ready:
        # Confidence gate cleared -- see app.pipeline.tier_scoring.should_redirect_to_booking and
        # 28_TIER_SCORING_APPROACH.md's "Score and redirect are two different decisions" section.
        # Multiple distinct signals AND both duration and impact confirmed across the conversation,
        # not just one message pushing the score over a line -- only now does the reply nudge
        # toward booking, and even then as a gentle suggestion, not an automatic handoff.
        guidance = (
            "This conversation has shown a sustained, corroborated pattern of concern over multiple "
            "messages -- not just one strong sentence. Duration and real-life impact have both come "
            "up. Gently and warmly suggest that talking to a mental health professional could really "
            "help, and ask if they'd like help finding or booking one. Keep the tone caring, not "
            "alarming or clinical -- this is a supportive suggestion, not an emergency."
        )
        served_from_label = "tier_redirect_ready"
    elif tier == 1:
        self_care_matches = await search_self_care_content(
            text_en,
            tier=1,
            language=request.language,
            db=db,
            embedding_provider=embedding_provider,
            query_embedding=query_embedding,
        )
        if self_care_matches:
            guidance = self_care_matches[0].text
            retrieved_chunk_ids = [c.chunk_id for c in self_care_matches]

    if guidance is None and conv_state.candidate_pattern_id is not None:
        guidance = await fetch_probing_guidance(conv_state.candidate_pattern_id, db=db)

    if not interlock_result.possible_concern and score_tier >= 2 and not redirect_ready:
        # Tier 2/3-level score, but not yet confident enough to redirect (see the confidence gate
        # above). Per the design doc, the default here is to KEEP LISTENING, not push toward
        # booking on the strength of one message -- gently work toward the two key clinical
        # questions (duration, impact) that the redirect gate is actually waiting on.
        missing = []
        if not conv_state.duration_established:
            missing.append("how long this has been going on")
        if not conv_state.impact_established:
            missing.append("whether it's affecting their day-to-day life (sleep, work, relationships)")
        if missing:
            nudge = (
                f"Somewhere in your reply, naturally (not like a checklist), ask about "
                f"{' and '.join(missing)}. Don't suggest booking a consultation yet -- this "
                f"conversation isn't confident enough for that; keep listening and supporting."
            )
            guidance = f"{guidance}\n\n{nudge}" if guidance else nudge
            served_from_label = "tier_gathering_evidence"

    # No therapist conversation matched AND nothing else gave us grounding material: ASK a therapist-
    # written clarifying question rather than let the LLM guess (doc 32, Gate 2) -- at most
    # CURATED_CLARIFY_LIMIT in a row, and not for a bare "hi". Skipped on a soft-zone concern (that
    # has its own doctor-written follow-up).
    if (
        use_therapist_library
        and curated is None
        and guidance is None
        and not interlock_result.possible_concern
        and conv_state.clarifications_asked < settings.curated_clarify_limit
        and len(text_en.split()) >= MIN_CLARIFY_WORDS
    ):
        clarify = await find_clarifying_question(query_embedding)
        if clarify is not None:
            question, question_similarity = clarify
            question = await _out(question, "clarifying_question")
            yield question
            conv_state.clarifications_asked += 1
            conv_state.record_turn(
                new_signal_ids=triage_reading.matched_signal_ids, user_text=request.text, response_text=question
            )
            await state.save_state(str(request.session_id), conv_state, redis=redis)
            await write_turn_audit_log(
                session_id=request.session_id,
                user_id=request.user_id,
                turn_number=conv_state.turn_count,
                served_from="therapist_clarify",
                matched_signal_ids=triage_reading.matched_signal_ids,
                matched_rule_id=routing_decision.rule_id,
                triage_tier=tier,
                confidence_score=conv_state.confidence_score,
                score_tier=score_tier,
                redirect_ready=redirect_ready,
                latency_ms={**latency, "clarify_similarity": round(question_similarity, 4)},
            )
            return

    prompt = build_prompt(
        PromptInputs(
            persona=request.persona,
            user_message=request.text,
            retrieved_guidance=guidance,
            # TEMPORARY fix (2026-10-01): this was hardcoded to [] -- the LLM had no memory of
            # anything said earlier in the conversation at all. conv_state.recent_turns (see
            # app.pipeline.state) now carries the last few turns verbatim; prompt_builder trims it
            # further to MAX_RECENT_TURNS. This is plain history, not a real running summary -- the
            # bigger intended design (below) is still pending.
            recent_turns=conv_state.recent_turns,
            running_summary=None,  # TODO: load from ConversationSession.summary once ownership is resolved
            few_shot_examples=request.few_shot_examples,
            language_instruction=language_instruction(language_style),
        )
    )

    # Step 9: token metering / rate limit check.
    # TODO: implement per-user rate limiting (documnets/understanding/APPROACH.md §8) -- not yet
    # modeled. Left as an explicit gap rather than a silent no-op that looks implemented.

    # Optional filler phrase while the LLM's first token is pending -- see
    # documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §4. Only emit this if there's an actual
    # expected gap; a real implementation should base this on measured p50 first-token latency.
    # DISABLED 2026-10-01 at direct request -- was firing on every single turn ("let me think about
    # that...") and that got repetitive/unwanted during voice testing. Re-enable once filler
    # selection is smarter (e.g. only on turns with an actual latency gap, varied phrasing) --
    # see app.pipeline.filler and 09_LATENCY_AND_PERFORMANCE.md §4 for the full intended design.
    # filler = select_filler(FillerSituation.THINKING, language=request.language)
    # if filler:
    #     yield filler + " "

    # Step 10: the LLM call -- phrasing only, never the safety decision or the retrieved facts.
    # Wrapped start-to-finish (through steps 11-14) in try/finally: if this generator is cancelled
    # here (voice barge-in cancels the task driving this call), the `finally` block below still
    # runs -- asyncio delivers CancelledError at the current `yield`/`await` and finally blocks run
    # during that unwind -- so an interrupted turn still gets its state saved and audited on
    # whatever partial response it managed to produce, instead of vanishing from the record.
    t_llm = time.monotonic()
    full_response_parts: list[str] = []
    interrupted = False
    try:
        async for chunk in llm.generate_stream(prompt):
            full_response_parts.append(chunk)
            yield chunk
    except (asyncio.CancelledError, GeneratorExit):
        interrupted = True
        raise
    finally:
        latency["llm_ms"] = (time.monotonic() - t_llm) * 1000
        latency["total_ms"] = (time.monotonic() - t0) * 1000
        response_text = "".join(full_response_parts)

        # Step 11: output guardrail -- skipped on an interrupted turn, there's no point grading a
        # response that was cut off mid-sentence and never fully reached the user anyway.
        if not interrupted and response_text:
            guardrail_result = check_grounding(response_text, retrieved_context=guidance)
            if not guardrail_result.passed:
                logger.warning(
                    "guardrail_failed", reason=guardrail_result.reason, session_id=str(request.session_id)
                )
                # TODO: define the actual remediation -- re-prompt, fall back to a safe generic
                # response, etc. Logging only today so the failure is visible, not silently ignored.

        # Step 12: response already streamed above via `yield` (partially, if interrupted).
        conv_state.record_turn(
            new_signal_ids=triage_reading.matched_signal_ids,
            user_text=request.text,
            response_text=response_text,
        )
        await state.save_state(str(request.session_id), conv_state, redis=redis)

        # Not cached on an interrupted turn -- a partial, cut-off response is not a valid cached
        # answer to this question and must never be served whole to a future, uninterrupted turn.
        if response_text and not interrupted:
            await cache.set_exact_cache(request.text, response_text, language=request.language, redis=redis)

        # Steps 13-14: audit log + session summary -- fired async, never blocking the response
        # above. Still fires on an interrupted turn (served_from records that explicitly) --
        # losing the audit trail for an interrupted turn would be a real gap in a design that
        # otherwise guarantees one on every single turn, cache hit or not.
        await write_turn_audit_log(
            session_id=request.session_id,
            user_id=request.user_id,
            turn_number=conv_state.turn_count,
            served_from=f"{served_from_label}_interrupted" if interrupted else served_from_label,
            matched_signal_ids=triage_reading.matched_signal_ids,
            matched_rule_id=routing_decision.rule_id,
            retrieved_chunk_ids=retrieved_chunk_ids or None,
            triage_tier=tier,
            confidence_score=conv_state.confidence_score,
            score_tier=score_tier,
            redirect_ready=redirect_ready,
            # Not a hard escalation (interlock_triggered stays False -- the LLM path ran normally),
            # but for a soft-zone turn this records WHICH flag prompted the clarifying question, so
            # the audit trail can distinguish "no concern at all" from "possible concern, handled
            # gently".
            interlock_flag_id=interlock_result.flag_id if interlock_result.possible_concern else None,
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
