"""
Two-tier cache -- the single biggest cost/latency lever in the system, per
documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §6 and pipeline steps 3-4 in
documnets/understanding/04_CONVERSATION_PIPELINE.md.

RULE THAT MUST NEVER BE VIOLATED: a cache hit still runs triage + interlock. This module only
ever short-circuits RETRIEVAL AND GENERATION -- see app.pipeline.orchestrator, which is the only
place allowed to decide what happens after a cache hit. Do not let a cache hit skip
app.safety.interlock.check_interlock under any circumstance, including here.

Cache keys are language-scoped: an English entry and a Hindi entry for the same underlying answer
are different entries, never the same one with a translation layer bolted on --
documnets/understanding/13_LANGUAGE_PHASING.md.
"""

from __future__ import annotations

import hashlib

import orjson
from redis.asyncio import Redis

EXACT_CACHE_PREFIX = "cache:exact"


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _exact_key(text: str, language: str) -> str:
    digest = hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()
    return f"{EXACT_CACHE_PREFIX}:{language}:{digest}"


async def get_exact_cache(text: str, *, language: str, redis: Redis) -> str | None:
    """Tier 1: exact-match/FAQ cache -- near-zero latency, checked first."""
    raw = await redis.get(_exact_key(text, language))
    if raw is None:
        return None
    return orjson.loads(raw)["response"]


async def set_exact_cache(text: str, response: str, *, language: str, redis: Redis, ttl_seconds: int = 86400) -> None:
    await redis.set(
        _exact_key(text, language), orjson.dumps({"response": response}), ex=ttl_seconds
    )


async def get_semantic_cache(
    text: str, *, language: str, embedding_provider, db, similarity_threshold: float = 0.95
) -> str | None:
    """
    Tier 2: semantic cache -- catches near-duplicate turns, skips the LLM call.

    TODO: implement as a pgvector similarity search over a dedicated `semantic_cache_entries`
    table (embedding + response + language + expiry), analogous to app.safety.interlock's query
    shape. Not modeled in app.db.models yet -- add it alongside this implementation, scoped by
    language per documnets/understanding/13_LANGUAGE_PHASING.md, and keep the index tight
    (single-digit-ms budget per documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §6).
    """
    return None
