"""
Deepgram adapter -- primary STT provider.

NOTE: documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #9 -- whether STT is Deepgram-only
or a dual Deepgram/Sarvam setup is UNRESOLVED across the three architecture PDFs. This adapter
implements Deepgram; if a dual-vendor design is confirmed, add a second adapter and a routing
strategy at the factory level (app/providers/factory.py), don't special-case it inside pipeline code.

TODO: wire up Deepgram's real streaming WebSocket API -- this stub establishes the interface
contract (app.providers.base.STTProvider) only.
"""

from collections.abc import AsyncIterator

from app.core.exceptions import ProviderError
from app.providers.base import STTProvider


class DeepgramSTTProvider(STTProvider):
    def __init__(self, api_key: str):
        self._api_key = api_key

    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes], *, language: str = "en"
    ) -> AsyncIterator[str]:
        if not self._api_key:
            raise ProviderError("deepgram_stt", "DEEPGRAM_API_KEY is not configured.")
        # TODO: open a Deepgram streaming websocket, feed audio_chunks in, yield partial/final
        # transcripts out as they arrive -- per documnets/understanding/09_LATENCY_AND_PERFORMANCE.md
        # §3, do not buffer the full utterance before yielding.
        raise NotImplementedError("Deepgram streaming integration not yet implemented.")
        yield  # pragma: no cover
