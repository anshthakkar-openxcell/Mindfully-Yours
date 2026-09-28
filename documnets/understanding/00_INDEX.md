# Mindfully Yours — Understanding Folder (Index)

> **Purpose of this folder**: a complete, implementation-ready synthesis of every planning document, architecture PDF, and knowledge-base spreadsheet the client has provided so far — so that when engineering work actually starts, the team can build from this folder directly instead of re-reading and re-cross-referencing 20+ source files scattered across `documnets/approch/`, `documnets/flow/`, and `documnets/knowledgebase/`.
>
> **How this was built**: every markdown design doc was read in full; every PDF (architecture diagrams, clinical markers, sample conversations, latency filler-phrase library) was extracted page-by-page; every CSV/XLSX knowledge-base sheet was parsed programmatically (not eyeballed) to get exact row counts, real column headers, and verbatim sample data. Where the design markdown's own estimates differ from what's actually in the real files, this folder's numbers come from the real files and are called out as corrections.
>
> **The project itself, as of this writing, has no code** (`backend/` is empty) — this is a pure planning/architecture phase. Everything here is meant to compress that planning phase into a fast, confident implementation start.
>
> **⚠ Build scope: the Python/FastAPI AI service only.** Per explicit direction, this implementation effort covers the RAG harness, conversation pipeline, silent triage, safety interlock, provider-abstraction layer, and ingestion pipeline — i.e. the "AI service" box in [02_ARCHITECTURE.md](02_ARCHITECTURE.md). **The Flutter/Next.js client apps, the NestJS backend (auth, consent UI, practitioner booking, payments), and human-to-human LiveKit rooms (practitioner/SOS calls) are out of scope.** They're still documented in full throughout this folder — the AI service's API contract and correctness depend on understanding what calls into it and why — but nothing outside the AI service is being built here. See [14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md](14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md) for the exact scope line drawn epic-by-epic, and its §4 for the proposed API contract between this service and everything around it.

## Read this first if you're new to the project
[01_PROJECT_OVERVIEW.md](01_PROJECT_OVERVIEW.md) — what Mindfully Yours is, the three design principles everything else follows from, and how the rest of this folder is organized. Read this before anything else.

## Full document map

