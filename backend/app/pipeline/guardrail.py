"""
Output guardrail -- pipeline step 11 of documnets/understanding/04_CONVERSATION_PIPELINE.md.

Verifies the LLM's response is actually supported by what was retrieved (grounding), not just
plausible-sounding -- per documnets/understanding/07_INGESTION_PIPELINE.md §3, "a good LLM response
can be generated from the wrong chunk and still sound convincing." This check exists specifically
to catch that failure mode before it reaches a user.

This is NOT the safety interlock -- the interlock (app.safety.interlock) has already run earlier
in the pipeline and independently of this. This module only checks grounding + protocol adherence
of an already-approved (non-red-flag, non-fallback) response.
"""

import re
from dataclasses import dataclass


@dataclass
class GuardrailResult:
    passed: bool
    reason: str | None = None


def check_grounding(response_text: str, *, retrieved_context: str | None) -> GuardrailResult:
    """
    TODO: real implementation should check that claims in `response_text` are traceable to
    `retrieved_context` -- e.g. via an NLI/entailment model, or a second lightweight LLM check
    (per documnets/understanding/LATENCY.md §7, keep any extra check either parallelizable or
    async, never a second heavyweight blocking call added to the critical path without checking
    that first). Placeholder below only checks the trivial "no grounding material and a
    substantive response" case, which should never be treated as grounded.
    """
    if not retrieved_context and len(response_text.strip()) > 0:
        return GuardrailResult(
            passed=False,
            reason="No retrieved context was available to ground this response.",
        )
    return GuardrailResult(passed=True)


_WORD = re.compile(r"[a-z0-9']+")
_NUMBER_OR_URL = re.compile(r"\d|https?://|www\.", re.IGNORECASE)
_STOPWORDS = frozenset(
    "a an the and or but if so to of in on at for with about as is are was were be been it its this that "
    "these those i you your yours me my we our they them he she his her do does did have has had can could "
    "would should will just very really also not no yes".split()
)


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS and len(w) > 2}


def check_rephrase_faithful(
    rephrased: str,
    *,
    original: str,
    min_overlap: float = 0.6,
    max_length_ratio: float = 1.6,
    check_overlap: bool = True,
) -> GuardrailResult:
    """
    Enforcing check for the PARTIAL-match path (doc 32, Gate 2): the LLM may only reword the
    therapist's reply, never add to it. Deliberately simple and instant (no second model call, so it
    adds no latency): the rewording must (1) reuse most of the therapist's own content words,
    (2) not introduce numbers or links the therapist didn't write, (3) not balloon in length.
    If any check fails the caller serves the therapist's original text instead -- a failed rewording
    is never shown. This catches drift and padding; it is a guard, not a proof of equivalence.
    """
    if not rephrased.strip():
        return GuardrailResult(False, "Empty rephrasing.")
    if _NUMBER_OR_URL.search(rephrased) and not _NUMBER_OR_URL.search(original):
        return GuardrailResult(False, "Rephrasing introduced numbers or links not in the therapist's reply.")
    if len(rephrased) > max_length_ratio * max(len(original), 40):
        return GuardrailResult(False, "Rephrasing is much longer than the therapist's reply.")
    if not check_overlap:
        # Different language from the original (Hindi/Hinglish reply vs English therapist text): word overlap
        # is meaningless, and the length ratio above is too (scripts differ), so only the empty/number/link
        # checks apply. A deliberately weaker guarantee -- recorded in doc 34.
        return GuardrailResult(True)
    original_words = _content_words(original)
    new_words = _content_words(rephrased)
    if new_words and original_words:
        overlap = len(new_words & original_words) / len(new_words)
        if overlap < min_overlap:
            return GuardrailResult(False, f"Rephrasing drifted from the therapist's wording (overlap {overlap:.2f}).")
    return GuardrailResult(True)
