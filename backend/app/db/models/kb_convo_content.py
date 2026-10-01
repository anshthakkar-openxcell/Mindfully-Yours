"""
Tables for the Sept 2026 "convo data" drop (documnets/knowledgebase/convo data/) -- the Layer I-IV
question banks, the emotion phrase banks, the scenario taxonomy, the clarification bank, the career
lookup, and the parenting guardrail rules. See
documnets/understanding/21_NEW_CONTENT_INGESTION_PLAN.md for the full per-file reasoning and
documnets/understanding/19_DATA_USAGE_MAP.md for which bucket each table belongs to.

Self-help tools (the DBT workbook, brain-dump worksheet) deliberately do NOT get a new table here
-- they're loaded into the existing `KBContentChunk` table (app/db/models/kb.py), which was already
designed for exactly this purpose (`content_type='self_care_tool'`) and is already wired into
app.pipeline.retrieval.search_self_care_content(). Adding a parallel table would duplicate that
mechanism for no reason.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.db.base import Base

EMBED_DIM = get_settings().embed_dim


class KBEmotionPhrase(Base):
    """
    Real first-person emotion phrasing, from THREE separate, unreconciled sources -- see
    documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #23. `source_list` is preserved so
    the eventual merge is a reviewed, auditable step, not a silent overwrite.
    `canonical_emotion_group` stays NULL until that merge happens -- do not populate it as a guess.
    """

    __tablename__ = "kb_emotion_phrases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    emotion_label: Mapped[str] = mapped_column(String, nullable=False)
    phrase: Mapped[str] = mapped_column(Text, nullable=False)
    source_list: Mapped[str] = mapped_column(String, nullable=False)
    # 'phase_ii_emotion_expression' (19 labels) | 'list_of_emotions_tanisha' (9 labels) |
    # 'layer_ii' | 'layer_iii' (both confirmed to share the same 28-label list)
    canonical_emotion_group: Mapped[str | None] = mapped_column(String, nullable=True)
    phrase_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    source_file: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")


class KBLayerContent(Base):
    """
    The Layer I-IV conversational-depth question/statement banks -- an axis separate from Tier
    1/2/3 severity. See documnets/understanding/18_NEW_CONVO_DATA_CATALOG.md §1.
    """

    __tablename__ = "kb_layer_content"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    layer: Mapped[str] = mapped_column(String, nullable=False)
    # 'I' | 'II' | 'III' | 'IV' | 'II-III' -- the last is `Layer 2 to 3 Transitions.docx`, a real
    # bridging file (confirmed by running ingestion against it -- app.ingestion.parsers.layer_content
    # deliberately tags its rows this way; this is not a typo to normalize away).
    section: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. 'Values', 'Safety Check'
    section_type: Mapped[str] = mapped_column(String, nullable=False)
    # 'generic' | 'emotion_specific' | 'transition'
    emotion_label: Mapped[str | None] = mapped_column(String, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    source_file: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")

    __table_args__ = (
        CheckConstraint("layer IN ('I','II','III','IV','II-III')", name="layer_valid"),
        CheckConstraint("section_type IN ('generic','emotion_specific','transition')", name="section_type_valid"),
    )


class KBScenario(Base):
    """
    From `List of Scenarios - Tanisha.docx`. `pending_governance_review=True` marks rows from the
    "Fetishes" category -- see documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #26.
    **Application code must exclude rows where this is True from any live retrieval index until
    the clinical + legal governance decision is made** -- they are stored, not silently dropped,
    specifically so nothing here requires re-ingesting the whole file once that decision lands.
    """

    __tablename__ = "kb_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    scenario_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    phrase: Mapped[str] = mapped_column(Text, nullable=False)
    pending_governance_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    phrase_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    source_file: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")


class KBAnxietySituation(Base):
    """From `Anxiety Situations.docx` -- a coarse, 35-row situation taxonomy (not phrase-level
    like KBScenario), used as a category-coverage index rather than a fine-grained match target."""

    __tablename__ = "kb_anxiety_situations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broad_situation: Mapped[str] = mapped_column(String, nullable=False)
    subtopics_raw: Mapped[str] = mapped_column(Text, nullable=False)
    source_file: Mapped[str] = mapped_column(String, nullable=False)


class KBClarificationPhrase(Base):
    """From `Questions For When AI Is Not Sure - Tanisha.docx` -- a cross-cutting NLU fallback
    bank, usable at any Layer/Tier. `has_drafting_note=True` flags rows with a literal
    parenthetical note left in the source text (e.g. "(could be followed up with some options)")
    that should be cleaned by the clinical team before this ships, not silently stripped here."""

    __tablename__ = "kb_clarification_phrases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    phrase: Mapped[str] = mapped_column(Text, nullable=False)
    has_drafting_note: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    phrase_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    source_file: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")


class KBCareerLookup(Base):
    """From `Career Field & Stream Lookup.csv` -- the deduplicated data extracted from
    `Career Conversation Sets 1.docx`'s 500x-repeated template. An exact/fuzzy lookup, not a
    fuzzy-only semantic target -- `career_name_embedding` exists to help match a user's own
    phrasing of a career name, but `career_name` itself should be tried as an exact/fuzzy string
    match first, since these are precise, known values."""

    __tablename__ = "kb_career_lookup"

    entry_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    career_name: Mapped[str] = mapped_column(String, nullable=False)
    field_category: Mapped[str] = mapped_column(String, nullable=False)
    likely_academic_stream: Mapped[str] = mapped_column(String, nullable=False)
    career_name_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)


class KBTierQuestionBank(Base):
    """
    From `Questions.docx` (9 life-situation scenarios, confirmed only 6 fully parsed -- see
    app.ingestion.parsers.tier_question_banks docstring) and `Question Set - Career.docx` (career
    topics). The single richest source for calibrating Tier 1/2/3 against real scenarios -- see
    documnets/understanding/18_NEW_CONVO_DATA_CATALOG.md §4a.
    """

    __tablename__ = "kb_tier_question_bank"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bank_source: Mapped[str] = mapped_column(String, nullable=False)  # 'questions_by_scenario' | 'career_question_set'
    scenario_or_topic: Mapped[str] = mapped_column(String, nullable=False)
    subsection: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. 'Tier 3 Questions (...)'; NULL for career set
    question_type: Mapped[str] = mapped_column(String, nullable=False)  # 'open' | 'close_ended'
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_options_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    tier_routing: Mapped[str | None] = mapped_column(String, nullable=True)
    # Confirmed always NULL today for the career set (column exists, every row is blank in the
    # source) -- kept distinct from "column doesn't apply" to make that gap visible, not hidden.
    question_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    source_file: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")

    __table_args__ = (
        CheckConstraint("bank_source IN ('questions_by_scenario','career_question_set')", name="bank_source_valid"),
        CheckConstraint("question_type IN ('open','close_ended')", name="question_type_valid"),
    )


class KBGuardrailRule(Base):
    """From `Parenting_Child Related.docx`'s Guardrail table -- Bucket 3 content, a pure
    deterministic lookup. NEVER embedded, NEVER searched -- `referral_urgency` is checked directly
    in code (e.g. `if urgency == 'Immediate/emergency': ...`), the same way
    app.safety.routing checks kb_routing_rules."""

    __tablename__ = "kb_guardrail_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    concern_category: Mapped[str] = mapped_column(String, nullable=False)
    referral_urgency: Mapped[str] = mapped_column(String, nullable=False)  # 'Yes' | 'Immediate' | 'Immediate/emergency'
    source_file: Mapped[str] = mapped_column(String, nullable=False)
