# Mindfully Yours — Project Overview & Technical Approach

This is the primary reference for understanding the project as a whole — what it is, why it's built the way it is, and how the pieces fit together. Read this first. `CLAUDE.md` (implementation rules) and `LATENCY.md` (performance) go into tactical detail on top of the approach explained here.

---

## 1. What this project is

Mindfully Yours is an AI-led mental and emotional-wellness companion and triage platform. A person opens the app and talks — by voice, text, or an avatar — to an AI Companion that feels like a warm, present conversation, not a form or a diagnostic tool. Underneath that calm surface, the system is quietly doing real clinical work: assessing severity, deciding whether self-care is enough or a human practitioner is needed, and — where it matters most — detecting crisis and escalating to a real person, independent of anything the AI itself decides.

The platform serves two very different scales of need with one product: the large majority of people dealing with everyday emotional and mental-wellness challenges (self-care, journaling, reflection), and the smaller number who need to be routed to a licensed practitioner or, in a genuine crisis, to immediate human help.

---

## 2. The three design principles everything else follows from

**1. Grounded, not generated.** The Companion never improvises mental-health guidance from a model's general training. Every substantive response is retrieved from the client's own clinical knowledge base first — the model's job is to phrase it naturally, not to invent it. This is the whole reason the system is a RAG (retrieval-augmented generation) architecture rather than a fine-tuned or freely-prompted model.

**2. Safety is independent of the AI, not a feature of it.** The safety interlock that detects crisis and can force escalation is a separate, deterministic, rule-based system — not a judgment call the LLM makes. It runs on every single turn, cannot be skipped by caching or errors, and fails toward caution, never toward permissiveness. This separation exists specifically so that a bad day for the AI (a hallucination, a provider outage, an unexpected prompt) can never become a bad day for user safety.

**3. The surface stays human; the intelligence stays invisible.** Severity assessment (triage) happens by silently reading the conversation — no questionnaires, no clinical-feeling forms. The product should never feel like it's grading the user.

---

## 3. The high-level architecture

Four cooperating layers, deliberately kept separate so clinical logic and safety are never entangled with application UI:

- **Client apps** — mobile (Flutter) and web (Next.js/React), full feature parity between them, serving both end users and practitioners.
- **Backend (NestJS)** — REST APIs, auth, role-based access, orchestration between the client apps and the AI service.
- **AI service (Python/FastAPI)** — the RAG harness, conversation layer, silent triage, and the safety interlock. This is architected as its own isolated service, not bolted onto the main backend, specifically so the safety-critical logic has a clean boundary.
- **Data spine** — PostgreSQL + pgvector as a single store for both relational and semantic (embedding) data, with Redis for caching and session/conversation memory.

Every external AI capability (the LLM, speech-to-text, voice/avatar, embeddings) sits behind a **provider-abstraction layer** — application logic calls a common interface, never a vendor SDK directly. This is what makes every model/vendor choice in this document a configuration decision, not an architectural commitment.

---

## 4. The conversation flow, end to end

**Before any user ever talks to the app** (ingestion, one-time, script-driven): the clinical team's knowledge base is chunked, embedded, and indexed. Every version goes through a pre-launch validation gate — grounding accuracy, tier-routing accuracy, and adversarial/crisis-trigger testing — before it's allowed to serve real users.

**Every time a user talks** (runtime, same order, every single turn):
1. The turn arrives and is transcribed if spoken.
2. A two-tier cache is checked first — exact-match, then semantic — to avoid a full retrieval-and-generation cycle on repeat or near-duplicate questions. This is the primary cost-control mechanism in the system.
3. On a cache miss, the knowledge base is retrieved, confidence-scored.
4. Silent triage reads the turn for severity signal — this and the next step run on **every** turn, cache hit or not.
5. The safety interlock independently evaluates for crisis/risk language and can force an escalation regardless of anything else happening in the pipeline.
6. A prompt is assembled from persona, retrieved passages, and a trimmed recent history (not the full transcript) and sent to the LLM, which composes the natural-language reply — deciding *how* something is said, never *what* or *whether* it's safe to say.
7. The output is checked for grounding, then streamed back as voice, text, and/or avatar.
8. The turn is fully audit-logged, and the session's summary/mood tag is persisted to inform the next conversation.

Depending on the assessed tier, the user either continues in self-care (Tier 1/2) or is routed toward a practitioner (Tier 3) or an immediate crisis flow, with a human alerted.

---

