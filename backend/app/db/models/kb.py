"""
Knowledge-base tables -- the AI service's own data, populated by the offline ingestion pipeline
(app/ingestion/). IN SCOPE per documnets/understanding/14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md.

Schema mirrors documnets/understanding/11_DATA_MODEL_AND_STORAGE.md §2-3 exactly, which in turn
is grounded in the real, verified sheet structures documented in
documnets/understanding/05_KNOWLEDGE_BASE_DEEP_DIVE.md. Read both before changing this file --
several columns exist specifically to carry forward a real data-quality issue (e.g. `is_complete`
on RoutingRule for Rule-025, nullable `bot_script` on RedFlag for RF-028-031) rather than to hide it.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.db.base import Base

EMBED_DIM = get_settings().embed_dim


class KBSignal(Base):
    """The Signal Library (from A1, enriched per 06_SIGNAL_ENRICHMENT_PIPELINE.md).
    285 rows in the client's raw data -- see 05_KNOWLEDGE_BASE_DEEP_DIVE.md §2."""

    __tablename__ = "kb_signals"

    signal_id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. 'SIG-002', normalized
    clinical_concept: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    mh_disorder: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    severity: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    red_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tone_cues: Mapped[str | None] = mapped_column(Text, nullable=True)
    trajectory_cues: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")
    phrasings_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    phrasing_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    matched_rules: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (CheckConstraint("severity IN (1,2,3)", name="severity_range"),)


class KBSymptom(Base):
    """Physical/Emotional Symptom Map (from A2). 154 rows: 17 PHYS-, 4 typo'd PHSY-, 133 EM-.
    The EM- rows have NO real signal mapping (free-text category labels instead) -- see
    05_KNOWLEDGE_BASE_DEEP_DIVE.md §3. `linked_signal_ids` is expected empty for those rows;
    that is correct data, not a parsing bug."""

    __tablename__ = "kb_symptoms"

    symptom_id: Mapped[str] = mapped_column(String, primary_key=True)  # 'PHYS-003', 'EM-023'
    id_family: Mapped[str] = mapped_column(String, nullable=False)  # 'PHYS' | 'EM'
    symptom: Mapped[str] = mapped_column(Text, nullable=False)
    how_described: Mapped[str | None] = mapped_column(Text, nullable=True)
    how_described_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBED_DIM), nullable=True
    )
    likely_root: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_signal_ids: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    linked_concepts: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    any_linked_red_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_linked_severity: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    distinguishing_cues: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")

    __table_args__ = (CheckConstraint("id_family IN ('PHYS','EM')", name="id_family_valid"),)


class KBRoutingRule(Base):
    """Routing Rules (from C11) -- a deterministic lookup, NEVER vector-searched.
    66 rules, 1 incomplete (Rule-025 -- no route_to/priority). Evaluation order is `priority`
    (1 -> 2 -> 3), NOT rule_id order -- these genuinely diverge in the real data, confirmed in
    05_KNOWLEDGE_BASE_DEEP_DIVE.md §4. Normalize the RULE-/Rule- casing split on ingest."""

    __tablename__ = "kb_routing_rules"

    rule_id: Mapped[str] = mapped_column(String, primary_key=True)  # normalized casing
    trigger_condition: Mapped[str] = mapped_column(Text, nullable=False)
    route_to: Mapped[str | None] = mapped_column(String, nullable=True)  # NULL for Rule-025
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    trajectory_factor: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)  # 1,2,3, or NULL

    @property
    def is_complete(self) -> bool:
        return self.route_to is not None and self.priority is not None

    __table_args__ = (CheckConstraint("priority IN (1,2,3) OR priority IS NULL", name="priority_range"),)


class KBSufficiencyPattern(Base):
    """Signal Sufficiency (sheet 9) -- deterministic tier thresholds, 12 clinical categories.
    Real row count is contested: 185 (raw CSV) vs 195 (merged workbook) -- see
    documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #18. Two rows have the literal
    placeholder 'check----------' instead of a real tier; `is_placeholder` marks those for
    exclusion until the client resolves them."""

    __tablename__ = "kb_sufficiency_patterns"

    pattern_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    pattern_name: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    is_placeholder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    minimum_signals_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    must_have_signals_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    tie_breaker_logic: Mapped[str | None] = mapped_column(Text, nullable=True)
    probing_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)  # fetched by ID, never searched
    graceful_exit_trigger: Mapped[str | None] = mapped_column(Text, nullable=True)
    pattern_name_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBED_DIM), nullable=True
    )  # the ONE narrow embedding case -- CHUNKING_EMBEDDING_STRATEGY.md §3
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")

    __table_args__ = (CheckConstraint("tier IN (1,2,3) OR tier IS NULL", name="tier_range"),)