| # | File | What it covers |
|---|---|---|
| 01 | [PROJECT_OVERVIEW](01_PROJECT_OVERVIEW.md) | The whole picture: what's being built, why, the roadmap, the three non-negotiable design principles |
| 02 | [ARCHITECTURE](02_ARCHITECTURE.md) | The four-layer system architecture, the provider-abstraction layer, data flow, and the client's own 12-section architecture diagram (transcribed in full) |
| 03 | [TECH_STACK](03_TECH_STACK.md) | Every vendor choice and why, including 3 real cross-PDF vendor discrepancies (avatar, STT, payments/KYC) that need client resolution |
| 04 | [CONVERSATION_PIPELINE](04_CONVERSATION_PIPELINE.md) | The exact 14-step runtime turn sequence, the corrected "one-LLM-call" design, and the three distinct retrieval mechanisms (lookup / direct-fetch / semantic search) |
| 05 | [KNOWLEDGE_BASE_DEEP_DIVE](05_KNOWLEDGE_BASE_DEEP_DIVE.md) | Every KB sheet's real columns, exact row counts, verbatim samples, and every data-quality issue found by direct parsing (encoding, placeholders, ID-casing, missing scripts) |
| 06 | [SIGNAL_ENRICHMENT_PIPELINE](06_SIGNAL_ENRICHMENT_PIPELINE.md) | How A1 (signals) + A2 (symptoms) + C11 (rules) get merged into enriched, retrieval-ready records — the exact regex/parsing logic, with real results |
| 07 | [INGESTION_PIPELINE](07_INGESTION_PIPELINE.md) | The offline 8-step KB ingestion pipeline: parse → chunk → tag → embed → index → validate → gate → go-live |
| 08 | [SAFETY_INTERLOCK_AND_TRIAGE](08_SAFETY_INTERLOCK_AND_TRIAGE.md) | **Read this early.** Silent triage, the Clinical Markers table (all 10 categories, verbatim), the Red Flags mechanism, and the Fallback & Safety Net — including a hard blocker (4 red flags with no bot script) |
| 09 | [LATENCY_AND_PERFORMANCE](09_LATENCY_AND_PERFORMANCE.md) | The 1.5-2.5s target, streaming strategy, two-tier caching, and the full filler-phrase library (13 categories, situation-mapped) |
| 10 | [LIVEKIT_REALTIME](10_LIVEKIT_REALTIME.md) | WebRTC transport for AI Companion voice/avatar, practitioner calls, and SOS calls — one technology, three use cases |
| 11 | [DATA_MODEL_AND_STORAGE](11_DATA_MODEL_AND_STORAGE.md) | A concrete, ready-to-adapt PostgreSQL+pgvector+Redis schema proposal covering every table this project needs |
| 12 | [SECURITY_COMPLIANCE_DPDP](12_SECURITY_COMPLIANCE_DPDP.md) | Contractually-binding data protection rules (some carry liquidated damages / uncapped liability) — read before touching any vendor integration or test data |
| 13 | [LANGUAGE_PHASING](13_LANGUAGE_PHASING.md) | Phase 1 English-only, Phase 2 Hindi — the plan, and one open cross-PDF disagreement about *how* Hindi queries get handled |
| 14 | [FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN](14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md) | **Start here for build scope.** AI-service-only epics, dependency-ordered build sequence, the API contract with the (out-of-scope) backend, and what can be built today vs. what's genuinely blocked |
| 15 | [OPEN_QUESTIONS_AND_BLOCKERS](15_OPEN_QUESTIONS_AND_BLOCKERS.md) | **The consolidated punch list.** Every blocker, discrepancy, and data-quality issue found across the whole exercise, ranked by severity |
| 16 | [GLOSSARY](16_GLOSSARY.md) | Every code prefix (SIG/PHYS/EM/RULE/RF), clinical term, and vendor name, in one lookup table |
| 17 | [PERSONA_AND_CONVERSATION_STYLE](17_PERSONA_AND_CONVERSATION_STYLE.md) | The AI Companion's actual tone and conversational pattern, extracted from 18 real sample conversations |
| 18 | [NEW_CONVO_DATA_CATALOG](18_NEW_CONVO_DATA_CATALOG.md) | **New (Sept 2026).** Catalog of the 46-file clinical-team drop that largely fills the Phase II/III/IV content gap — the "Layer I-IV" depth model, the master AI decision-pathway spec, real Phase IV self-help tools, and several new open items (unreconciled taxonomies, sensitive content needing governance) |

## If you only have time to read three files

1. **[01_PROJECT_OVERVIEW.md](01_PROJECT_OVERVIEW.md)** — the principles everything else follows from.
2. **[04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md)** — the exact mechanics of what happens on every single user turn.
3. **[15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md)** — what's not actually settled yet, so you don't build on an assumption that turns out to be wrong.

## The single most important cross-cutting rule

Per [01_PROJECT_OVERVIEW.md](01_PROJECT_OVERVIEW.md) principle #2, restated everywhere it's relevant throughout this folder: **the safety interlock is never skipped, never bypassed, never delegated to the LLM, and always fails toward the more cautious path.** If any implementation decision in any epic ever seems ambiguous, resolve it in favor of this rule over speed, cost, or convenience.

## Known hard blockers before full production launch (see [15](15_OPEN_QUESTIONS_AND_BLOCKERS.md) for full detail)

