"""
Sarvam-M adapter -- primary LLM provider, per documnets/understanding/03_TECH_STACK.md §3.
Chosen for Indian-language/Hinglish tone and cost, and because it's also the ingestion-time
chunk-boundary-refinement model (documnets/understanding/07_INGESTION_PIPELINE.md §2 step 2).

TODO: wire up the real Sarvam chat-completion endpoint/payload shape once the technology review
finalizes it -- this stub establishes the interface contract (app.providers.base.LLMProvider) and
streaming shape (httpx streaming request -> yield incremental text) so pipeline code can be built
and tested against a fake/mock implementation of this same interface today.
"""

from collections.abc import AsyncIterator

import httpx

from app.core.exceptions import ProviderError
from app.providers.base import LLMProvider


class SarvamLLMProvider(LLMProvider):
    def __init__(self, api_key: str, api_base: str):
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")

    async def generate_stream(
        self, prompt: str, *, max_tokens: int | None = None, temperature: float = 0.7
    ) -> AsyncIterator[str]:
        if not self._api_key:
            raise ProviderError("sarvam_llm", "SARVAM_API_KEY is not configured.")

        # TODO: replace with the real Sarvam-M chat/completions request + streaming response
        # parsing once confirmed. Shape below is illustrative only.
        async with httpx.AsyncClient(base_url=self._api_base, timeout=30.0) as client:
            async with client.stream(
                "POST",
                "/v1/chat/completions",  # placeholder path
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": "sarvam-m",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                },
            ) as response:
                if response.status_code != 200:
                    raise ProviderError(
                        "sarvam_llm", f"Unexpected status {response.status_code}"
                    )
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    # TODO: parse the real SSE/streaming chunk format -- placeholder pass-through.
                    yield line
