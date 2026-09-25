"""
LiveKit Agent -- the server-side participant that joins an AI Companion Room, per
documnets/understanding/10_LIVEKIT_REALTIME.md §3. IN SCOPE per
documnets/understanding/14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md Epic G.

Scope reminder: this process JOINS a Room it's handed a token for -- it never CREATES Rooms or
issues tokens (that's the NestJS backend, out of scope here). Practitioner/SOS rooms never involve
this Agent at all; it exists purely for the AI Companion use case.

LiveKit only carries the media -- it makes no decisions. Triage, the interlock, and grounding are
entirely app.pipeline / app.safety logic, unaffected by how the audio got here. This module's job
is exactly: subscribe to the user's audio track -> STT -> app.pipeline.orchestrator.run_turn ->
TTS -> publish the response track. Use LiveKit's built-in interruption/turn-taking handling
(the Agents framework) -- do not reimplement voice-activity detection here.

TODO: this is a structural skeleton. Wire up the actual `livekit-agents` SDK's JobContext /
VoicePipelineAgent (or equivalent, depending on SDK version) once the LiveKit Cloud vs. self-hosted
decision (documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md, LIVEKIT.md §5) is made.
"""

from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)


async def handle_companion_room(*, room_name: str, session_id: UUID, language: str, db, redis) -> None:
    """
    TODO: replace this outline with the real livekit-agents entrypoint. Pseudocode of the
    per-utterance flow, to make the intended shape unambiguous for whoever wires up the SDK:

        stt = get_stt_provider()
        tts = get_tts_provider()
        llm = get_llm_provider()
        embeddings = get_embedding_provider()

        async for user_audio_track in room.subscribed_audio_tracks():
            async for transcript_chunk in stt.transcribe_stream(user_audio_track, language=language):
                if transcript_chunk.is_final:
                    request = TurnRequest(session_id=session_id, user_id=None, language=language,
                                           text=transcript_chunk.text)
                    async for response_text_chunk in run_turn(
                        request, db=db, redis=redis, llm=llm, embedding_provider=embeddings
                    ):
                        async for audio_chunk in tts.synthesize_stream(response_text_chunk, language=language):
                            await room.publish_audio(audio_chunk)

    The critical property to preserve when implementing this for real: app.pipeline.orchestrator.run_turn
    is called EXACTLY the same way here as from app.api.v1.endpoints.conversation -- do not fork
    pipeline logic between the text and voice paths.
    """
    logger.info("livekit_agent_not_yet_implemented", room=room_name, session_id=str(session_id))
    raise NotImplementedError("Wire up the livekit-agents SDK per this module's docstring.")
