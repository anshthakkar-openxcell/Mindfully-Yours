"""
Adapts app.providers.tts.sarvam_tts.SarvamTTSProvider (our own real, live-tested Sarvam Bulbul
streaming adapter) into the livekit-agents 1.x `tts.TTS` plugin interface, so it can be passed
directly to `AgentSession(tts=...)` per
documnets/understanding/31_CONVERSATION_LAYER_IMPLEMENTATION_PLAN.md Phase 5.

Deliberately a thin adapter -- all the actual websocket/streaming logic stays in
app.providers.tts.sarvam_tts, unchanged and still directly covered by that module's own live test.

Design decision: `capabilities=TTSCapabilities(streaming=False)`. This is what the former "Phase 4
sentence-boundary buffer" in the conversation-layer plan turned into -- rather than hand-rolling
punctuation-based sentence splitting, declaring non-streaming capability here makes
livekit-agents' own default `tts_node` wrap this TTS in `tts.StreamAdapter` with its blingfire
sentence tokenizer automatically (confirmed by reading the installed package's own
`Agent.default.tts_node` source: it checks `activity.tts.capabilities.streaming` and only skips
the StreamAdapter/tokenizer when it's True). That gives genuine sentence-by-sentence synthesis as
the LLM streams out, for free, using a more robust tokenizer than a hand-written one would be, and
without a second buffering implementation to maintain. SarvamTTSProvider already matches the
resulting one-call-per-text-chunk shape exactly (`synthesize_stream(text) -> AsyncIterator[bytes]`),
so no adaptation was needed on that side either.

Confirmed against the real installed livekit-agents 1.8.3 package via introspection:
- `tts.ChunkedStream._run(self, output_emitter)` is the abstract method; `output_emitter.initialize
  (mime_type="audio/pcm", ...)` tells it the bytes pushed via `.push()` are raw PCM (no container),
  matching SarvamTTSProvider's `output_audio_codec="linear16"` choice exactly -- `end_input()` is
  called automatically by the base class after `_run()` returns, not something this adapter calls.
"""

from livekit.agents import tts
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions

from app.providers.tts.sarvam_tts import SarvamTTSProvider


class SarvamLiveKitTTS(tts.TTS):
    def __init__(self, provider: SarvamTTSProvider, *, language_state: dict[str, str]):
        """`language_state` is a small shared mutable dict (`{"current": "en"}`), the same object
        passed to app.realtime.livekit_llm.OrchestratorLLM, which updates `language_state["current"]`
        once per turn after identifying the actual language of its reply (see that module -- Sarvam
        TTS, unlike the LLM, can't auto-detect language, and Sarvam STT's own per-utterance language
        tag was confirmed live (2026-10-01) to be unreliable for Hindi specifically). Read fresh on
        every `synthesize()` call (one per sentence, per this TTS's non-streaming capability) rather
        than fixed at construction, so a mid-conversation language switch takes effect immediately
        on the next sentence, not just the next turn."""
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=provider.sample_rate,
            num_channels=1,
        )
        self._provider = provider
        self._language_state = language_state

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> "_SarvamChunkedStream":
        return _SarvamChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            provider=self._provider,
            language=self._language_state["current"],
        )


class _SarvamChunkedStream(tts.ChunkedStream):
    def __init__(
        self,
        *,
        tts: SarvamLiveKitTTS,
        input_text: str,
        conn_options: APIConnectOptions,
        provider: SarvamTTSProvider,
        language: str,
    ):
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._provider = provider
        self._language = language

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        output_emitter.initialize(
            request_id=str(id(self)),
            sample_rate=self._tts.sample_rate,
            num_channels=self._tts.num_channels,
            mime_type="audio/pcm",
        )
        async for audio_chunk in self._provider.synthesize_stream(self._input_text, language=self._language):
            output_emitter.push(audio_chunk)
