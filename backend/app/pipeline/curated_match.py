"""
Therapist-first response -- find the therapists' own reply for what the user just said
(documnets/understanding/32_THERAPIST_FIRST_RESPONSE_APPROACH.md, steps 2-3).

LATENCY (Gate 1): this adds NO embedding call -- it takes the turn's already-computed
`query_embedding`. It is ONE indexed pgvector query, and it runs on its OWN database session as a
background task started right after the embedding exists, so it overlaps with triage / tier scoring /
the interlock instead of adding to them (an AsyncSession cannot run two queries at once, hence the
separate session). The orchestrator only waits for it at the point it actually needs the answer.

ACCURACY (Gate 2): only rows with `approved AND match_eligible` are searched (the same predicate as
the partial HNSW index, so the index is used, and held rows -- crisis, governance, placeholders,
too-short -- can never be returned). Bands come from config thresholds that are provisional until
calibrated with a therapist-labelled set; "strong" is deliberately conservative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.kb_convo_content import KBClarificationPhrase, KBTherapistTurn
from app.db.session import AsyncSessionLocal

logger = get_logger(__name__)

Band = Literal["strong", "partial", "none"]
PREFERRED_BONUS = 0.02  # tie-breaker only -- never lifts a poor match over the threshold on its own
MIN_CLARIFY_WORDS = 4  # don't answer "hi" / "hello" with a clarifying question
# Only the GENERIC clarifying questions are safe to use for any message. The bank's other categories
# are situation-specific ("Have you noticed changes in your appetite?", "Who was involved?") and
# would read as a non-sequitur when chosen by nearest-neighbour -- or aren't questions at all
# ("There's no rush."). Confirmed by sampling the real table.
GENERIC_CLARIFY_CATEGORIES = (
    "General Fallback Responses",
    "General Clarification Responses",
    "When AI Needs More Context",
)


@dataclass
class CuratedExample:
    """One close therapist example: what the person said, and the reply the therapist wrote."""

    turn_id: int
    user_text: str
    reply_text: str
    similarity: float


@dataclass
class CuratedMatch:
    turn_id: int
    conversation_id: str
    reply_text: str
    similarity: float
    is_opening: bool
    band: Band
    # The best match first, then other close (>= partial threshold) therapist examples. Only the
    # PARTIAL path uses the extras: they are shown to the LLM so it gets the full picture.
    examples: list[CuratedExample] = field(default_factory=list)


def classify_band(similarity: float, *, is_opening: bool) -> Band:
    """Pure function (easy to test and, later, to calibrate): similarity -> strong / partial / none."""
    s = get_settings()
    strong_cut = s.curated_strong_similarity + (0.0 if is_opening else s.curated_non_opening_margin)
    if similarity >= strong_cut:
        return "strong"
    if similarity >= s.curated_partial_similarity:
        return "partial"
    return "none"


async def find_curated_match(query_embedding: list[float], *, language: str) -> CuratedMatch | None:
    """
    The nearest approved therapist reply, with its band. Returns None when nothing is even a
    partial match. Never raises -- a failure here must not break the turn; the pipeline simply
    falls back to the existing path (logged).
    """
    s = get_settings()
    try:
        distance = KBTherapistTurn.context_embedding.cosine_distance(query_embedding)
        stmt = (
            select(KBTherapistTurn, distance.label("distance"))
            .where(
                # Bare boolean columns, NOT `.is_(True)`: that renders `approved IS true`, which Postgres cannot
                # prove implies the partial HNSW index's `WHERE approved AND match_eligible` predicate, so the
                # index silently went unused (confirmed with EXPLAIN, 2026-10-13). Keep this form.
                KBTherapistTurn.approved,
                KBTherapistTurn.match_eligible,
                KBTherapistTurn.context_embedding.is_not(None),
                KBTherapistTurn.language == language,
            )
            .order_by(distance)
            .limit(s.curated_top_k)
        )
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(stmt)).all()
    except Exception as exc:  # noqa: BLE001 -- never break the turn over this
        logger.error("curated_match_failed", error=str(exc))
        return None

    best: CuratedMatch | None = None
    best_score = -1.0
    close: list[tuple[float, KBTherapistTurn, float]] = []  # (score, turn, similarity), >= partial threshold
    for turn, dist in rows:
        similarity = 1.0 - float(dist)
        score = similarity + (PREFERRED_BONUS if turn.is_preferred else 0.0)
        if similarity >= s.curated_partial_similarity:
            close.append((score, turn, similarity))
        if score > best_score:
            best_score = score
            best = CuratedMatch(
                turn_id=turn.id,
                conversation_id=turn.conversation_id,
                reply_text=turn.reply_text,
                similarity=similarity,
                is_opening=turn.is_opening,
                band=classify_band(similarity, is_opening=turn.is_opening),
            )
    if best is None or best.band == "none":
        return None
    seen_replies: set[str] = set()
    for _, turn, similarity in sorted(close, key=lambda c: c[0], reverse=True):
        key = " ".join(turn.reply_text.lower().split())
        if key in seen_replies:
            continue  # two conversations that end in the same reply add nothing for the LLM
        seen_replies.add(key)
        best.examples.append(CuratedExample(turn.id, turn.user_text, turn.reply_text, similarity))
        if len(best.examples) >= s.curated_max_examples:
            break
    return best


async def find_clarifying_question(query_embedding: list[float]) -> tuple[str, float] | None:
    """The therapists' own "when the AI is not sure" question nearest to what the user said. Used
    when nothing in the library matched -- asking beats guessing (doc 32, Gate 2)."""
    try:
        distance = KBClarificationPhrase.phrase_embedding.cosine_distance(query_embedding)
        stmt = (
            select(KBClarificationPhrase.phrase, distance.label("distance"))
            .where(
                KBClarificationPhrase.phrase_embedding.is_not(None),
                KBClarificationPhrase.category.in_(GENERIC_CLARIFY_CATEGORIES),
                KBClarificationPhrase.phrase.like("%?"),
                KBClarificationPhrase.has_drafting_note.is_(False),
            )
            .order_by(distance)
            .limit(1)
        )
        async with AsyncSessionLocal() as db:
            row = (await db.execute(stmt)).first()
    except Exception as exc:  # noqa: BLE001
        logger.error("clarifying_question_lookup_failed", error=str(exc))
        return None
    return (row.phrase, 1.0 - float(row.distance)) if row else None
