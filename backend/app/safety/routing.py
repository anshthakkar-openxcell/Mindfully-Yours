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

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.kb import KBRoutingRule


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

    TODO: this currently only supports rules whose trigger_condition was pre-resolved into an
    explicit signal-id set at ingestion time (see app.ingestion.enrichment -- only 25/285 signals
    are auto-matched today per documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #4). Rules
    with unresolved range/combination trigger_conditions cannot be evaluated by this function yet
    and must be excluded, not guessed at.
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
    TODO: real implementation depends on app.ingestion.enrichment resolving rule.trigger_condition
    into a structured signal-id requirement at ingestion time (matched_rules on KBSignal, or a
    dedicated resolved-condition column on KBRoutingRule -- not yet modeled, see
    documnets/understanding/06_SIGNAL_ENRICHMENT_PIPELINE.md for the parsing approach and its
    known limitations). Placeholder always returns False so this never silently mis-routes before
    that resolution logic exists.
    """
    return False