class KBRedFlag(Base):
    """Red Flags (sheet 7) -- the safety interlock's own table, checked on EVERY turn.
    31 flags. FOUR (RF-028..031) have NO bot_script -- see
    documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #1, the single most important open
    item in the whole KB. `bot_script IS NULL` must be handled as a hard human-alert path in
    app/safety/interlock.py -- see app.core.exceptions.MissingBotScriptError."""

    __tablename__ = "kb_red_flags"

    flag_id: Mapped[str] = mapped_column(String, primary_key=True)  # 'RF-001'..'RF-031'
    trigger_phrases: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    trigger_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    clinical_meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    immediate_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    bot_script: Mapped[str | None] = mapped_column(Text, nullable=True)  # NULLABLE -- see docstring
    escalation_target: Mapped[str | None] = mapped_column(Text, nullable=True)  # NULL for RF-020
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")


class KBFallbackScenario(Base):
    """Fallback & Safety Net (sheet 17) -- code-evaluated triggers, NOT embedded, per
    CHUNKING_EMBEDDING_STRATEGY.md §5. Real structure is 4 lettered sections (A-D) PLUS a separate
    84-row, 15-group disorder matrix -- confirmed twice (05_KNOWLEDGE_BASE_DEEP_DIVE.md §7,
    08_SAFETY_INTERLOCK_AND_TRIAGE.md §5), not the 3-section structure the earliest design docs
    described. CAUTION: the source data has a real person's name hardcoded into three
    escalation_path rows -- scrub before loading into any environment beyond local dev, see
    documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #13."""

    __tablename__ = "kb_fallback_scenarios"

    scenario_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    section: Mapped[str] = mapped_column(String, nullable=False)
    # 'A_insufficient' | 'B_contradictory' | 'C_disengagement' | 'D_special_population' | 'disorder_matrix'
    disorder_group: Mapped[str | None] = mapped_column(String, nullable=True)  # only for disorder_matrix rows
    scenario_type: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_condition: Mapped[str] = mapped_column(Text, nullable=False)  # evaluated as CODE, never embedded
    fallback_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    bot_script: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    clinical_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")

    __table_args__ = (
        CheckConstraint(
            "section IN ('A_insufficient','B_contradictory','C_disengagement',"
            "'D_special_population','disorder_matrix')",
            name="section_valid",
        ),
    )


class KBContentChunk(Base):
    """Phase III/IV content (clinical guidance, psycho-education, self-care tools) -- NOT YET
    RECEIVED from the client, see documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #3.
    Schema is a placeholder so Epic D's Tier 1 recommendation step (04_CONVERSATION_PIPELINE.md
    Step F) can be built and structurally tested against synthetic fixtures now."""

    __tablename__ = "kb_content_chunks"

    chunk_id: Mapped[str] = mapped_column(String, primary_key=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    pattern_name: Mapped[str | None] = mapped_column(String, nullable=True)
    tier: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    source_document: Mapped[str | None] = mapped_column(String, nullable=True)
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")
    linked_pattern_id: Mapped[int | None] = mapped_column(
        ForeignKey("kb_sufficiency_patterns.pattern_id"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "content_type IN ('probing_guidance','psycho_education','self_care_tool')",
            name="content_type_valid",
        ),
    )


class KBVersion(Base):
    """Ingestion version control -- atomic swap + rollback, per
    documnets/understanding/07_INGESTION_PIPELINE.md §2 step 8. A KB version only becomes queryable
    in the live pipeline once status='live'; see app.core.exceptions.KBVersionNotLiveError."""

    __tablename__ = "kb_versions"

    version_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="building")
    retrieval_hit_rate: Mapped[float | None] = mapped_column(nullable=True)
    grounding_accuracy: Mapped[float | None] = mapped_column(nullable=True)
    tier_routing_accuracy: Mapped[float | None] = mapped_column(nullable=True)
    adversarial_pass_rate: Mapped[float | None] = mapped_column(nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('building','validating','live','rolled_back','failed')",
            name="status_valid",
        ),
    )


class PromptConfig(Base):
    """Static, versioned prompt/persona content (Clinical Markers table, interlock rule-set
    version, etc). Per the architecture PDFs' Prompt & Persona Engineering section: 'Prompt is not
    visible or editable by any user or admin -- same governed process for all.' Application code
    must NEVER expose a write path to this table on any general-purpose API route -- only the
    ingestion/clinical-review tooling should write here. See app/safety/clinical_markers.py for
    the actual verbatim content this table is meant to hold."""

    __tablename__ = "prompt_config"

    config_key: Mapped[str] = mapped_column(String, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    clinical_signoff_by: Mapped[str | None] = mapped_column(String, nullable=True)
    clinical_signoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_live: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
