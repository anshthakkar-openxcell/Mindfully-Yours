"""
Integration test placeholder for the full app.pipeline.orchestrator.run_turn flow.

TODO: requires a running Postgres+pgvector and Redis (or testcontainers), plus fake/mock
LLMProvider and EmbeddingProvider implementations (do NOT hit real vendor APIs in tests -- see
documnets/understanding/12_SECURITY_COMPLIANCE_DPDP.md §8, synthetic data and no real vendor spend
in test environments). Seed a synthetic KBRedFlag row and assert that a matching input routes to
its verbatim bot_script, never an LLM-generated response -- that is the single most important
behavior in this codebase to have an automated regression test for.
"""

import pytest


@pytest.mark.skip(reason="Requires a test DB/Redis + fake providers -- not wired up yet.")
async def test_red_flag_match_returns_verbatim_script_not_llm_generation():
    ...


@pytest.mark.skip(reason="Requires a test DB/Redis + fake providers -- not wired up yet.")
async def test_cache_hit_still_runs_interlock():
    """The single most important invariant in the pipeline: a cache hit must never skip the
    safety interlock. See documnets/understanding/04_CONVERSATION_PIPELINE.md."""
    ...
