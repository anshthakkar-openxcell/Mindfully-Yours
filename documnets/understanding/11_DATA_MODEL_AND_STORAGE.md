# 11 — Proposed Data Model (PostgreSQL + pgvector + Redis)

> **This is a proposed concrete schema, synthesized from every architectural constraint documented elsewhere in this folder — it is not something the client handed over directly.** Treat table/column names as a sensible starting point to accelerate implementation, not as a client-mandated spec. Validate against actual application needs before finalizing migrations. Every design choice below traces back to a specific rule in [01](01_PROJECT_OVERVIEW.md)-[10](10_LIVEKIT_REALTIME.md); the citation after each table says which.
>
> **Scope note**: per [14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md](14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md), this build covers the Python/FastAPI AI service only. §2-3 and §5-6 below (`kb_*`, `kb_versions`, `sessions`'s running-state fields, `turn_audit_log`, Redis cache) are **in scope — this is the AI service's own database.** §4 (`users`, `consents`) and §7 (`practitioners`, `bookings`, `call_recordings`) are **out of scope** — they belong to the NestJS backend's database and are included here only so the AI service's `user_id`/`session_id` foreign-key references make sense and the API contract (see [14](14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md) §4) is unambiguous. Do not build §4/§7 as part of this effort.

## 1. Design constraints this schema must satisfy (recap)

- Single data spine: Postgres + pgvector, not two separate databases ([02_ARCHITECTURE.md](02_ARCHITECTURE.md) §1).
- Every chunk and every logged row carries a `language` field, `en` in Phase 1 ([13_LANGUAGE_PHASING.md](13_LANGUAGE_PHASING.md)).
- Every chunk carries a `user_id` tag for isolation where relevant — one user's logged history must never leak into another's retrieval context ([04](04_CONVERSATION_PIPELINE.md), `CLAUDE.md` §6).
- Field-level encryption for clinical content ([12_SECURITY_COMPLIANCE_DPDP.md](12_SECURITY_COMPLIANCE_DPDP.md) §12).
- Retention timers independent per data type ([12_SECURITY_COMPLIANCE_DPDP.md](12_SECURITY_COMPLIANCE_DPDP.md) §12).
- Audit logs retained ≥3 years ([12_SECURITY_COMPLIANCE_DPDP.md](12_SECURITY_COMPLIANCE_DPDP.md) §4).
- Three distinct retrieval mechanisms need three distinct storage shapes: deterministic lookup tables, direct ID-linked guidance chunks, and genuinely embedded/searched content ([04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md) §3).
- Session lifecycle is a 4-state machine: Live → Closed → Tiered → Shared (per the architecture PDFs' Storage section).

## 2. Knowledge base tables **[IN SCOPE]** (populated by the offline ingestion pipeline — [07](07_INGESTION_PIPELINE.md), [06](06_SIGNAL_ENRICHMENT_PIPELINE.md))

```sql
-- The Signal Library (from A1, enriched per 06_SIGNAL_ENRICHMENT_PIPELINE.md)
CREATE TABLE kb_signals (
    signal_id           TEXT PRIMARY KEY,        -- e.g. 'SIG-002', normalized (zero-padded, uppercase)
    clinical_concept    TEXT NOT NULL,
    category            TEXT,                    -- normalized (see data-quality notes, 05_KNOWLEDGE_BASE_DEEP_DIVE §2)
    mh_disorder         TEXT[],                   -- array; source rows are newline-joined multi-value
    severity            SMALLINT CHECK (severity IN (1,2,3)),
    red_flag            BOOLEAN NOT NULL DEFAULT false,  -- normalized from Yes/yes/No/no/blank
    tone_cues           TEXT,
    trajectory_cues     TEXT,
    language            TEXT NOT NULL DEFAULT 'en',
    phrasings_text      TEXT,                     -- raw concatenated phrasings, kept for reference
    phrasing_embedding  vector(EMBED_DIM),         -- Sarvam embedding of `phrasings_text` -- THE searchable field
    matched_rules       JSONB,                     -- e.g. [{"rule_id":"RULE-001","priority":1,"route_to":"Tier 3"}]
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON kb_signals USING ivfflat (phrasing_embedding vector_cosine_ops);
CREATE INDEX ON kb_signals (category, language);   -- pre-filter before vector search, per INGESTION.md §3

-- The Physical/Emotional Symptom Map (from A2)
CREATE TABLE kb_symptoms (
    symptom_id              TEXT PRIMARY KEY,     -- 'PHYS-003', 'EM-023', normalized prefix (fix PHSY typo)
    id_family               TEXT NOT NULL,        -- 'PHYS' | 'EM' -- see 05_KNOWLEDGE_BASE_DEEP_DIVE §3: these are semantically different
    symptom                 TEXT NOT NULL,
    how_described            TEXT,
    how_described_embedding vector(EMBED_DIM),     -- only meaningful for PHYS/PHSY rows with real language content
    likely_root              TEXT,
    linked_signal_ids        TEXT[],               -- resolved via the parser in 06_SIGNAL_ENRICHMENT_PIPELINE §3; EMPTY for EM- rows (expected, not an error)
    linked_concepts           TEXT[],
    any_linked_red_flag       BOOLEAN DEFAULT false,
    max_linked_severity       SMALLINT,
    distinguishing_cues       TEXT,
    language                  TEXT NOT NULL DEFAULT 'en'
);

-- Routing Rules (from C11) -- a deterministic lookup table, NEVER vector-searched
CREATE TABLE kb_routing_rules (
    rule_id            TEXT PRIMARY KEY,         -- normalize 'RULE-XXX'/'Rule-XXX' casing on ingest
    trigger_condition  TEXT NOT NULL,             -- raw free text; parsed range/combination logic lives in application code, not here
    route_to           TEXT,                      -- nullable -- Rule-025 has none, see 05_KNOWLEDGE_BASE_DEEP_DIVE §4
    override_reason    TEXT,
    trajectory_factor  TEXT,
    priority           SMALLINT,                  -- 1, 2, 3, or NULL (Rule-025) -- THIS, not rule_id, is evaluation order
    is_complete        BOOLEAN GENERATED ALWAYS AS (route_to IS NOT NULL AND priority IS NOT NULL) STORED
);
CREATE INDEX ON kb_routing_rules (priority) WHERE is_complete;  -- evaluation-order index

-- Signal Sufficiency (from sheet 9) -- deterministic tier thresholds
CREATE TABLE kb_sufficiency_patterns (
    pattern_id            SERIAL PRIMARY KEY,
    category              TEXT NOT NULL,          -- one of the 12 clinical categories
    pattern_name          TEXT NOT NULL,
    tier                  SMALLINT CHECK (tier IN (1,2,3)),  -- NULL if placeholder 'check----------' -- see 05 §6
    is_placeholder        BOOLEAN DEFAULT false,   -- true for the 2 known 'check----------' rows -- exclude from matching until resolved
    minimum_signals_raw   TEXT,                    -- raw SIG:/EM:/PHYS: text; parse at query time or pre-parse into an array column later
    must_have_signals_raw TEXT,
    confidence_rule       TEXT,
    tie_breaker_logic     TEXT,
    probing_guidance      TEXT,                    -- "when_to_keep_probing" -- fetched by ID, never searched (04_CONVERSATION_PIPELINE §D)
    graceful_exit_trigger TEXT,
    pattern_name_embedding vector(EMBED_DIM),       -- the ONE narrow embedding case, per CHUNKING_EMBEDDING_STRATEGY.md §3
    language              TEXT NOT NULL DEFAULT 'en'
);

-- Red Flags (from sheet 7) -- the safety interlock's own table, checked on EVERY turn
CREATE TABLE kb_red_flags (
    flag_id              TEXT PRIMARY KEY,        -- 'RF-001'..'RF-031'
    trigger_phrases      TEXT[] NOT NULL,          -- parsed from mixed newline/quote-separated/paragraph formats, see 05 §5
    trigger_embedding    vector(EMBED_DIM),         -- embedded for semantic match; threshold deliberately MORE permissive than normal RAG
    clinical_meaning     TEXT,
    immediate_action     TEXT,                     -- e.g. 'Tier 3 + SOS flag'
    bot_script           TEXT,                      -- NULLABLE -- RF-028..031 are missing this; app code MUST handle the null case explicitly, see 08 §4 and 15
    escalation_target    TEXT,                      -- NULLABLE -- RF-020 is missing this
    language             TEXT NOT NULL DEFAULT 'en'
);

-- Fallback & Safety Net (from sheet 17) -- code-evaluated triggers, NOT embedded (per CHUNKING_EMBEDDING_STRATEGY.md §5)
CREATE TABLE kb_fallback_scenarios (
    scenario_id          SERIAL PRIMARY KEY,
    section              TEXT NOT NULL,            -- 'A_insufficient' | 'B_contradictory' | 'C_disengagement' | 'D_special_population' | 'disorder_matrix'
    disorder_group       TEXT,                      -- populated only for section='disorder_matrix' rows (15 groups)
    scenario_type        TEXT NOT NULL,
    trigger_condition    TEXT NOT NULL,             -- evaluated as CODE against conversation state -- turn count, confidence, response length -- never embedded
    fallback_action      TEXT,
    bot_script           TEXT,
    escalation_path       TEXT,                     -- CAUTION: source data has a hardcoded person name ("Shreya") in one row -- scrub before loading, see 15
    clinical_reasoning   TEXT,
    language             TEXT NOT NULL DEFAULT 'en'
);

-- Clinical Markers -- NOT a table at all; this is static prompt content.
-- Store it as a versioned config row, not a queryable table:
CREATE TABLE prompt_config (
    config_key    TEXT PRIMARY KEY,       -- e.g. 'clinical_markers_table', 'interlock_rule_set_version'
    version       INT NOT NULL,
    content       JSONB NOT NULL,          -- the 10-category table, verbatim, from 08_SAFETY_INTERLOCK_AND_TRIAGE.md §2
    clinical_signoff_by  TEXT,
    clinical_signoff_at  TIMESTAMPTZ,
    is_live       BOOLEAN DEFAULT false,
    created_at    TIMESTAMPTZ DEFAULT now()
);
-- Per the architecture PDF's Prompt & Persona Engineering section: "Prompt is not visible or
-- editable by any user or admin -- same governed process for all." Application code must never
-- expose a write path to this table outside the ingestion/clinical-review tooling.

-- Future Phase III/IV content (clinical guidance, self-care library) -- not yet received, schema is a placeholder
CREATE TABLE kb_content_chunks (
    chunk_id          TEXT PRIMARY KEY,
    category          TEXT,
    pattern_name      TEXT,
    tier              SMALLINT,
    content_type      TEXT CHECK (content_type IN ('probing_guidance','psycho_education','self_care_tool')),
    text              TEXT NOT NULL,
    embedding         vector(EMBED_DIM),        -- genuinely searched, per 04_CONVERSATION_PIPELINE §3 (Tier 1 recommendation)
    source_document   TEXT,
    language          TEXT NOT NULL DEFAULT 'en',
    linked_pattern_id INT REFERENCES kb_sufficiency_patterns(pattern_id)
);
CREATE INDEX ON kb_content_chunks USING ivfflat (embedding vector_cosine_ops);
```

## 3. Ingestion version control **[IN SCOPE]** (per [07_INGESTION_PIPELINE.md](07_INGESTION_PIPELINE.md) §2, step 8 — atomic swap + rollback)

```sql
CREATE TABLE kb_versions (
    version_id       SERIAL PRIMARY KEY,
    label            TEXT,                       -- e.g. 'v3-2026-09-25'
    status           TEXT CHECK (status IN ('building','validating','live','rolled_back','failed')),
    retrieval_hit_rate     NUMERIC,
    grounding_accuracy     NUMERIC,
    tier_routing_accuracy  NUMERIC,
    adversarial_pass_rate  NUMERIC,
    validated_at      TIMESTAMPTZ,
    activated_at      TIMESTAMPTZ,
    deactivated_at    TIMESTAMPTZ
);
-- Every KB table above should carry a kb_version_id FK in a production implementation,
-- so "swap to live" is an atomic pointer flip, and the previous version stays queryable for rollback.
```

## 4. User, consent, and session tables **[`users`/`consents` OUT OF SCOPE — NestJS-owned, shown for FK context only; `sessions` is a shared boundary — see note below]**

The `sessions` table straddles the scope line: the backend likely owns session *creation* and lifecycle (since it also drives booking/UI concerns), while the AI service needs to *read* `user_id`/`language`/`session_id` and *write* `assigned_tier`, `summary`, `mood_tag`, and `lifecycle_state` transitions triggered by its own routing decisions. **Resolve who owns this table with whoever builds the NestJS backend** — the AI service, at minimum, needs its own Redis-backed running conversation state (shown further below) regardless of that decision, since that state must be sub-millisecond-fast on every turn and has no reason to round-trip through another service.

```sql
CREATE TABLE users (
    user_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role              TEXT CHECK (role IN ('end_user','practitioner','clinical_admin')),
    -- profile fields, PII -- field-level encrypted per 12_SECURITY_COMPLIANCE_DPDP.md §12
    preferred_language TEXT DEFAULT 'en',
    preferred_mode     TEXT CHECK (preferred_mode IN ('voice','text','avatar')),
    created_at         TIMESTAMPTZ DEFAULT now(),
    deleted_at         TIMESTAMPTZ            -- soft-delete for DPDP "right to deletion" requests
);

CREATE TABLE consents (
    consent_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID REFERENCES users(user_id),
    purpose        TEXT NOT NULL,              -- DPDP: consent is PURPOSE-WISE, not blanket
    version        INT NOT NULL,               -- DPDP: consent is VERSIONED
    granted_at     TIMESTAMPTZ,
    revoked_at     TIMESTAMPTZ
);

CREATE TABLE sessions (
    session_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(user_id),
    mode            TEXT CHECK (mode IN ('voice','text','avatar')),
    language        TEXT NOT NULL DEFAULT 'en',
    lifecycle_state TEXT CHECK (lifecycle_state IN ('live','closed','tiered','shared')) DEFAULT 'live',
    -- the 4-state machine named explicitly in the architecture PDFs' Storage section
    assigned_tier   SMALLINT CHECK (assigned_tier IN (1,2,3)),
    -- NOTE: if the 4-state Tier/Crisis model from Phase1_English_Architecture.pdf is confirmed
    -- (see 08_SAFETY_INTERLOCK_AND_TRIAGE.md §3), add a separate `crisis_flag BOOLEAN` column
    -- distinct from `assigned_tier`, rather than overloading tier=3 to mean both "practitioner
    -- referral" and "SOS" -- resolve this before finalizing the column.
    summary          TEXT,                     -- persisted for next session's context, per CLAUDE.md §3 step 14
    mood_tag         TEXT,
    livekit_room_id  TEXT,                     -- only populated for voice/avatar sessions, per 10_LIVEKIT_REALTIME.md
    started_at       TIMESTAMPTZ DEFAULT now(),
    closed_at        TIMESTAMPTZ
);

-- Running conversation state -- read/written on EVERY turn (04_CONVERSATION_PIPELINE.md Step B)
-- Lives in Redis, not Postgres, for latency (single-digit-ms access on the hot path):
--   key: session:{session_id}:state
--   value (JSON): {
--     observed_signals: ["SIG-002", "PHYS-003", ...],
--     turn_count: 7,
--     candidate_pattern_id: 42,
--     duration_established: true,
--     impact_established: false,
--     confidence_score: 0.62,
--     last_response_lengths: [12, 8, 5]   -- feeds Fallback Section C disengagement detection
--   }
```

## 5. Per-turn audit log **[IN SCOPE]** (never blocks the response path — written async, per [09_LATENCY_AND_PERFORMANCE.md](09_LATENCY_AND_PERFORMANCE.md) §8)

```sql
CREATE TABLE turn_audit_log (
    turn_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID REFERENCES sessions(session_id),
    user_id             UUID REFERENCES users(user_id),
    turn_number         INT,
    served_from         TEXT CHECK (served_from IN ('exact_cache','semantic_cache','rag_retrieval')),
    retrieved_chunk_ids TEXT[],                 -- full traceability, per CLAUDE.md §3 step 13
    matched_signal_ids  TEXT[],
    matched_rule_id     TEXT,
    triage_tier         SMALLINT,
    interlock_triggered BOOLEAN DEFAULT false,
    interlock_flag_id   TEXT,                   -- FK-like reference to kb_red_flags, if triggered
    fallback_scenario_id INT,                    -- FK-like reference to kb_fallback_scenarios, if triggered
    latency_ms          JSONB,                   -- per-stage breakdown: {"stt":120,"retrieval":45,"llm_first_token":610,...}
    kb_version_id       INT REFERENCES kb_versions(version_id),
    created_at          TIMESTAMPTZ DEFAULT now()
    -- retention: independent timer per CLAUDE.md/DATA_PROTECTION_SECURITY.md -- audit logs specifically
    -- retained >= 3 years per Clause 5.4, longer than e.g. raw audio which may have a shorter timer
);
```

## 6. Cache tables **[IN SCOPE]** (Redis, two-tier per [09_LATENCY_AND_PERFORMANCE.md](09_LATENCY_AND_PERFORMANCE.md) §6)

```
exact_cache:{language}:{normalized_query_hash}  -> cached response  (near-zero latency, checked first)
semantic_cache index (vector similarity over recent query embeddings, per-language, per CLAUDE.md §4 --
  "an English cache entry and a Hindi cache entry for the same underlying answer are different entries")
```

**Reminder embedded directly in the schema comments above**: a cache hit still triggers the full triage + interlock read against `turn_audit_log` and the Red Flags/Fallback tables — caching only ever skips retrieval + generation, never safety. Application code, not the schema, enforces this — but the schema must make it *possible*, e.g. by never gating writes to `interlock_triggered` on `served_from`.

## 7. Practitioner & booking **[OUT OF SCOPE — NestJS-owned, shown for contract context only]** (implied by Tier 2 routing, not detailed in source material — flagged as a gap in [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md))

```sql
CREATE TABLE practitioners (
    practitioner_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID REFERENCES users(user_id),   -- practitioners are also `users` with role='practitioner'
    kyc_verified      BOOLEAN DEFAULT false,             -- via Onfido, per 03_TECH_STACK.md §5 -- unconfirmed use case
    specialization    TEXT[]
);

CREATE TABLE bookings (
    booking_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id        UUID REFERENCES sessions(session_id),   -- the Tier 2 AI session that triggered this
    user_id           UUID REFERENCES users(user_id),
    practitioner_id   UUID REFERENCES practitioners(practitioner_id),
    livekit_room_id   TEXT,             -- the two-party consultation room, per 10_LIVEKIT_REALTIME.md
    payment_ref       TEXT,             -- Razorpay reference, per 03_TECH_STACK.md §5 -- unconfirmed use case
    scheduled_at      TIMESTAMPTZ,
    status            TEXT CHECK (status IN ('scheduled','completed','cancelled','no_show'))
);

CREATE TABLE call_recordings (
    recording_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id        UUID REFERENCES bookings(booking_id),   -- only practitioner + SOS calls are recorded, never AI Companion turns
    s3_path           TEXT NOT NULL,     -- via LiveKit Egress
    transcript         TEXT,
    ai_summary         TEXT,
    retention_expires_at TIMESTAMPTZ     -- independent retention timer, per 12_SECURITY_COMPLIANCE_DPDP.md
);
```

## 8. What NOT to do with this schema

- Don't store the deterministic tables (`kb_routing_rules`, `kb_sufficiency_patterns`, `kb_fallback_scenarios`) with an embedding column "just in case" — per [05](05_KNOWLEDGE_BASE_DEEP_DIVE.md)/[06](06_SIGNAL_ENRICHMENT_PIPELINE.md)/`CHUNKING_EMBEDDING_STRATEGY.md`, most of this content is never semantically searched; a stray embedding column invites someone to wire up a vector search against it later by mistake.
- Don't let `kb_red_flags.bot_script` have a NOT NULL constraint until RF-028-031 are filled in by the client — but DO make the application code treat a null `bot_script` as a hard error/alert, never a silent fallback to LLM generation (see [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) item #1).
- Don't collapse `assigned_tier` and a potential future `crisis_flag` into one column until the 3-tier vs. 4-state discrepancy ([08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) §3) is resolved with the client.
- Don't skip the `language` column on any table, even ones that feel English-only today.

---
*This document is original synthesis, not a direct extraction from a source file — it operationalizes the storage principles described across `INGESTION.md`, `CONVERSATION_REASONING_FLOW.md`, `SIGNAL_ENRICHMENT_APPROACH.md`, `CHUNKING_EMBEDDING_STRATEGY.md`, `DATA_PROTECTION_SECURITY.md`, and the architecture PDFs' Storage section, combined with the exact real-data shapes confirmed in [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md). Review with the engineering team before treating as final migrations.*
