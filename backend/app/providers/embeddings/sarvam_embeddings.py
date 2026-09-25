"""
Sarvam embeddings adapter -- used for BOTH offline ingestion (app/ingestion/embedding.py) and the
runtime embedding-based signal pre-filter (app/pipeline/signal_prefilter.py, Step A of
documnets/understanding/04_CONVERSATION_PIPELINE.md).

Chosen even though Phase 1 is English-only, specifically so Phase 2's Hindi content can share the
same vector space without a re-embed -- see documnets/understanding/07_INGESTION_PIPELINE.md §3.
Do NOT swap this provider without accounting for a full KB re-embed + re-validation.

TODO: wire up the real Sarvam embeddings endpoint (batched -- see docstring on
app.providers.base.EmbeddingProvider.embed).
"""

import httpx

from app.core.exceptions import ProviderError
from app.providers.base import EmbeddingProvider


class SarvamEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, api_base: str):
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self._api_key:
            raise ProviderError("sarvam_embeddings", "SARVAM_API_KEY is not configured.")
        if not texts:
            return []

        # TODO: replace with the real Sarvam embeddings request/response shape once confirmed.
        async with httpx.AsyncClient(base_url=self._api_base, timeout=30.0) as client:
            response = await client.post(
                "/v1/embeddings",  # placeholder path
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": "sarvam-embed", "input": texts},
            )
            if response.status_code != 200:
                raise ProviderError(
                    "sarvam_embeddings", f"Unexpected status {response.status_code}"
                )
            data = response.json()
            # TODO: adjust once the real response schema is confirmed.
            return [item["embedding"] for item in data.get("data", [])]