## 5. Why RAG, not a custom-trained or freely-prompted model

A custom-trained model requires large volumes of data and significant GPU investment, and is effectively its own separate project. RAG gets a working, fully-controllable product live fast: the knowledge base is entirely owned and editable by the clinical team, every response is traceable to a source passage, and the system only pays for inference, not training. Every RAG conversation is logged, which means the platform is quietly building the exact dataset a future custom model would need — RAG is the first step toward that future capability, not a detour from it.

---

## 6. Language approach: bilingual by design, phased rollout

**Phase 1 ships English only.** This isn't because Hindi is an afterthought — it's a deliberate risk-reduction choice: prove the conversation, triage, and safety interlock work correctly in one language before adding the complexity of a second one. Every stored record and logged row carries a `language` field from day one specifically so Phase 2 doesn't require a schema migration — adding Hindi later is additive, not a rebuild.

**Phase 2 adds Hindi** by translating the existing knowledge base once, offline (never live, per-query — that would add cost and latency to every single turn), embedding both language versions into the same shared index, and hand-authoring the Hindi/Hinglish crisis vocabulary directly with the clinical team rather than machine-translating it. The runtime pipeline itself doesn't change — the same models already handle both languages; the LLM simply replies in whatever language the user just used, independent of which language the retrieved passage happened to be stored in.

---

## 7. Model and provider choices, and the reasoning behind them

| Capability | Primary choice | Why |
|---|---|---|
| LLM (generation) | Sarvam-M | Built specifically for Indian languages and Hinglish tone; materially cheaper than importing a Western model for the same job |
| Embeddings | Sarvam | Same reasoning — needs to understand Hindi and English equally well |
| Speech-to-text | Deepgram | Best balance of latency and accuracy on Hindi + code-switched Hinglish |
| Voice (TTS) | Sarvam TTS (Bulbul) | Natural Hindi voice at a fraction of premium alternatives' cost |
| Avatar | 2-D character (Rive/Live2D) | Every realistic rendered avatar charges a render fee on top of voice — the 2-D option has none, so it costs the same as voice-only |
| Fallback benchmark | GPT-4o-mini / Claude Haiku, OpenAI embeddings, ElevenLabs | Tested at the technology review as the comparison point, not the default |

None of these are permanent commitments — the provider-abstraction layer exists specifically so any of them can be swapped based on what the pre-launch evaluation actually shows, not assumed in advance.

---

## 8. Cost-control approach

Three layers, in order of impact: **(1)** the two-tier cache, which avoids the LLM call entirely wherever possible — the single biggest cost lever in the system; **(2)** provider choice, favoring Sarvam's India-first pricing over premium Western defaults; **(3)** a set of smaller engineering levers — trimmed context windows, incremental re-ingestion (only changed knowledge-base content gets re-embedded), rule-based (not model-based) safety checks, per-user rate limits, and compressed audio transport. Avatar rendering specifically is opt-in and cost-gated, since it's the most expensive component in the system by a wide margin when using a realistic rendered face.

---

## 9. Roadmap and phasing

- **Phase 1**: English-only launch — full conversational companion, triage, safety interlock, self-care, journaling, practitioner booking. Built compliant with DPDP (India's Digital Personal Data Protection Act) from day one — consent capture, data residency in India, encryption, access control, and audit logging.
- **Phase 2**: Hindi added on top of the same architecture, per Section 6.
- **This is a DPDP-compliant platform, not a HIPAA-compliant one** — no U.S. health-data regulatory regime applies here. Don't introduce HIPAA-specific requirements (BAAs, U.S.-specific de-identification standards, U.S. breach-notification timelines) into this project; they belong to a different regulatory context entirely.

---

## 10. How this fits with the other reference files

- **This file** — the whole picture: what the project is, why it's shaped this way, how the pieces connect.
- **`CLAUDE.md`** — hard implementation rules derived from this approach: exact pipeline order, what must never be skipped, storage conventions, what not to do.
- **`LATENCY.md`** — performance-specific guidance for meeting the real-time target without compromising anything in `CLAUDE.md`.

When these three files ever seem to disagree, the safety principles in Section 2 above win — nothing in this project trades safety for speed, cost, or convenience.

---

*Prepared as the primary project-context reference — derived from the finalized Mindfully Yours architecture (OpenXcell Technolabs Pvt. Ltd. / Mindfully Yours Private Limited). Keep this file, `CLAUDE.md`, and `LATENCY.md` in sync if any decision here changes.*
