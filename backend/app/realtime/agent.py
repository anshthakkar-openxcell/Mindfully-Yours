"""
LiveKit Agent -- the server-side participant that joins an AI Companion Room, per
documnets/understanding/10_LIVEKIT_REALTIME.md §3 and
documnets/understanding/31_CONVERSATION_LAYER_IMPLEMENTATION_PLAN.md Phase 5.

Scope reminder: this process JOINS a Room it's handed a token for -- it never CREATES Rooms or
issues tokens (that's the NestJS backend, out of scope here). Practitioner/SOS rooms never involve
this Agent at all; it exists purely for the AI Companion use case.

LiveKit only carries the media -- it makes no decisions. Triage, the interlock, and grounding are
entirely app.pipeline / app.safety logic, running unchanged inside app.pipeline.orchestrator.run_turn,
unaffected by how the audio got here. This module's job is exactly: join the Room, build an
AgentSession wired to our own Sarvam STT/TTS adapters and the orchestrator (via the thin
livekit-agents plugin wrappers in app.realtime.livekit_stt/livekit_tts/livekit_llm), and let the
LiveKit Agents framework itself own voice-activity detection, turn-taking, and barge-in -- per
LIVEKIT.md §4/§6, that is a solved problem in the framework, not something to reimplement here.

Room/session identification is intentionally minimal scaffolding, not a real contract: per
documnets/understanding/31_CONVERSATION_LAYER_IMPLEMENTATION_PLAN.md §5/§6, designing the real
Room-naming/metadata contract with the (out-of-scope) NestJS backend is explicitly deferred. Room
name is read as the session_id directly; if it isn't a valid UUID (e.g. ad-hoc manual testing), a
fresh one is generated for that run so the Agent still works standalone.
"""

import uuid

from livekit import agents, rtc
from livekit.agents import AgentSession, JobContext, JobProcess, WorkerOptions
from livekit.agents.voice import room_io
from livekit.plugins import noise_cancellation, silero
from redis.asyncio import from_url as redis_from_url

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import AsyncSessionLocal
from app.pipeline.welcome import pick_welcome
from app.providers.factory import get_embedding_provider, get_stt_provider, get_tts_provider
from app.realtime.livekit_llm import OrchestratorLLM
from app.realtime.livekit_stt import SarvamLiveKitSTT
from app.realtime.livekit_tts import SarvamLiveKitTTS

logger = get_logger(__name__)
settings = get_settings()

# Phase 1 is English-only by design (documnets/understanding/13_LANGUAGE_PHASING.md) -- this is a
# fixed default, not a guess, until Hindi actually ships and Room metadata carries a real value.
DEFAULT_LANGUAGE = "en"

# The Agent's own `instructions` are framework bookkeeping, not the real prompt: all persona/
# grounding/safety prompt assembly happens inside app.pipeline.prompt_builder.build_prompt, called
# from inside run_turn (via app.realtime.livekit_llm.OrchestratorLLM). This string exists only
# because livekit-agents' Agent.__init__ requires one; our custom llm_node equivalent (chat())
# ignores the framework's own system-prompt injection entirely.
_AGENT_INSTRUCTIONS = (
    "Unused by this Agent's own logic -- see app.realtime.livekit_llm.OrchestratorLLM. "
    "All real persona/prompt assembly happens inside app.pipeline.prompt_builder."
)


def prewarm(proc: JobProcess) -> None:
    """Runs once per worker process, before any job is accepted -- loading the VAD model here
    (rather than per-job in entrypoint) avoids paying its load cost on every single Room join.

    Also where logging gets configured for this process: each job runs in its own subprocess
    (job_executor_type=PROCESS, the default), so app.core.logging.configure_logging() -- which
    sets GLOBAL structlog/stdlib state -- has to run once per subprocess, same as app.main does
    for the FastAPI process. Without this, every log line in this process (including every
    orchestrator/safety log on every single turn) silently falls back to structlog's unconfigured
    default instead of the structured JSON logging the rest of this service relies on."""
    configure_logging()
    proc.userdata["vad"] = silero.VAD.load()


