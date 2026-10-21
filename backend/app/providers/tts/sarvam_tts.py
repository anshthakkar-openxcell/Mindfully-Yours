"""
Sarvam Text-to-Speech (Bulbul) real-time streaming adapter -- primary and only voice provider.

Confirmed against Sarvam's real API reference (docs.sarvam.ai, Oct 2026) AND a live synthesis call
(not guessed, not just documented) -- same diligence as app.providers.llm.sarvam and
app.providers.stt.sarvam_stt:
- `wss://api.sarvam.ai/text-to-speech/ws`. The docs still listed `bulbul:v2` as current, but a live
  call returned `400: Model 'bulbul:v2' has been deprecated. Please use 'bulbul:v3' instead.` --
  confirming the docs lag the real API here. `bulbul:v3` is the default model; `shubh` is one of
  its real speaker names (v3 and v2 have non-overlapping speaker lists -- a v2 speaker name on v3
  fails with a 400 listing the real options, which is how `shubh` was confirmed). v3's default
  sample rate is 24000 Hz, not v2's 22050.
- Auth header: `api-subscription-key` (same header name as every other Sarvam adapter).
- Unlike the STT websocket, session config here is a JSON message sent right after connecting, not
  a query string: `{"type": "config", "data": {language_code, speaker, model, output_audio_codec,
  speech_sample_rate, ...}}`.
- Text is sent as `{"type": "text", "data": {"text": "..."}}`; the server buffers internally
  (`min_buffer_size`, default 50 chars) before synthesizing, so a short chunk needs an explicit
  `{"type": "flush"}` to force it out immediately rather than sitting unsent in Sarvam's buffer --
  per documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §3, callers here feed this one sentence
  at a time, which is exactly the case that needs an explicit flush.
- Audio comes back as `{"type": "audio", "data": {"content_type": ..., "audio": "<base64>"}}`
  chunks -- base64-encoded, not binary frames, decoded here before yielding.
- `output_audio_codec="linear16"` (raw PCM) is requested rather than the wav/mp3 default so the
  bytes this adapter yields are playable audio samples directly, not a container format that would
  need a separate decode step before they can be pushed onto a LiveKit audio track.

Known limitation, left as an explicit gap rather than silently "fixed": this opens a fresh
websocket connection per `synthesize_stream()` call (per sentence, given the one-sentence-at-a-time
caller contract) rather than keeping one connection open and reused across every sentence of a
single turn -- documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §8 wants warm, reused
connections. Doing that properly needs the TTSProvider interface itself to accept an async
iterable of text (so one call spans a whole turn) instead of one string per call -- a real
interface change, not an adapter-only fix, and out of scope for this pass.
"""

import base64
import json
from collections.abc import AsyncIterator

import websockets

from app.core.exceptions import ProviderError
from app.providers.base import TTSProvider

# Phase 1 is English-only (documnets/understanding/13_LANGUAGE_PHASING.md) -- extend when Hindi
# actually ships rather than guessing ahead.
_BCP47 = {"en": "en-IN", "hi": "hi-IN"}


class SarvamTTSProvider(TTSProvider):
    def __init__(
        self,
        api_key: str,
        api_base: str,
        model: str = "bulbul:v3",
        speaker: str = "shubh",
        sample_rate: int = 24000,
    ):
        self._api_key = api_key
        # Same host as every other Sarvam adapter (SARVAM_API_BASE), just over wss:// instead of
        # https:// -- one configured base for the whole vendor, not a second URL to keep in sync.
        self._ws_base = api_base.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
        self._model = model
        self._speaker = speaker
        self._sample_rate = sample_rate

    @property
    def sample_rate(self) -> int:
        """The sample rate of the raw PCM audio this adapter yields -- callers that need to
        declare an audio format up front (e.g. app.realtime.livekit_tts's AudioEmitter.initialize)
        read this rather than reaching into a private attribute."""
        return self._sample_rate

    async def synthesize_stream(self, text: str, *, language: str = "en") -> AsyncIterator[bytes]:
        if not self._api_key:
            raise ProviderError("sarvam_tts", "SARVAM_API_KEY is not configured.")
        if not text.strip():
            return

        try:
            async with websockets.connect(
                f"{self._ws_base}/text-to-speech/ws?model={self._model}&send_completion_event=true",
                additional_headers={"api-subscription-key": self._api_key},
            ) as ws:
                await ws.send(
                    json.dumps(
                        {
                            "type": "config",
                            "data": {
                                "language_code": _BCP47.get(language, language),
                                "speaker": self._speaker,
                                "model": self._model,
                                "speech_sample_rate": str(self._sample_rate),
                                "output_audio_codec": "linear16",
                            },
                        }
                    )
                )
                await ws.send(json.dumps({"type": "text", "data": {"text": text}}))
                # Forces immediate synthesis of this chunk rather than waiting for Sarvam's own
                # internal buffer threshold (min_buffer_size, default 50 chars) to fill -- without
                # this, a short sentence could sit unsent, defeating the point of streaming per
                # sentence instead of per full response.
                await ws.send(json.dumps({"type": "flush"}))

                async for raw in ws:
                    event = json.loads(raw)
                    event_type = event.get("type")
                    if event_type == "audio":
                        yield base64.b64decode(event["data"]["audio"])
                    elif event_type == "event" and event.get("data", {}).get("event_type") == "final":
                        break
                    elif event_type == "error":
                        detail = event.get("data", {})
                        raise ProviderError("sarvam_tts", f"Sarvam TTS error: {detail.get('message')}")
        except websockets.exceptions.WebSocketException as exc:
            raise ProviderError("sarvam_tts", f"Sarvam TTS connection failed: {exc}") from exc
