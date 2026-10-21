"""
Wraps app.pipeline.orchestrator.run_turn as a livekit-agents 1.x `llm.LLM` plugin, so the voice
path calls the EXACT SAME pipeline function as the text HTTP endpoint
(app.api.v1.endpoints.conversation) -- the one non-negotiable invariant the whole conversation-
layer build is organized around (see run_turn's own module docstring and app.realtime.agent's).

This is not "an LLM" in the vendor sense. livekit-agents' `llm.LLM` slot in `AgentSession` is being
used here as "the thing that takes the latest user utterance and produces a reply" -- which
run_turn already does in full (safety interlock, triage, routing, caching, retrieval, and only
then the real Sarvam LLM call for phrasing). The framework doesn't need to know any of that
happens inside; it just sees `chat()` return a stream of `ChatChunk` text deltas, like any other
LLM plugin would.

Confirmed against the real installed livekit-agents 1.8.3 package via introspection: `LLMStream._run()`
emits output by calling `self._event_ch.send_nowait(ChatChunk(...))`, not by yielding/returning --
verified by reading the base class's actual `_LLMEventChannel` source, not assumed from docs.
"""

import asyncio
import uuid

from livekit.agents import llm
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, APIConnectOptions, NotGivenOr
from redis.asyncio import Redis

from app.db.session import AsyncSessionLocal
from app.pipeline.orchestrator import TurnRequest, run_turn
from app.providers.base import EmbeddingProvider
from app.providers.factory import get_llm_provider
from app.providers.language_id import identify_language

# How much of the reply to accumulate before asking Sarvam's /text-lid which language it's in --
# long enough for a reliable read (a couple of words can misclassify), short enough that the
# answer is ready before the framework's sentence tokenizer finishes the first sentence and calls
# TTS. Not science, a practical middle ground -- revisit against real latency numbers if needed.
_LANGUAGE_DETECTION_MIN_CHARS = 12


class OrchestratorLLM(llm.LLM):
    """One instance per voice session, constructed once in app.realtime.agent.entrypoint --
    session_id/language are fixed for the Room's lifetime; redis/embedding_provider are shared
    app resources threaded through, not per-call state."""

    def __init__(
        self,
        *,
        session_id: uuid.UUID,
        language: str,
        redis: Redis,
        embedding_provider: EmbeddingProvider,
        tts_language_state: dict[str, str],
        sarvam_api_key: str,
        sarvam_api_base: str,
    ):
        super().__init__()
        self._session_id = session_id
        self._language = language
        self._redis = redis
        self._embedding_provider = embedding_provider
        self._tts_language_state = tts_language_state
        self._sarvam_api_key = sarvam_api_key
        self._sarvam_api_base = sarvam_api_base

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict] = NOT_GIVEN,
    ) -> "_OrchestratorLLMStream":
        return _OrchestratorLLMStream(
            llm_instance=self,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
            session_id=self._session_id,
            language=self._language,
            redis=self._redis,
            embedding_provider=self._embedding_provider,
            tts_language_state=self._tts_language_state,
            sarvam_api_key=self._sarvam_api_key,
            sarvam_api_base=self._sarvam_api_base,
        )


def _latest_user_text(chat_ctx: llm.ChatContext) -> str:
    """The orchestrator doesn't take conversation history (it loads its own running state from
    Redis via session_id -- see app.pipeline.state and the TODOs in orchestrator.py about recent-
    turn history not being wired in yet), so only the newest user utterance matters here."""
    for item in reversed(chat_ctx.items):
        if isinstance(item, llm.ChatMessage) and item.role == "user":
            return item.text_content or ""
    return ""


class _OrchestratorLLMStream(llm.LLMStream):
    def __init__(
        self,
        *,
        llm_instance: OrchestratorLLM,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool],
        conn_options: APIConnectOptions,
        session_id: uuid.UUID,
        language: str,
        redis: Redis,
        embedding_provider: EmbeddingProvider,
        tts_language_state: dict[str, str],
        sarvam_api_key: str,
        sarvam_api_base: str,
    ):
        super().__init__(llm_instance, chat_ctx=chat_ctx, tools=tools, conn_options=conn_options)
        self._session_id = session_id
        self._language = language
        self._redis = redis
        self._embedding_provider = embedding_provider
        self._tts_language_state = tts_language_state
        self._sarvam_api_key = sarvam_api_key
        self._sarvam_api_base = sarvam_api_base

    async def _run(self) -> None:
        user_text = _latest_user_text(self._chat_ctx)
        if not user_text.strip():
            return

        # TurnRequest.language stays fixed ("en") regardless of what the user actually spoke --
        # it scopes KB retrieval/caching, and the KB is English-only in Phase 1 (CLAUDE.md §5), so
        # routing it to "hi" would just make retrieval find nothing. The REPLY's language is a
        # separate, downstream concern: the prompt (app.pipeline.prompt_builder) now explicitly
        # tells the LLM to mirror the user's actual language/script, independent of this field --
        # exactly the split CLAUDE.md §5 already documents ("the LLM always replies in whatever
        # language the user used... independent of which language the retrieved chunk was in").
        request = TurnRequest(
            session_id=self._session_id, user_id=None, language=self._language, text=user_text
        )
        # One id per LLM-slot call, not per orchestrator turn -- matches how every other LLM
        # plugin's ChatChunk.id scopes a single chat() invocation's output.
        request_id = str(uuid.uuid4())

        detection_buffer = ""
        language_detected = False

        # A fresh session per turn, same as the text endpoint's app.api.deps.get_db per-request
        # dependency -- not held open for the whole voice call.
        async with AsyncSessionLocal() as db:
            async for chunk in run_turn(
                request,
                db=db,
                redis=self._redis,
                llm=get_llm_provider(),
                embedding_provider=self._embedding_provider,
            ):
                self._event_ch.send_nowait(
                    llm.ChatChunk(id=request_id, delta=llm.ChoiceDelta(role="assistant", content=chunk))
                )

                # Figure out what language this reply is actually in, once, as soon as there's
                # enough text to tell -- fired in the background (not awaited here) so identifying
                # the language never delays a single token reaching the user. See
                # app.providers.language_id's docstring for why this can't just reuse the user's
                # input language or the STT's own per-utterance language tag.
                if not language_detected:
                    detection_buffer += chunk
                    if len(detection_buffer) >= _LANGUAGE_DETECTION_MIN_CHARS:
                        language_detected = True
                        asyncio.create_task(self._update_tts_language(detection_buffer))

    async def _update_tts_language(self, text: str) -> None:
        detected = await identify_language(
            text,
            api_key=self._sarvam_api_key,
            api_base=self._sarvam_api_base,
            fallback=self._tts_language_state["current"],
        )
        self._tts_language_state["current"] = detected
