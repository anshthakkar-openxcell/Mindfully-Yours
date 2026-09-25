"""
Provider-abstraction interfaces. Per documnets/understanding/02_ARCHITECTURE.md §2, this is the
single most load-bearing architectural decision in the system: application code (pipeline,
safety, ingestion) calls ONLY these interfaces, never a vendor SDK directly.

Why this matters beyond clean code:
- It's a CONTRACTUAL requirement -- Clause 2.8 (documnets/understanding/12_SECURITY_COMPLIANCE_DPDP.md
  §2) requires the client's written consent before substituting/materially modifying any model,
  API, or platform. An adapter swap behind this interface is how that stays a config change instead
  of a scattered refactor.
- Every vendor named in documnets/understanding/03_TECH_STACK.md is provisional -- swappable
  pending a pre-launch re-evaluation and a latency re-benchmark, never a drop-in assumption.

Do not add vendor-specific parameters to these interfaces (e.g. a Sarvam-only option) -- if a
capability genuinely can't be expressed generically, that's a sign it belongs in the adapter's
constructor/config, not the interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    """Per documnets/understanding/04_CONVERSATION_PIPELINE.md Step E: the LLM composes phrasing
    only -- it never decides safety or supplies facts not already retrieved. Implementations must
    support streaming; see documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §3 -- never buffer
    a full response before the first token is available to the caller."""

    @abstractmethod
    async def generate_stream(
        self, prompt: str, *, max_tokens: int | None = None, temperature: float = 0.7
    ) -> AsyncIterator[str]:
        """Yield response text incrementally (token/chunk at a time)."""
        raise NotImplementedError
        yield  # pragma: no cover -- makes this an async generator for type checkers


class STTProvider(ABC):
    """Per documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §3: process partial transcripts
    as they arrive, don't wait for a full utterance where safely avoidable."""

    @abstractmethod
    async def transcribe_stream(
        self, audio_chunks: AsyncIterator[bytes], *, language: str = "en"
    ) -> AsyncIterator[str]:
        """Yield partial/final transcript text as audio is consumed."""
        raise NotImplementedError
        yield  # pragma: no cover


class TTSProvider(ABC):
    """Per documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §3: synthesize from the first
    completed sentence, not the full LLM response -- callers should feed this sentence-by-sentence,
    not wait for the entire reply."""

    @abstractmethod
    async def synthesize_stream(self, text: str, *, language: str = "en") -> AsyncIterator[bytes]:
        """Yield audio bytes incrementally for the given text."""
        raise NotImplementedError
        yield  # pragma: no cover


class EmbeddingProvider(ABC):
    """Per documnets/understanding/07_INGESTION_PIPELINE.md §3: switching embedding models is a
    full KB re-embed + re-validation, never a drop-in swap -- treat this interface's implementation
    choice as a decision with real migration cost, not a config toggle to flip casually."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Batch-embed texts. Batch, don't call once per text -- see
        documnets/understanding/07_INGESTION_PIPELINE.md §2 step 4 (free efficiency offline)."""
        raise NotImplementedError


class AvatarProvider(ABC):
    """Vendor for this interface is UNRESOLVED -- three different answers across the source
    material (Spatius.ai / HeyGen / Rive-Live2D 2-D). See
    documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #8. Avatar is opt-in and cost-gated
    by design (documnets/understanding/03_TECH_STACK.md) -- never call this unconditionally."""

    @abstractmethod
    async def render_stream(self, audio_chunks: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        """Yield lip-synced video frames/chunks as audio is consumed."""
        raise NotImplementedError
        yield  # pragma: no cover