def _resolve_session_id(room: rtc.Room) -> uuid.UUID:
    try:
        return uuid.UUID(room.name)
    except ValueError:
        generated = uuid.uuid4()
        logger.warning(
            "room_name_not_a_uuid_generating_session_id",
            room_name=room.name,
            generated_session_id=str(generated),
        )
        return generated


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    session_id = _resolve_session_id(ctx.room)
    language = DEFAULT_LANGUAGE

    logger.info("voice_agent_joining_room", room_name=ctx.room.name, session_id=str(session_id))

    redis = redis_from_url(settings.redis_url, decode_responses=False)
    embedding_provider = get_embedding_provider()

    # Shared mutable state, not a constant: app.realtime.livekit_llm.OrchestratorLLM updates
    # ["current"] once per turn (after identifying the actual language of its reply -- see that
    # module and app.providers.language_id for why), and app.realtime.livekit_tts.SarvamLiveKitTTS
    # reads it fresh on every sentence it synthesizes. "en" here is only the fallback before the
    # very first turn's detection completes.
    tts_language_state: dict[str, str] = {"current": language}

    # "auto" (not a fixed language) -- confirmed live (2026-10-01) that Sarvam's realtime STT
    # correctly adapts per utterance within one long-lived connection, including a genuine
    # mid-conversation switch from English to Hindi in the same session -- forcing "en" here would
    # have badly mangled any Hindi speech instead of transcribing it (even imperfectly) in kind.
    stt_plugin = SarvamLiveKitSTT(provider=get_stt_provider(), language="auto")
    tts_plugin = SarvamLiveKitTTS(provider=get_tts_provider(), language_state=tts_language_state)
    llm_plugin = OrchestratorLLM(
        session_id=session_id,
        language=language,
        redis=redis,
        embedding_provider=embedding_provider,
        tts_language_state=tts_language_state,
        sarvam_api_key=settings.sarvam_api_key,
        sarvam_api_base=settings.sarvam_api_base,
    )

    session = AgentSession(
        stt=stt_plugin,
        llm=llm_plugin,
        tts=tts_plugin,
        vad=ctx.proc.userdata["vad"],
        # Built-in barge-in per LIVEKIT.md §4/§6 -- do not reimplement voice-activity detection or
        # interruption handling here. On interruption, the framework cancels the task driving
        # OrchestratorLLM's _run() (the in-flight run_turn call) AND clears whatever response audio
        # is still queued/unplayed; see app.pipeline.orchestrator's module docstring for how
        # cancellation is handled safely on the run_turn side (state save + audit log still fire).
        #
        # mode="vad" is explicit, not the default: with both a VAD plugin and a streaming STT
        # present, AgentSession auto-selects its "adaptive" interruption detector instead, which
        # calls out to a LiveKit Cloud ML inference endpoint (confirmed live in this project's own
        # logs: "adaptive interruption detector initialized", base_url agent-gateway.livekit.cloud)
        # specifically tuned to IGNORE short backchannel sounds ("mhm", a cough, background noise)
        # so it doesn't falsely interrupt the agent -- which trades off "stops the instant you make
        # any sound" for "won't stop for a non-interruption." Live-tested 2026-10-01: with a real
        # user speaking over the agent, the adaptive detector did not reliably cut playback. Forcing
        # "vad" uses the already-provided local Silero VAD directly instead -- any detected speech
        # of at least min_duration immediately counts as an interruption, no network round-trip, no
        # judgment call about whether it's a "real" interruption. This is the more literal, more
        # reliable reading of "if the user starts talking, stop" that a voice companion needs.
        turn_handling={"interruption": {"mode": "vad", "min_duration": 0.3}},
    )

    async def _close_redis() -> None:
        await redis.aclose()

    ctx.add_shutdown_callback(_close_redis)

    await session.start(
        agent=agents.Agent(instructions=_AGENT_INSTRUCTIONS),
        room=ctx.room,
        # Background Voice Cancellation -- runs on the raw mic audio BEFORE it ever reaches VAD/STT,
        # specifically trained to suppress other people's voices and ambient noise in the room,
        # keeping only the nearest/loudest speaker. Added 2026-10-01 after live testing showed
        # forcing turn_handling's VAD-based interruption (above) made the agent stop talking for
        # background noise/a third person's voice, not just the actual conversation partner --
        # this is the real fix for that (reduce what VAD ever sees), not a VAD threshold tweak,
        # which would only trade "too sensitive" for "too sluggish" without addressing the cause.
        # Model ships bundled with livekit-plugins-noise-cancellation -- no separate download/setup.
        room_input_options=room_io.RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    # Open the conversation with one of the therapists' own welcome messages, as written (doc 33) --
    # no LLM, so it's spoken immediately. Best-effort: a failed greeting must never break the session,
    # and it stays interruptible like any other agent speech. The voice path doesn't know the user's
    # name, so the greeting is the neutral "Hi there, ...".
    try:
        async with AsyncSessionLocal() as db:
            greeting = await pick_welcome(db, language=language)
        session.say(greeting, allow_interruptions=True)
    except Exception as exc:  # noqa: BLE001
        logger.error("welcome_greeting_failed", error=str(exc), session_id=str(session_id))


if __name__ == "__main__":
    agents.cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            ws_url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
    )
