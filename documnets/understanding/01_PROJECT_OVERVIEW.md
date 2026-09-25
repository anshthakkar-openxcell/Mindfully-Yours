# 01 — Project Overview

> Read this first. It answers: what are we building, for whom, and what are the non-negotiable principles that every later document assumes.

## 1. What Mindfully Yours is

Mindfully Yours is an AI-led mental and emotional-wellness companion and triage platform. A person opens the app and talks — by voice, text, or an on-screen 2-D avatar — to an AI Companion that is meant to feel like a warm, present conversation, never a form or a diagnostic quiz. Underneath that calm surface, the system is continuously doing real clinical work on every single turn:

- silently assessing severity (which "tier" this person's situation falls into),
- deciding whether self-care content is enough or a licensed practitioner should be looped in, and
- detecting genuine crisis and escalating to a human being — **independently of anything the AI itself decides.**

The product serves two very different populations through one experience:
- the large majority, dealing with everyday emotional/mental-wellness challenges — served with self-care conversation, journaling, reflection, and grounded psycho-education;
- a smaller number who need routing to a licensed practitioner (Tier 2) or immediate human crisis help (Tier 3).

The client entity is **Mindfully Yours Private Limited**; the platform is being built by **OpenXcell Technolabs Pvt. Ltd.** under a signed Technology Development and Services Agreement (Sept 2026 draft). Every clinical and safety decision documented here originates from client-authored material, not from engineering judgment — see [08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) for exactly which content is client-authored verbatim.

## 2. The three design principles everything else follows from

These three rules are referenced constantly throughout every other document in this folder. When any implementation decision seems ambiguous, resolve it in favor of these, in order:

1. **Grounded, not generated.** The Companion never improvises mental-health guidance from the LLM's general training. Every substantive response is retrieved from the client's own clinical knowledge base first — the model's job is to *phrase* it naturally, never to *invent* it. This is the entire reason the system is RAG-based rather than fine-tuned or freely prompted.
2. **Safety is independent of the AI, not a feature of it.** The safety interlock that detects crisis and can force escalation is a separate, deterministic, rule-based system — never a judgment call the LLM makes. It runs on every single turn, cannot be skipped by caching, retries, or errors, and always fails toward the more cautious path, never the more permissive one.
3. **The surface stays human; the intelligence stays invisible.** Severity assessment happens by silently reading the conversation — no questionnaires, no clinical-feeling forms, no visible "scoring." The product must never feel like it's grading the user.

**Tie-breaker rule for the whole project**: if any two documents (or any document and a coding decision) ever seem to disagree, principle #2 wins. Nothing in this project trades safety for speed, cost, or convenience.

## 3. The four-layer architecture, in one paragraph

Client apps (Flutter mobile + Next.js/React web, full feature parity, serving both end users and practitioners) talk to a NestJS backend (REST APIs, auth, RBAC, orchestration) which delegates all conversational-AI work to an isolated Python/FastAPI AI service (RAG harness, conversation layer, silent triage, safety interlock — kept deliberately separate from the main backend so safety-critical logic has a clean boundary). Everything persists in one data spine: PostgreSQL + pgvector for both relational and embedding data, plus Redis for session state and caching. Full detail: [02_ARCHITECTURE.md](02_ARCHITECTURE.md).

Every external AI capability (LLM, STT, TTS/voice, avatar, embeddings) sits behind a **provider-abstraction layer** — application code calls a common interface, never a vendor SDK directly. This is what makes every vendor choice below a *configuration* decision, not an architectural commitment, and it's also a contractual requirement (Clause 2.8 — provider swaps need client written consent; see [12_SECURITY_COMPLIANCE_DPDP.md](12_SECURITY_COMPLIANCE_DPDP.md)).

## 4. The conversation flow, end to end (summary — full detail in 04)

**Before any user ever talks to the app** (offline, ingestion, script-driven, run once and again on every KB update): the clinical team's knowledge base is chunked, embedded, indexed, and validated through a pre-launch gate (grounding accuracy, tier-routing accuracy, adversarial/crisis-trigger testing) before it's ever allowed to serve real users. See [07_INGESTION_PIPELINE.md](07_INGESTION_PIPELINE.md).

**Every time a user talks** (runtime, same fixed order, every single turn — see [04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md) for the exact 14-step sequence):
1. Turn arrives, transcribed if spoken.
2. Two-tier cache checked (exact-match, then semantic) — the primary cost lever in the system.
3. On a cache miss: KB retrieval, confidence-scored.
4. Silent triage reads the turn for severity signal — runs on **every** turn, cache hit or not.
5. Safety interlock independently evaluates for crisis language, can force escalation regardless of anything else.
6. Prompt assembled (persona + retrieved passages + trimmed recent history, not the full transcript) → sent to the LLM, which composes phrasing only — never decides *what* or *whether* it's safe to say.
7. Output checked for grounding, then streamed back as voice/text/avatar.
8. Full audit log; session summary + mood tag persisted for next conversation's context.

Depending on assessed tier: Tier 1/2 stay in self-care conversation or move to practitioner booking; Tier 3 triggers immediate SOS routing with a human alerted.

## 5. Why RAG, not a custom-trained or freely-prompted model

A custom-trained model needs large data volumes and heavy GPU investment — effectively its own separate project. RAG gets a working, fully-controllable product live fast: the KB is entirely owned and editable by the clinical team, every response is traceable to a source passage, and the system only pays for inference, not training. Every RAG conversation is logged — meaning the platform is quietly building the exact dataset a future custom model would need. RAG is a first step toward that future capability, not a detour from it.

**Important legal constraint layered on top of this** (Clause 5.7 of the signed agreement): none of this logged data may ever be used to train/fine-tune/improve any AI/ML model except strictly to perform the contracted services — see [12_SECURITY_COMPLIANCE_DPDP.md](12_SECURITY_COMPLIANCE_DPDP.md) §1. "Building a future training dataset" is true in principle but must stay entirely within the Company's ownership and control — it can never be repurposed by the vendor building this platform.

## 6. Language approach: bilingual by design, phased rollout

- **Phase 1 ships English only** — not because Hindi is an afterthought, but as deliberate risk reduction: prove conversation, triage, and the safety interlock work correctly in one language before adding a second. Every stored record and logged row carries a `language` field from day one (set to `en` everywhere in Phase 1) specifically so Phase 2 is additive, never a schema migration.
- **Phase 2 adds Hindi**: the KB is translated once, offline (never live/per-query — that would add cost and latency to every turn), embedded into the same shared vector index, and the Hindi/Hinglish crisis vocabulary is hand-authored with the clinical team, never machine-translated (same reason the English crisis vocabulary is hand-authored, not model-inferred). The runtime pipeline itself doesn't change — the LLM simply replies in whichever language the user just used, independent of which language the retrieved chunk happened to be stored in.
- Full detail: [13_LANGUAGE_PHASING.md](13_LANGUAGE_PHASING.md).

## 7. Model & provider choices (summary — full detail in 03)

| Capability | Primary choice | Why |
|---|---|---|
| LLM (generation) | Sarvam-M | Built for Indian languages + Hinglish tone; materially cheaper than a Western model for the same job |
| Embeddings | Sarvam | Same reasoning — must understand Hindi and English equally well, and switching later means a full re-embed |
| Speech-to-text | Deepgram | Best latency/accuracy balance on Hindi + code-switched Hinglish |
| Voice (TTS) | Sarvam TTS (Bulbul) | Natural Hindi voice at a fraction of premium alternatives' cost |
| Avatar | 2-D character (Rive/Live2D) | No render fee unlike a realistic rendered avatar — costs the same as voice-only |
| Real-time transport | LiveKit (WebRTC) | Replaces a separate Agora/Daily/Twilio shortlist with one technology for AI Companion + practitioner calls + SOS calls |
| Fallback benchmark | GPT-4o-mini / Claude Haiku, OpenAI embeddings, ElevenLabs | Comparison point from the technology review, not the default |

None of these are permanent commitments — the provider-abstraction layer exists so any of them can be swapped based on pre-launch evaluation results, subject to the client's written consent per Clause 2.8.

## 8. Cost-control approach, in priority order

1. **The two-tier cache** — avoids the LLM call entirely wherever possible. The single biggest cost lever in the system.
2. **Provider choice** — Sarvam's India-first pricing over premium Western defaults.
3. **Smaller engineering levers** — trimmed context windows, incremental re-ingestion (only changed KB content gets re-embedded), rule-based (not model-based) safety checks, per-user rate limits, compressed audio transport. Avatar rendering is opt-in and cost-gated — the most expensive component by a wide margin when using a realistic rendered face (mitigated here by choosing 2-D avatar instead).

## 9. Roadmap and regulatory scope

- **Phase 1**: English-only launch — full conversational companion, triage, safety interlock, self-care, journaling, practitioner booking. Built DPDP-compliant from day one (consent capture, India data residency, encryption, access control, audit logging).
- **Phase 2**: Hindi added on top of the same architecture.
- **This is a DPDP-compliant platform (India's Digital Personal Data Protection Act), not a HIPAA-compliant one.** No U.S. health-data regime applies. Do not introduce HIPAA-specific requirements (BAAs, U.S. de-identification standards, U.S. breach-notification timelines) — they belong to a different regulatory context entirely.

## 10. How the rest of this `understanding/` folder is organized

See [00_INDEX.md](00_INDEX.md) for the full map. In short: 02–03 cover architecture and stack; 04 covers the exact runtime pipeline; 05–08 cover the knowledge base, ingestion, signal enrichment, and safety/triage content in deep, implementation-ready detail; 09–10 cover latency and LiveKit; 11 proposes a concrete data model; 12–13 cover security/compliance and language phasing; 14 is the feature-by-feature implementation plan; 15 lists every open blocker; 16 is a glossary of every code/term (SIG, PHYS, RULE, RF, tier, etc).

---
*Source material: `documnets/approch/APPROACH.md`, and the Phase 1 architecture PDFs (see [15_OPEN_QUESTIONS_AND_BLOCKERS.md] for anything the PDFs added beyond the markdown). This document is a synthesis, not a replacement — the original files remain the authoritative source if this summary and a source file ever disagree.*
