"""
FastAPI dependency providers -- DB session, Redis client, and provider-adapter instances. Keeping
these as dependencies (rather than module-level globals imported directly into endpoints) is what
makes endpoint handlers trivially testable with overrides (see tests/conftest.py).
"""

from collections.abc import AsyncGenerator

from redis.asyncio import Redis, from_url

from app.core.config import get_settings
from app.db.session import get_db  # re-exported for convenience: `Depends(get_db)`
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.factory import get_embedding_provider, get_llm_provider

__all__ = ["get_db", "get_redis", "get_llm", "get_embeddings"]

_redis_client: Redis | None = None


async def get_redis() -> AsyncGenerator[Redis, None]:
    global _redis_client
    if _redis_client is None:
        _redis_client = from_url(get_settings().redis_url, decode_responses=False)
    yield _redis_client


def get_llm() -> LLMProvider:
    return get_llm_provider()


def get_embeddings() -> EmbeddingProvider:
    return get_embedding_provider()
