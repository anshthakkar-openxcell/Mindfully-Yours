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
from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text, UniqueConstraint
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


class KBTherapistTurn(Base):
    """
    One real (user message -> therapist-written reply) pair, taken from the therapists' full
    "User: / AI:" dialogue files. THE source for the therapist-first response approach in
    documnets/understanding/32_THERAPIST_FIRST_RESPONSE_APPROACH.md -- at runtime a strong match
    here is served as the therapist wrote it, instead of being generated by the LLM.

    `user_text` is what gets embedded (it is what the live user's single embedded message will be
    compared against -- no extra embedding call at runtime, see doc 32 Gate 1). `prior_context` is
    stored for display/review and context-aware ranking, NOT embedded.

    A row is only ever served at runtime if `approved AND match_eligible`. Both default to the safe
    side: `approved` is False until someone explicitly approves it (ingestion CLI --approve-eligible
    or a therapist review), and `match_eligible` is False for anything the parser could not trust
    (drafting notes, placeholders, crisis/Tier-3 content that the red-flag interlock owns, content
    on governance hold, one-word replies to "yes"/"thanks"). `hold_reason` says why.
    """

    __tablename__ = "kb_therapist_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 = therapist's reply to the opening message
    user_text: Mapped[str] = mapped_column(Text, nullable=False)
    prior_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_text: Mapped[str] = mapped_column(Text, nullable=False)
    scenario: Mapped[str | None] = mapped_column(String, nullable=True)  # conversation title as written
    section: Mapped[str | None] = mapped_column(String, nullable=True)  # topic heading the conversation sits under
    tier: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1|2|3 only when the source states it
    emotion: Mapped[str | None] = mapped_column(String, nullable=True)  # NULL until #23 taxonomy merge -- never guessed
    layer: Mapped[str | None] = mapped_column(String, nullable=True)  # NULL until tagged -- never guessed
    author: Mapped[str | None] = mapped_column(String, nullable=True)  # Anam | Ankita | Shreya | Tanisha | NULL
    source_file: Mapped[str] = mapped_column(String, nullable=False)
    is_opening: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    match_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hold_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # True for the client's curated "Best Conversations" -- a tie-breaker at match time, so when two
    # replies are similarly close the team's own best-of is preferred.
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)  # makes re-ingestion idempotent
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")
    context_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)

    __table_args__ = (CheckConstraint("tier IS NULL OR tier IN (1,2,3)", name="therapist_turn_tier_valid"),)


class KBWelcomeResponse(Base):
    """
    The therapists' opening messages ("Hi user, what's on your mind today?"), from
    `AI WELCOME RESPONSES.docx`. Served as the FIRST message of a conversation exactly as written,
    one picked at random for variety -- no LLM call, so the opening is instant. `user` in the
    source text is the name slot; it is stored as-is and replaced with the person's name (or
    dropped) at serve time. Never embedded -- nothing is searched, it's a pick-one lookup.
    """

    __tablename__ = "kb_welcome_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_file: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")


class KBSituationalRouting(Base):
    """
    One row per everyday situation from `Situational Routing.xlsx` (137 situations in 13 groups):
    what Tier 1 / Tier 2 / Tier 3 looks like FOR THAT SITUATION, plus the therapists' self-care
    strategy. The situation text is embedded so a user's message can be matched to a situation.

    The three tier descriptions are stored but NOT yet wired into routing -- this sheet uses its own
    tier wording and has to be reconciled with the existing Tier logic first (see
    documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #25). The self-care strategies ARE
    live: each is also loaded into kb_content_chunks (content_type='self_care_tool', tier 1), which
    app.pipeline.retrieval.search_self_care_content already searches.
    """

    __tablename__ = "kb_situational_routing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    situation_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)  # 'SID-001'
    category: Mapped[str] = mapped_column(String, nullable=False)
    situation: Mapped[str] = mapped_column(Text, nullable=False)
    tier1_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    tier2_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    tier3_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    self_care_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    situation_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    source_file: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")


class KBTranslation(Base):
    """
    A fixed English reply translated into a user's language, so a Hindi/Hinglish speaker gets it
    instantly (doc 34). Live translation costs 0.7-1.5 s per call -- too slow to do on every turn --
    so every fixed reply (therapist replies, clarifying questions, welcome messages, red-flag scripts)
    is translated ONCE, offline, and looked up here by the hash of its English text. A miss at runtime
    translates live and stores the result here for next time.

    `reviewed` is False for every machine translation. Red-flag crisis scripts in particular should be
    reviewed by a clinician; until then a machine translation is served (a Hindi speaker in crisis is
    better served by a translated script than by an English one).
    """

    __tablename__ = "kb_translations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_hash: Mapped[str] = mapped_column(String, nullable=False)  # sha256 of the normalised English text
    style: Mapped[str] = mapped_column(String, nullable=False)  # 'hi' (Devanagari) | 'hinglish' (Roman)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str | None] = mapped_column(String, nullable=True)  # therapist_reply | red_flag_script | ...
    model: Mapped[str] = mapped_column(String, nullable=False)
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("source_hash", "style", name="uq_kb_translations_hash_style"),
        CheckConstraint("style IN ('hi','hinglish')", name="translation_style_valid"),
    )
