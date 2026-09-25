"""
Fallback/benchmark LLM adapter (GPT-4o-mini / Claude Haiku class) -- per
documnets/understanding/03_TECH_STACK.md §3, this is a comparison point from the technology
review, NOT the default. Only wire this in as an actual runtime fallback if/when the client
approves it per Clause 2.8 (documnets/understanding/12_SECURITY_COMPLIANCE_DPDP.md §2) -- and
confirm a no-training/no-retention tier before any real conversation data reaches it (§1).

TODO: implement once a specific fallback vendor + no-training tier is confirmed. Left unimplemented
deliberately -- do not wire this into app.pipeline until that confirmation happens.
"""

from collections.abc import AsyncIterator

from app.providers.base import LLMProvider


class FallbackLLMProvider(LLMProvider):
    async def generate_stream(
        self, prompt: str, *, max_tokens: int | None = None, temperature: float = 0.7
    ) -> AsyncIterator[str]:
        raise NotImplementedError(
            "Fallback LLM provider is not yet approved/configured -- see "
            "documnets/understanding/12_SECURITY_COMPLIANCE_DPDP.md §1-2 before implementing."
        )
        yield  # pragma: no cover
