"""
Sarvam Speech-to-Text (Saaras) real-time streaming adapter -- the ONLY STT provider.

Decision (2026-10-01): documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #9 had left
dual Deepgram/Sarvam vs. Deepgram-only STT as an open cross-PDF discrepancy. Direct product
decision since: Sarvam only, for both STT and TTS -- Deepgram is not used anywhere in this system.
See that doc's entry for the resolution and
documnets/understanding/31_CONVERSATION_LAYER_IMPLEMENTATION_PLAN.md for the conversation-layer
build this adapter is part of. There is now exactly one STT adapter, not two behind a routing
choice, by design.

Confirmed against Sarvam's real API reference (docs.sarvam.ai, Oct 2026), not guessed -- same
diligence as app.providers.llm.sarvam:
- `wss://api.sarvam.ai/speech-to-text-realtime/ws` (model `saaras:v3-realtime`) -- session config is
  passed as URL query parameters on connect, NOT a JSON config message (unlike the TTS websocket).
- Auth header: `api-subscription-key` (same header name as every other Sarvam adapter in this repo).
- Client -> server: `{"event": "audio_input", "audio": "<base64>"}` per audio chunk.
- Server -> client: `{"event": "transcript.partial" | "transcript.final", "text": ..., ...}` per
  utterance (an `utterance_idx` field demarcates separate utterances within one connection) --
  mapped 1:1 onto this module's `TranscriptChunk(text, is_final)`.
- `session.begin` / `vad.speech_start` / `vad.speech_end` events carry no caller-visible action
  today; they're acknowledged (not raised as errors) but otherwise ignored.

Caller contract: `audio_chunks` must already be mono PCM16 (`linear16`) at 16kHz -- this adapter
does not resample. Getting LiveKit track audio into that exact shape is app.realtime.agent's job
(LiveKit tracks are commonly 48kHz) before handing chunks to this adapter.
"""

import asyncio
import base64
import contextlib
import json
from collections.abc import AsyncIterator
from urllib.parse import urlencode

import websockets

from app.core.exceptions import ProviderError
from app.providers.base import STTProvider, TranscriptChunk

# Phase 1 is English-only (documnets/understanding/13_LANGUAGE_PHASING.md) -- this map only needs
# to be correct for "en" today; extend it when Hindi actually ships rather than guessing ahead.
_BCP47 = {"en": "en-IN", "hi": "hi-IN"}


class SarvamSTTProvider(STTProvider):
    def __init__(
        self, api_key: str, api_base: str, model: str = "saaras:v3-realtime", sample_rate: int = 16000
    ):
        self._api_key = api_key
        # Same host as every other Sarvam adapter (SARVAM_API_BASE), just over wss:// instead of
        # https:// -- one configured base for the whole vendor, not a second URL to keep in sync.
        self._ws_base = api_base.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
        self._model = model
        self._sample_rate = sample_rate

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes], *, language: str = "en"
    ) -> AsyncIterator[TranscriptChunk]:
        if not self._api_key:
            raise ProviderError("sarvam_stt", "SARVAM_API_KEY is not configured.")

        query = urlencode(
            {
                "language_code": _BCP47.get(language, language),
                "model": self._model,
                "stream_type": "balanced",
                "mode": "transcribe",
                "encoding": "linear16",
                "sample_rate": self._sample_rate,
                "endpointing": "vad",
            }
        )

        try:
            async with websockets.connect(
                f"{self._ws_base}/speech-to-text-realtime/ws?{query}",
                additional_headers={"api-subscription-key": self._api_key},
            ) as ws:
                # Feed audio in concurrently with reading transcripts back -- this has to be a
                # background task, not a sequential "send everything, then read everything" loop,
                # or partial transcripts would never reach the caller until the whole call ended,
                # defeating the entire point of streaming (documnets/understanding/
                # 09_LATENCY_AND_PERFORMANCE.md §3).
                send_task = asyncio.create_task(self._send_audio(ws, audio_chunks))
                try:
                    async for raw in ws:
                        event = json.loads(raw)
                        event_type = event.get("event")
                        if event_type in ("transcript.partial", "transcript.final"):
                            is_final = event_type == "transcript.final"
                            yield TranscriptChunk(text=event["text"], is_final=is_final)
                        elif event_type == "error" and event.get("is_fatal"):
                            msg = event.get("message")
                            raise ProviderError("sarvam_stt", f"Sarvam STT fatal error: {msg}")
                        # session.begin / vad.speech_start / vad.speech_end: no action needed.
                finally:
                    send_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await send_task
        except websockets.exceptions.WebSocketException as exc:
            raise ProviderError("sarvam_stt", f"Sarvam STT connection failed: {exc}") from exc

    @staticmethod
    async def _send_audio(ws: websockets.ClientConnection, audio_chunks: AsyncIterator[bytes]) -> None:
        async for chunk in audio_chunks:
            audio_b64 = base64.b64encode(chunk).decode("ascii")
            await ws.send(json.dumps({"event": "audio_input", "audio": audio_b64}))
        # TODO: Sarvam's docs don't document an explicit end-of-audio control message (checked Oct
        # 2026) -- this function returning (closing the implicit send side) and the caller's `async
        # with` block eventually exiting is what currently signals "no more audio" to the server.
        # Revisit if Sarvam adds an explicit `{"event": "audio_end"}`-style message later.
