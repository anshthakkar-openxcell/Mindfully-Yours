"""
OpenAI embeddings adapter -- used for BOTH offline ingestion (app/ingestion/embedding.py) and the
runtime embedding-based signal pre-filter (app/pipeline/signal_prefilter.py, Step A of
documnets/understanding/04_CONVERSATION_PIPELINE.md).

WHY OPENAI, NOT SARVAM: the rest of the stack (chat, STT, TTS) uses Sarvam, but Sarvam has no
embeddings product at all -- confirmed directly against their live model list and API reference
(https://docs.sarvam.ai/api/getting-started/models, https://docs.sarvam.ai/api-reference-docs/introduction)
in Sept 2026, not assumed. `text-embedding-3-small` was already the documented fallback/benchmark
embeddings vendor (see documnets/understanding/03_TECH_STACK.md), so this promotes an already-vetted
option to primary rather than introducing a brand-new vendor relationship.

WHY `dimensions=1024`, not the model's native 1536: every Vector column in app/db/models/ was
already created (and migrated) at EMBED_DIM=1024. text-embedding-3-small natively supports
requesting a shorter vector via the `dimensions` parameter (Matryoshka representation learning --
OpenAI's own docs confirm this preserves most of the embedding's quality, unlike naively truncating
a normal embedding yourself), so this avoids a disruptive re-migration of already-created columns
for no real accuracy cost.

Per app.providers.base.EmbeddingProvider's docstring: switching embedding models later is a full
KB re-embed, never a drop-in swap -- don't change OPENAI_EMBEDDING_MODEL or EMBED_DIM in .env
casually, even though both are configurable rather than hardcoded here.

LATENCY, measured live against the real API (2026-09-28): a single-text embed call averaged
~512ms with a fresh connection per call, almost entirely TCP+TLS handshake to api.openai.com, not
OpenAI's own processing time. Fixed by keeping ONE persistent `httpx.AsyncClient` for this
provider's whole process lifetime (it's already a singleton via app.providers.factory's
`@lru_cache`) instead of opening a new connection per call -- re-measured afterward at ~310-390ms
average (real network round-trip + jitter to an external API; not eliminable without self-hosting
the model, see 03_TECH_STACK.md's embeddings discussion for that tradeoff). This matters because
app.safety.interlock calls embed() on EVERY turn, with no exceptions, against
documnets/understanding/09_LATENCY_AND_PERFORMANCE.md's 1.5-2.5s TOTAL turn budget.

FUTURE RISK, not yet a bug (flagging before it becomes one): app.safety.triage.read_turn and
app.pipeline.cache.get_semantic_cache are both still stubs, but once implemented, each will need
to embed the SAME turn's text as the interlock does. If each is left to independently call
embed() on the identical string, that's 2-3 sequential ~300-400ms network round-trips stacked on
one turn instead of one -- easily blowing the whole latency budget by itself. Whoever implements
those should embed the text ONCE in app.pipeline.orchestrator.run_turn and pass the resulting
vector into cache/triage/interlock, not call this method redundantly from each one.
"""

import httpx

from app.core.exceptions import ProviderError
from app.providers.base import EmbeddingProvider

EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str, dimensions: int):
        self._api_key = api_key
        self._model = model  # from OPENAI_EMBEDDING_MODEL -- never hardcode a model name here
        self._dimensions = dimensions  # from EMBED_DIM -- must match every Vector(...) column
        # ONE client, reused for every call -- see module docstring's LATENCY note. Not opened as
        # `async with` per-call anymore; that pattern silently paid a full TCP+TLS handshake on
        # every single embed() call instead of reusing the connection.
        #
        # timeout=3.0, not httpx's old default of 30.0: app.safety.interlock calls embed() on
        # EVERY turn against a 1.5-2.5s TOTAL turn budget (09_LATENCY_AND_PERFORMANCE.md). A 30s
        # timeout means a single slow OpenAI response could silently eat the entire budget before
        # the interlock's own "fail SAFE on timeout" exception handling ever gets a chance to run.
        # 3s is still generous next to the ~300-900ms measured live, but bounds the worst case so
        # the fail-safe path actually triggers promptly instead of hanging.
        self._client = httpx.AsyncClient(timeout=3.0)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self._api_key:
            raise ProviderError("openai_embeddings", "OPENAI_API_KEY is not configured.")
        if not texts:
            return []

        response = await self._client.post(
            EMBEDDINGS_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "input": texts,
                "dimensions": self._dimensions,
                "encoding_format": "float",
            },
        )
        if response.status_code != 200:
            raise ProviderError(
                "openai_embeddings", f"Unexpected status {response.status_code}: {response.text}"
            )
        data = response.json()
        # The API returns `data` items in the same order as the input list, each carrying its
        # own `index` -- sort by index defensively rather than trusting list order blindly.
        items = sorted(data["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in items]

    async def aclose(self) -> None:
        """Call once on app shutdown (see app.main's lifespan) -- not per-request."""
        await self._client.aclose()
