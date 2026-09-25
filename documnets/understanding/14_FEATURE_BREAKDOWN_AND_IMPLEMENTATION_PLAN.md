# 14 — Feature Breakdown & Implementation Plan

> **Scope for this build: the Python/FastAPI AI service only.** Per explicit direction, this implementation effort covers the RAG harness, conversation pipeline, silent triage, safety interlock, provider-abstraction layer, ingestion pipeline, and the AI service's own data (KB tables, session/conversation state, audit logs) — i.e. everything inside the "AI service" box in [02_ARCHITECTURE.md](02_ARCHITECTURE.md) §1. **The Flutter/Next.js client apps, the NestJS backend (auth, RBAC, user/consent CRUD, practitioner booking, payments), and human-to-human LiveKit rooms (practitioner consultations, SOS calls) are out of scope for this build** — they're documented elsewhere in this folder for context (so the AI service's contract with them is clear), not because they're being built here. Epics below are labeled accordingly.

## 1. Roles relevant to the AI service (full role list, with scope noted)

| Role | What they do | In scope here? |
|---|---|---|
| **End user** (via the AI service's API contract, not its own UI) | Talks to the AI Companion; the AI service receives transcript/audio and returns a response — it does not own login, profile storage, or consent UI | Partially — the AI service consumes `user_id`/`session_id`/consent-check results handed to it by the backend, per [04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md) step 1 |
| **Practitioner** | Receives Tier 2 routing decisions *from* the AI service; booking/consultation itself is NestJS+LiveKit | Out of scope — the AI service only emits the routing decision, per [08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) §3 |
| **Clinical team / clinical lead** | Owns interlock vocabulary, tier thresholds, prompt sign-off; authors against KB gaps; receives safety-event escalations | **In scope** — the AI service's ingestion/validation tooling and prompt-config storage exist to serve this workflow ([07_INGESTION_PIPELINE.md](07_INGESTION_PIPELINE.md), [11_DATA_MODEL_AND_STORAGE.md](11_DATA_MODEL_AND_STORAGE.md) §2) |
| **AI service's own consuming clients** (the NestJS backend, practically speaking) | Calls the AI service's API per turn, passes consent/session context in, receives a response + tier + audit trail out | **This is effectively who the AI service is built for** — treat the AI service as a well-defined internal API, not a user-facing product |
| **Admin** | Explicitly excluded from prompt visibility/edit rights ("Prompt is not visible or editable by any user or admin") | Out of scope for UI; **in scope** for the AI service to enforce this — the prompt-config write path must never be exposed on any general-purpose API surface, see [11_DATA_MODEL_AND_STORAGE.md](11_DATA_MODEL_AND_STORAGE.md) §2 |
| **Client's on-shift crisis team** | Receives Tier 3/SOS alerts | Out of scope — the AI service's job ends at emitting the escalation event/flag; who receives and acts on it is a NestJS/ops concern |

## 2. Feature epics — AI service scope marked explicitly

### Epic B — Knowledge base ingestion pipeline **[IN SCOPE]**
- The 8-step offline pipeline: intake/parse → LLM boundary refinement → tagging → embedding → store/index → retrieval+grounding eval → adversarial validation → gate/go-live ([07_INGESTION_PIPELINE.md](07_INGESTION_PIPELINE.md)).
- The signal enrichment merge (A1+C11, A2+A1) ([06_SIGNAL_ENRICHMENT_PIPELINE.md](06_SIGNAL_ENRICHMENT_PIPELINE.md)).
- **Schema**: all `kb_*` tables + `kb_versions` in [11_DATA_MODEL_AND_STORAGE.md](11_DATA_MODEL_AND_STORAGE.md) §2-3 — these live in the AI service's own Postgres+pgvector instance/schema.
- **Depends on**: resolving the data-quality items in [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) Tier 1 before this can be treated as production-validated (structural build can start immediately using the real-but-imperfect data; go-live validation must wait for blockers #1, #2, #3 at minimum).
- **This is the ceiling on everything downstream** — per [07_INGESTION_PIPELINE.md](07_INGESTION_PIPELINE.md) §1, retrieval can never be better than what ingestion gave it. Build and validate this first, before any conversation-pipeline code depends on it.

### Epic C — Silent triage & safety interlock **[IN SCOPE — highest priority]**
- Clinical Markers as static prompt content ([08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) §2).
- Red-flag phrase matching + verbatim script fetch ([08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) §4).
- Fallback & Safety Net conversation-state evaluation, including the confirmed 4-section + disorder-matrix structure ([08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) §5).
- Tier routing via `C11` priority-ordered rule evaluation.
- **This is the highest-priority epic in the entire AI service** per [01_PROJECT_OVERVIEW.md](01_PROJECT_OVERVIEW.md) principle #2 — build and adversarially test this before wiring it into the full conversation pipeline, not as an afterthought bolted onto a working chat flow.
- **The AI service's job here ends at emitting a decision** (tier, red-flag match, fallback scenario) plus the verbatim script/action to return — it does not itself notify a human crisis team or a practitioner; that hand-off is a NestJS/backend responsibility consuming the AI service's output.
- **Depends on**: Epic B (needs `kb_red_flags`, `kb_fallback_scenarios`, `kb_routing_rules` populated); blocked from full launch-readiness by [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #1 (missing bot scripts, now confirmed as the single most important open item in the KB) and #7 (tier model discrepancy — affects how many distinct values the AI service's tier/crisis output field needs).

### Epic D — Conversation pipeline (the 14-step runtime sequence) **[IN SCOPE — the core of this build]**
- The full turn-by-turn flow: cache checks → retrieval → triage → interlock → prompt assembly → LLM call → guardrail → stream → audit → close ([04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md)).
- The embedding-based signal pre-filter (Step A) and running conversation state (Step B, Redis-backed).
- Provider-abstraction interfaces for LLM/STT/TTS/embeddings ([02_ARCHITECTURE.md](02_ARCHITECTURE.md) §2, [03_TECH_STACK.md](03_TECH_STACK.md)).
- **The AI service's external contract**: an API (REST/WebSocket for text; a LiveKit Agent process for voice/avatar — see Epic G) that takes `user_id`, `session_id`, a consent-check result, and either text or an audio stream, and returns a streamed response plus the full audit/tier metadata. Everything about *how that input arrived* (login, consent UI, room provisioning) is the caller's concern, not this service's.
- **Depends on**: Epic B (KB populated) and Epic C (interlock built) — this epic wires them together into the live pipeline.

### Epic E — Two-tier caching **[IN SCOPE]**
- Exact-match/FAQ cache + semantic cache, Redis-backed ([09_LATENCY_AND_PERFORMANCE.md](09_LATENCY_AND_PERFORMANCE.md) §6).
- Language-aware cache keys (English/Hindi entries are distinct, never translated).
- **Depends on**: Epic D existing in a basic form — but should be designed alongside Epic D from the start, since it's the single biggest cost lever in the whole service.

### Epic F — Latency, streaming & filler phrases **[IN SCOPE]**
- Streaming at every stage (STT partials, LLM tokens, TTS sentence-by-sentence) ([09_LATENCY_AND_PERFORMANCE.md](09_LATENCY_AND_PERFORMANCE.md) §3). Avatar-frame streaming itself is a client-rendering concern, but the AI service must stream audio in a way that supports it.
- Filler-phrase library integration, situation-mapped ([09_LATENCY_AND_PERFORMANCE.md](09_LATENCY_AND_PERFORMANCE.md) §4).
- Per-stage latency instrumentation, P50/P95/P99 tracking ([09_LATENCY_AND_PERFORMANCE.md](09_LATENCY_AND_PERFORMANCE.md) §11).
- **Depends on**: Epic D (needs a real pipeline to instrument and stream).

### Epic G — LiveKit integration, AI Companion Agent only **[PARTIALLY IN SCOPE]**
- **In scope**: the LiveKit Agent process itself — a server-side participant that subscribes to a user's audio track in a Room and feeds it through Epic D's pipeline (STT → retrieval/triage/interlock/LLM → TTS), publishing the response back as an outgoing track. This is effectively part of the AI service's deployable, per [10_LIVEKIT_REALTIME.md](10_LIVEKIT_REALTIME.md) §3.
- **Out of scope**: Room creation/token issuance for practitioner consultations and SOS calls (two-party human calls, no AI Agent involved), and LiveKit Egress recording/S3 storage for those calls — these belong to the NestJS backend + infra, not the AI service. The AI service does not create Rooms; it joins one it's handed a token for.
- **Depends on**: Epic D (the Agent needs a working pipeline to feed audio through).

### Epic H — Practitioner booking, payments, KYC **[OUT OF SCOPE]**
- Practitioner directory, booking flow, KYC (Onfido), payments (Razorpay) — all NestJS backend + frontend responsibilities.
- **Relevant to this build only as a consumer of Epic C's output**: the AI service emits a Tier 2 routing decision; whatever happens next (booking flow, notification, calendar) is entirely outside this service. Documented in [11_DATA_MODEL_AND_STORAGE.md](11_DATA_MODEL_AND_STORAGE.md) §7 for context/contract clarity only — do not build these tables as part of this effort.

### Epic I — Observability, feedback & incident loop **[IN SCOPE, for the AI service's own signals]**
- Quality metrics (grounding, fallback rate, tier accuracy), safety-event logging, cost/usage tracking, model regression checks (architecture PDF §⑧) — these are all things the AI service itself measures and logs.
- Feedback loop: session feedback → KB gap reporting → safety-event escalation → root-cause/rollback to last approved prompt version (architecture PDF §⑦) — the *rollback mechanism* (Epic B's `kb_versions` table) and the *audit trail* (`turn_audit_log`) are in scope; the human workflow around reviewing feedback and deciding to act on it is a clinical-ops/product process, not code this service needs to provide UI for.
- **Depends on**: Epic B (`kb_versions` table + rollback mechanism) and Epic D (`turn_audit_log` needs to exist first).

### Epic J — Hindi (Phase 2, not Phase 1 scope) **[IN SCOPE, when Phase 2 starts]**
- Offline KB translation, shared vector index, hand-authored crisis vocabulary ([13_LANGUAGE_PHASING.md](13_LANGUAGE_PHASING.md)) — all AI-service-side work (ingestion + pipeline), no frontend/backend changes needed per the source material's own claim that this is additive.
- **Depends on**: every Phase 1 AI-service epic being complete and validated first.

### Not epics in this plan — explicitly out of scope, listed once so nothing is silently assumed
- Epic A (consent/profile/data-rights UI and storage) — NestJS + frontend. The AI service only *reads* a consent-check result passed to it per turn; it does not capture or store consent itself.
- Client apps (Flutter, Next.js) — entirely out of scope.
- NestJS backend (auth, RBAC, orchestration, non-AI product features) — entirely out of scope, except as the calling client of this AI service's API.
- Practitioner/SOS LiveKit room management, Egress recording, transcription/summary pipeline for those calls — out of scope (Epic G note above).

## 3. Suggested build order (AI-service epics only)

```
1. Epic B (KB ingestion) ── build first; everything downstream depends on it
2. Epic C (triage/interlock) ── depends on B; build and adversarially test in isolation
3. Epic D (conversation pipeline) ── depends on B + C; wires everything into the live turn sequence
4. Epic E (caching) ── designed alongside D, ships with or shortly after D
5. Epic F (latency/streaming/fillers) ── depends on D, layer on top once D works end-to-end
6. Epic G (LiveKit Agent) ── depends on D; this is what lets voice/avatar mode reach a real Room
7. Epic I (observability/feedback) ── depends on B + D, but instrument from day one rather than bolting on at the end
8. Epic J (Hindi) ── Phase 2, after Phase 1 is live and validated
```

**The one epic that should never be treated as "later"**: Epic C (safety interlock). Per [01_PROJECT_OVERVIEW.md](01_PROJECT_OVERVIEW.md) principle #2, it's tempting to build a working chat experience first and "add safety after" — don't. Build the interlock as an independent, testable module from day one, and integrate it into Epic D's pipeline as a hard dependency, not a plugin added at the end.

## 4. The AI service's external API contract (what the NestJS backend needs from it)

Since the backend and frontend are out of scope but still need to integrate with this service, the contract boundary should be explicit from the start:

**Inbound** (from NestJS, per turn):
- `user_id`, `session_id`, `language` (always `en` in Phase 1)
- Consent-check result (boolean/status — the AI service trusts this, it doesn't re-verify consent itself)
- The turn's content: text, or an audio stream reference / LiveKit Room+track identifiers for voice
- Recent conversation summary/history reference (or the AI service owns this internally via Epic D's Redis-backed running state, keyed by `session_id` — recommended, since it avoids the backend needing to shuttle state back and forth every turn)

**Outbound** (to NestJS, per turn):
- The generated response (streamed: text chunks, and/or audio chunks)
- `assigned_tier` (and, pending resolution of [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #7, a possible separate `crisis_flag`)
- Whether a red flag or fallback scenario was triggered, and which one (for the backend to route Tier 2 bookings or Tier 3/SOS alerts — the AI service does not perform this routing itself)
- Full per-turn audit metadata (retrieved chunk IDs, matched signals/rules, latency breakdown) — per `turn_audit_log` in [11_DATA_MODEL_AND_STORAGE.md](11_DATA_MODEL_AND_STORAGE.md) §5

**Recommendation**: define this contract (e.g. an OpenAPI spec or a shared schema) very early in Epic D — it's the seam between the in-scope and out-of-scope parts of the system, and getting it wrong means rework on both sides later.

## 5. Pre-launch validation gate (applies across Epics B, C, D — the actual go/no-go criteria)

Per [07_INGESTION_PIPELINE.md](07_INGESTION_PIPELINE.md) §2 step 6-8 and the architecture PDF §⑤, nothing goes live until:
- Retrieval hit-rate and grounding accuracy are measured **separately** and both clear threshold.
- Tier-routing validation passes, with **false negatives on high-risk cases as the primary safety metric** (the single most important explicit KPI named anywhere in the source material).
- Adversarial/jailbreak/crisis-trigger tests pass against the interlock specifically.
- A failure routes back to the clinical team — it never reaches real users.

This gate applies entirely within the AI service's own scope — it doesn't require the frontend or backend to exist, only synthetic/scripted callers exercising the AI service's API contract (§4 above).

## 6. What can be built and tested today vs. what's genuinely blocked

**Can build and structurally test now** (using synthetic placeholder data per [12_SECURITY_COMPLIANCE_DPDP.md](12_SECURITY_COMPLIANCE_DPDP.md) §8 for anything not yet client-supplied, and a stubbed/mocked caller in place of the real NestJS backend):
- The entire conversation pipeline shape (Epic D), including the one-LLM-call design.
- Ingestion pipeline mechanics (Epic B) against the real KB sheets already received (with known data-quality issues normalized per [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) §0).
- Red flag and fallback matching logic (Epic C) for the 27 of 31 flags that do have bot scripts.
- Two-tier caching, streaming, filler phrases (Epics E/F) — none of this depends on missing content.
- The LiveKit Agent process (Epic G) against a locally-run or dev LiveKit server — doesn't require the practitioner/SOS room-management code to exist.
- The AI service's own data model (Epic B/C/D/I schema, audit logging) in [11_DATA_MODEL_AND_STORAGE.md](11_DATA_MODEL_AND_STORAGE.md) §2-3, §5-6.

**Genuinely blocked until external input arrives**:
- Full Tier 1 self-care recommendation quality (needs Phase III/IV content — [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #3).
- Complete rule-matching coverage across all 285 signals (#4).
- Any EM-code-dependent routing logic (#2).
- Final go-live for the 4 red flags missing bot scripts (#1) — build the matching logic now, but gate production activation of those 4 flags specifically until scripts arrive.
- Vendor-final decisions (avatar, STT dual/single) pending technology-review sign-off (#8, #9) — these affect the provider-abstraction adapters in Epic D but not the pipeline's structure.

---
*This document is original synthesis — a build plan derived from every other document in this folder, not a client-delivered project plan. Validate epic scope and the API contract in §4 with whoever owns the NestJS backend before treating either as final.*
