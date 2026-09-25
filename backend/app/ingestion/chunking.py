"""
Chunk-boundary logic, per documnets/understanding/07_INGESTION_PIPELINE.md §4.

For all six real KB sheets received so far, the client's own structure already IS the chunk
boundary -- one row = one chunk, no LLM involved (see app.ingestion.parsers -- each parser already
produces one dict per chunk). This module exists for the ONE case that genuinely needs LLM-based
boundary refinement: Phase III/IV content (clinical guidance, psycho-education, self-care tools),
NOT YET RECEIVED from the client (documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #3),
expected to arrive as flowing prose rather than a pre-segmented table.

Do not apply this module's logic to any of the six existing KB sheets -- see
documnets/understanding/07_INGESTION_PIPELINE.md §5: "Don't let the LLM used for chunk-boundary
refinement rewrite the source text -- it marks split points only."
"""

from app.providers.base import LLMProvider

OVERLAP_RATIO = 0.125  # ~10-15% overlap between neighboring chunks, per 07_INGESTION_PIPELINE.md §2 step 2

_BOUNDARY_INSTRUCTION = (
    "Mark natural sub-boundaries in the following text so each resulting chunk is one complete, "
    "self-contained idea. Do not rewrite or rephrase the text -- only indicate where to split it, "
    "using the marker [[SPLIT]]."
)


async def refine_chunk_boundaries_with_llm(raw_text: str, *, llm: LLMProvider) -> list[str]:
    """
    Sends already-structurally-split-but-still-too-large text to the LLM (Sarvam-M) with ONE
    instruction: mark split points, never rewrite. This is only reached for prose sections that
    are still too large/ambiguous after the free structural pass (headings, numbered steps,
    bullet lists) -- see documnets/understanding/07_INGESTION_PIPELINE.md §2 steps 1-2.

    TODO: implement once Phase III/IV content exists to test this against. The instruction text
    above is fixed per the design doc -- do not let the LLM rewrite source wording, only mark
    [[SPLIT]] boundaries; verify this invariant with a test once real content is available.
    """
    raise NotImplementedError(
        "No Phase III/IV content received yet to chunk -- see "
        "documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #3."
    )