1. **Four Red Flags (RF-028–031) have no verbatim bot script** — covers some of the most severe disclosure categories in the KB (violence, rape, molestation). **Confirmed on a second, independent re-verification pass — this is the single most important open item in the whole knowledge base.** Until scripts arrive, a matched flag with an empty script must route to a hard human alert, never a silent LLM-generated fallback.
2. `EM` signal codes are confirmed undefined as a real, matchable legend (unlike `SIG` and `PHYS`, which are fully resolved) — re-confirmed as the one remaining hard blocker on the routing/sufficiency logic.
3. ~~Phase III/IV content not yet received~~ — **largely resolved as of a Sept 2026 client drop** (46 clinical-team working documents). See [18_NEW_CONVO_DATA_CATALOG.md](18_NEW_CONVO_DATA_CATALOG.md). This surfaced new work, though: three separate severity/depth/scenario/emotion taxonomies now need reconciling into one canonical model before the data model is finalized, a few files have real content gaps (notably Trauma, again — see below), and one section (paraphilic-disorder content) needs an explicit clinical/legal governance decision before going anywhere near a live index.
4. `Kb_Phase_I_17.csv` (Fallback & Safety Net) has ~70% more content than first documented — a 4th section (special-population scenarios: perinatal, bereavement, burnout, identity/life-transition) plus a separate 84-row, 15-group disorder-specific matrix — and a real individual's name is hardcoded into **three** escalation-path rows (confirmed on re-verification, not just one). Both corrected throughout this folder; the name still needs scrubbing from the source data before production use.
5. The new drop's own Trauma content is nearly empty (one scenario, cuts off mid-sentence) — the same domain (violence/abuse) where the 4 missing red-flag scripts in item #1 already live. This is now the project's single most under-served content area and worth prioritizing with the clinical team.

None of these block starting engineering work on the AI service — see [14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md](14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md) §6 for exactly what can be built today with synthetic placeholders versus what's genuinely gated on this content arriving.

## Source material this folder is derived from

```
documnets/approch/
  APPROACH.md, CLAUDE.md, DATA_PROTECTION_SECURITY.md, INGESTION.md, LATENCY.md, LIVEKIT.md
  README.md (explains how the 3 PDFs below relate -- read this before opening any of them)
  Mindfully_Yours_Phase1.pdf, Mindfully_Yours_Phase1_Final.pdf,
  Mindfully_Yours_Phase1_English_Architecture.pdf, Mindfully_Yours_AI_Latency_Filler_Phrases.pdf
documnets/flow/RAG/
  END_TO_END_RAG_APPROACH.md, KNOWLEDGE_BASE_CONTENT.md, SIGNAL_ENRICHMENT_APPROACH.md
  rag simple flow.pdf
documnets/knowledgebase/
  CHUNKING_EMBEDDING_STRATEGY.md, CONVERSATION_REASONING_FLOW.md, chunking .docx
  Clinical_Markers_Reference_Table (1).pdf, Convo Samples.pdf
  Kb Phase I.xlsx, Kb Phase I(7/9/17/A1/A2/C11).csv
  Knowledge Base Directory(Sheet1).csv, Mindfully_Yours_Merged_Signal_Profile (2).xlsx
  convo data/MYPL - Mindfully Yours Work/   -- 46-file Sept 2026 drop, see 18_NEW_CONVO_DATA_CATALOG.md
    decrypted/                              -- deduplicated, readable copy (44 of 46 files; 3 still locked)
```

**Two confirmed zero-value duplicate files have been removed from the repo** (not just hidden):
`Kb Phase I(A2 (1).csv` (byte-identical to `Kb Phase I(A2.csv`) and `Mindfully_Yours_Merged_Signal_Profile (1).xlsx` (a strict subset of `(2).xlsx`, zero unique rows). Neither removal lost any information — see [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) §0 and §8 for the verification.

**The three architecture PDFs are intentionally all still kept** — they are NOT duplicates, they genuinely disagree with each other on real decisions (avatar vendor, STT vendor, the tier/crisis model — see [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #7-9). Deleting any one of them would lose real, still-relevant information. `documnets/approch/README.md` gives a one-glance guide to what each PDF is for and exactly how they differ, so opening that folder is never ambiguous even though three overlapping files sit in it.

**This folder is a synthesis layer, not a replacement.** Where any document here disagrees with a source file, the source file is authoritative unless this folder explicitly documents why its own number/finding supersedes it (usually because it comes from directly parsing the real data rather than an earlier estimate). Keep this index and [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) updated as blockers resolve and new source material arrives.
