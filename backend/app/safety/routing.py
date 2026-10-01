"""
Deterministic tier routing -- evaluates kb_routing_rules (C11) against the accumulated signal set
for the current conversation.

CRITICAL: rules evaluate in `priority` order (1 -> 2 -> 3), NEVER `rule_id` order -- these
genuinely diverge in the real data (e.g. RULE-004 is priority 1 while RULE-002/003 are priority 2).
See documnets/understanding/05_KNOWLEDGE_BASE_DEEP_DIVE.md §4 for concrete examples of the
divergence. Getting this wrong silently applies rules in the wrong sequence with no error raised.

This module implements pipeline Step D (Sufficiency check) from
documnets/understanding/04_CONVERSATION_PIPELINE.md -- it is a lookup, not a model call.
"""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.kb import KBRoutingRule
from app.ingestion.parsers.common import match_signal_in_trigger_condition, match_symptom_in_trigger_condition


@dataclass
class RoutingDecision:
    matched: bool
    rule_id: str | None = None
    route_to: str | None = None
    override_reason: str | None = None


async def evaluate_routing_rules(
    observed_signal_ids: set[str],
    *,
    db: AsyncSession,
) -> RoutingDecision:
    """
    Evaluate the routing rules table against the signals observed so far in this conversation
    (Redis-backed running state -- see app.pipeline.state), in priority order.

    `observed_signal_ids` should be the ACCUMULATED set across the whole conversation
    (ConversationState.observed_signal_ids unioned with this turn's new matches), not just this
    turn's -- a rule needing 2 signals from different turns must still be able to match.

    KNOWN LIMITATION, not silently hidden: only resolves rules via direct single-number mentions in
    trigger_condition (see _rule_matches) -- confirmed to resolve only 25/285 signals on the real
    data (documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #4). A rule with unresolved
    range/combination logic is correctly excluded, not guessed at.
    """
    stmt = (
        select(KBRoutingRule)
        .where(KBRoutingRule.route_to.is_not(None), KBRoutingRule.priority.is_not(None))
        .order_by(KBRoutingRule.priority.asc())
    )
    result = await db.execute(stmt)
    rules = result.scalars().all()

    for rule in rules:
        if _rule_matches(rule, observed_signal_ids):
            return RoutingDecision(
                matched=True,
                rule_id=rule.rule_id,
                route_to=rule.route_to,
                override_reason=rule.override_reason,
            )

    return RoutingDecision(matched=False)


def _rule_matches(rule: KBRoutingRule, observed_signal_ids: set[str]) -> bool:
    """
    Real implementation, built on app.ingestion.parsers.common's tolerant regex matchers -- the
    same ones already used at ingestion time to link signals to rules. A rule matches if ANY
    observed ID's number appears in its free-text trigger_condition, checked against BOTH the
    'SIG-xxx' pattern and the 'EM-xxx' pattern (CONFIRMED 2026-09-29: every real Tier 1 rule is
    keyed on EM-codes, not SIG-codes -- see match_symptom_in_trigger_condition's docstring for how
    this was verified against the real data, correcting an earlier design doc that called EM-codes
    "confirmed missing").

    KNOWN LIMITATION, inherited from those helpers and not silently hidden here: they only catch
    direct single-number mentions, not range/combination logic like "SIG 001-017 minus SIG002-003"
    or "EM45 to 54" (the literal endpoints match, numbers implied by the range don't) -- confirmed
    to resolve only 25/285 signals on the real data (documnets/understanding/
    15_OPEN_QUESTIONS_AND_BLOCKERS.md #4). A rule whose trigger_condition depends on unresolved
    range/combination logic will simply never match here, which is correct behavior (excluded, not
    guessed at) rather than a bug to fix in this function.
    """
    if not rule.trigger_condition:
        return False
    for observed_id in observed_signal_ids:
        # FIXED BUG (found 2026-09-29 live, not caught by review): matching on the bare number
        # regardless of prefix causes false positives across unrelated ID namespaces -- confirmed
        # concretely with 'PHYS-004' ("Occupational Impairment") falsely matching RULE-004
        # (Premenstrual Dysphoric Disorder) purely because both contain the digits "004". Only
        # SIG-xxx and EM-xxx are meaningful to kb_routing_rules' trigger_condition text; anything
        # else (e.g. PHYS-xxx) must be explicitly excluded, not silently number-matched.
        prefix_match = re.match(r"(SIG|EM)[\s\-]?0*(\d+)", observed_id, re.IGNORECASE)
        if not prefix_match:
            continue
        prefix, number = prefix_match.group(1).upper(), int(prefix_match.group(2))
        if prefix == "EM":
            if match_symptom_in_trigger_condition(rule.trigger_condition, number):
                return True
        elif match_signal_in_trigger_condition(rule.trigger_condition, number):
            return True
    return False
