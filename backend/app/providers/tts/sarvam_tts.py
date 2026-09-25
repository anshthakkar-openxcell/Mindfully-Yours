"""
Sarvam TTS (Bulbul) adapter -- primary voice provider, per documnets/understanding/03_TECH_STACK.md §3.

TODO: wire up the real Sarvam TTS streaming endpoint. This stub establishes the interface contract
(app.providers.base.TTSProvider) -- per documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §3,
callers must feed this sentence-by-sentence as the LLM streams out, not the full response at once.
"""

from collections.abc import AsyncIterator

from app.core.exceptions import ProviderError
from app.providers.base import TTSProvider


class SarvamTTSProvider(TTSProvider):
    def __init__(self, api_key: str, api_base: str):
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")

    async def synthesize_stream(self, text: str, *, language: str = "en") -> AsyncIterator[bytes]:
        if not self._api_key:
            raise ProviderError("sarvam_tts", "SARVAM_API_KEY is not configured.")
        # TODO: call the real Sarvam TTS (Bulbul) streaming synthesis endpoint.
        raise NotImplementedError("Sarvam TTS integration not yet implemented.")
        yield  # pragma: no cover
