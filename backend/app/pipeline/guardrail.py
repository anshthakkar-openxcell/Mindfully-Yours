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
