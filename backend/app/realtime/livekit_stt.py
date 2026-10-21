"""
Adapts app.providers.stt.sarvam_stt.SarvamSTTProvider (our own real, live-tested Sarvam Saaras
streaming adapter) into the livekit-agents 1.x `stt.STT` plugin interface, so it can be passed
directly to `AgentSession(stt=...)` per
documnets/understanding/31_CONVERSATION_LAYER_IMPLEMENTATION_PLAN.md Phase 5.

Deliberately a thin adapter, not a second implementation of the Sarvam integration -- all the
actual websocket/streaming logic stays in app.providers.stt.sarvam_stt, unchanged and still
directly covered by that module's own live round-trip test. This file only translates between
livekit-agents' SpeechEvent/AudioFrame shapes and our TranscriptChunk/bytes shapes.

Confirmed against the real installed livekit-agents 1.8.3 package via introspection (not
guessed/assumed from docs, which are not always in sync with a pinned version -- see
app.providers.tts.sarvam_tts's docstring for why that caution matters here specifically, not just
in the abstract):
- `stt.RecognizeStream.__init__(sample_rate=16000)` makes the base class automatically resample
  every pushed `rtc.AudioFrame` to 16kHz before it reaches `self._input_ch` -- this adapter does
  NOT do its own resampling, unlike the caller contract SarvamSTTProvider documents for a
  non-LiveKit caller (it assumes an already-16kHz byte stream; here, the base class guarantees that).
- `rtc.AudioFrame.data` is a memoryview cast to 16-bit samples; `bytes(frame.data)` recovers the
  exact raw little-endian PCM16 bytes SarvamSTTProvider expects -- verified empirically (round-
  tripping known sample values through AudioFrame and back produced byte-identical output).
"""

from collections.abc import AsyncIterator

from livekit import rtc
from livekit.agents import stt
from livekit.agents.stt.stt import AudioBuffer
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, APIConnectOptions, NotGivenOr
from livekit.agents.utils import is_given

from app.providers.stt.sarvam_stt import SarvamSTTProvider


class SarvamLiveKitSTT(stt.STT):
    def __init__(self, provider: SarvamSTTProvider, *, language: str = "en"):
        super().__init__(capabilities=stt.STTCapabilities(streaming=True, interim_results=True))
        self._provider = provider
        self._language = language

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        """One-shot batch recognize -- required by the base class, but not this system's real
        path (voice conversation always goes through `stream()` below). Implemented by draining
        the same streaming adapter over one pre-combined buffer, rather than adding a second
        (REST) Sarvam integration that nothing in this codebase would otherwise call."""
        lang = language if is_given(language) else self._language
        frame = rtc.combine_audio_frames(buffer) if isinstance(buffer, list) else buffer
        raw = bytes(frame.data)

        async def one_chunk() -> AsyncIterator[bytes]:
            yield raw

        text = ""
        async for chunk in self._provider.transcribe_stream(one_chunk(), language=lang):
            if chunk.is_final:
                text = chunk.text
        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt.SpeechData(language=lang, text=text)],
        )

    def stream(
        self,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> "_SarvamRecognizeStream":
        lang = language if is_given(language) else self._language
        return _SarvamRecognizeStream(
            stt=self, provider=self._provider, language=lang, conn_options=conn_options
        )


class _SarvamRecognizeStream(stt.RecognizeStream):
    def __init__(
        self,
        *,
        stt: SarvamLiveKitSTT,
        provider: SarvamSTTProvider,
        language: str,
        conn_options: APIConnectOptions,
    ):
        # sample_rate=16000 -- see module docstring: the base class resamples every pushed frame
        # to this rate before _run() ever sees it, satisfying SarvamSTTProvider's caller contract.
        super().__init__(stt=stt, conn_options=conn_options, sample_rate=16000)
        self._provider = provider
        self._language = language

    async def _run(self) -> None:
        async def byte_chunks() -> AsyncIterator[bytes]:
            async for item in self._input_ch:
                if isinstance(item, stt.RecognizeStream._FlushSentinel):
                    # A flush marks an input segment boundary (e.g. on end_input()) -- our
                    # continuous streaming session doesn't need a distinct per-segment action,
                    # Sarvam's own VAD-based endpointing already demarcates utterances.
                    continue
                yield bytes(item.data)

        async for chunk in self._provider.transcribe_stream(byte_chunks(), language=self._language):
            event_type = (
                stt.SpeechEventType.FINAL_TRANSCRIPT
                if chunk.is_final
                else stt.SpeechEventType.INTERIM_TRANSCRIPT
            )
            self._event_ch.send_nowait(
                stt.SpeechEvent(
                    type=event_type,
                    alternatives=[stt.SpeechData(language=self._language, text=chunk.text)],
                )
            )
