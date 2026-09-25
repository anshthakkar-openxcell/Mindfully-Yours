# 02 — System Architecture

> Full detail on the four-layer architecture introduced in [01_PROJECT_OVERVIEW.md](01_PROJECT_OVERVIEW.md) §3. This is the layer diagram every implementation decision should be checked against.
>
> **Scope note**: this build is the **AI service (Python/FastAPI) layer only** — see [14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md](14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md). The Client Apps and NestJS Backend layers below are described in full because the AI service's API contract and correctness depend on understanding what calls into it and why — but building those two layers is out of scope for this effort.

## 1. The four layers, and why they're kept separate

```
┌─────────────────────────────────────────────────────────────────┐
│  CLIENT APPS                                                      │
│  - Flutter (mobile, iOS+Android)                                  │
│  - Next.js/React (web)                                            │
│  - Full feature parity between the two                            │
│  - Serves two roles: end users AND practitioners                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST (+ WebSocket for text chat,
                            │  LiveKit/WebRTC for voice+avatar)
┌───────────────────────────▼─────────────────────────────────────┐
│  BACKEND — NestJS                                                  │
│  - REST APIs                                                      │
│  - Auth, role-based access control                                │
│  - Orchestration between client apps and the AI service           │
│  - Practitioner booking, journaling, non-AI product features      │
└───────────────────────────┬─────────────────────────────────────┘
                            │ internal service call (HTTP/gRPC)
┌───────────────────────────▼─────────────────────────────────────┐
│  AI SERVICE — Python / FastAPI  (isolated, its own deployable)    │
│  - RAG harness (retrieval + prompt assembly)                      │
│  - Conversation layer (persona, history, running state)           │
│  - Silent triage (severity signal reading)                        │
│  - Safety interlock (deterministic, independent, cannot be        │
│    skipped — see 08_SAFETY_INTERLOCK_AND_TRIAGE.md)                │
│  - Provider-abstraction layer (LLM/STT/TTS/avatar/embeddings)      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│  DATA SPINE                                                        │
│  - PostgreSQL + pgvector — single store, relational AND embedding │
│    data together (not two separate databases)                     │
│  - Redis — session state, working memory, two-tier cache          │
└─────────────────────────────────────────────────────────────────┘
```

**Why the AI service is a separate deployable from the NestJS backend, specifically**: this is not a language preference (Python vs. TypeScript) — it's so the safety-critical logic (triage + interlock) has a clean architectural boundary. A bug, deploy, or outage in the main product backend (bookings, profile, journaling) should never be able to affect the safety interlock's ability to run, and vice versa. Keep this boundary intentional in every future refactor — don't let convenience pull triage/interlock logic into the NestJS backend "just this once."

## 2. The provider-abstraction layer — the single most load-bearing architectural decision

Every external AI capability — LLM, STT, TTS/voice, avatar rendering, embeddings — sits behind a common internal interface. Application code (retrieval logic, conversation orchestration, prompt assembly) calls **that interface**, never a vendor SDK directly.

```
Application code
      │
      ▼
[ LLMProvider interface ]  →  SarvamLLMAdapter  (primary)
                           →  OpenAI/AnthropicAdapter (fallback/benchmark)
[ STTProvider interface ]  →  DeepgramAdapter  (primary)
[ TTSProvider interface ]  →  SarvamTTSAdapter (Bulbul, primary)
                           →  ElevenLabsAdapter (fallback/benchmark)
[ EmbeddingProvider interface ] → SarvamEmbeddingAdapter (primary)
[ AvatarProvider interface ]    → Rive/Live2D 2-D renderer (primary)
```

Why this matters beyond "clean code":
- **It's a contractual requirement.** Clause 2.8 of the signed agreement requires the client's prior written consent before substituting or materially modifying any model/API/platform that could affect functionality, performance, or security. If the abstraction layer doesn't exist, a provider swap becomes a scattered, risky refactor instead of an adapter swap plus a sign-off. See [12_SECURITY_COMPLIANCE_DPDP.md](12_SECURITY_COMPLIANCE_DPDP.md) §2.
- **It's the entire cost/performance flexibility story.** None of the vendor choices in [03_TECH_STACK.md](03_TECH_STACK.md) are permanent commitments; they're the result of a technology review the client can revisit, and re-benchmarking is only cheap if adapters, not business logic, need to change.
- **Every provider swap must be re-evaluated, not assumed drop-in.** Both `CLAUDE.md` and `LATENCY.md` are explicit: re-run the pre-launch evaluation set (accuracy) and re-benchmark first-token latency (performance) before treating a new provider as production-ready — a provider swap is never a purely mechanical change.

**Implementation guidance**: define the interface contracts first (before writing any adapter) — e.g. `LLMProvider.generate(prompt, stream=True) -> AsyncIterator[str]`, `STTProvider.transcribe_stream(audio_chunks) -> AsyncIterator[PartialTranscript]`. Every adapter implements the same contract; nothing upstream of the interface should know or care which vendor is behind it.

## 3. Data flow for a single conversational turn (high level — exact sequence in 04)

```
User (voice/text/avatar)
   │
   ▼
Client app  ──(LiveKit Room, voice/avatar)──┐
   │                                         │
   └──(REST/WebSocket, text)─────────┐       │
                                     ▼       ▼
                              NestJS Backend  LiveKit Agent (server-side
                                     │         participant, see 10_LIVEKIT)
                                     ▼               │
                              AI Service (FastAPI) ◄──┘
                                     │
              ┌──────────────┬───────┼────────────┬───────────────┐
              ▼              ▼       ▼             ▼               ▼
        Cache (Redis)   Retrieval  Triage    Safety Interlock  Provider
        (2-tier)        (pgvector) (signal   (deterministic,   Adapters
                                    reading)  rule-based)       (LLM/TTS/STT)
              │              │       │             │               │
              └──────────────┴───────┴─────────────┴───────────────┘
                                     │
                                     ▼
                          Prompt assembly → LLM call → Output guardrail
                                     │
                                     ▼
                     Response streamed back (voice/text/avatar)
                                     │
                                     ▼
                    Audit log + session summary (async, non-blocking)
```

## 4. Roles served by the same client codebase

- **End users** — the primary consumer of the AI Companion, self-care content, journaling, and practitioner booking.
- **Practitioners** — licensed professionals who receive Tier 2 routing, conduct consultations (via LiveKit, see [10_LIVEKIT_REALTIME.md](10_LIVEKIT_REALTIME.md)), and likely see session summaries/transcripts (via the recording+transcription pipeline).
- Both roles share the same Flutter/Next.js codebases with full feature parity across mobile and web — role-specific screens/permissions are gated by the NestJS backend's RBAC, not by separate apps.

(An admin/clinical-ops role for managing the knowledge base, reviewing escalations, and running the ingestion validation gate is implied by the ingestion and audit requirements but not explicitly named in the source docs — flagged in [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md).)

## 5. The actual architecture diagram, as drawn in the source PDFs (12 numbered sections)

The three Phase 1 architecture PDFs (`Mindfully_Yours_Phase1_Final.pdf` being the primary reference — see [03_TECH_STACK.md](03_TECH_STACK.md) for version differences) render the whole system as one large diagram with 12 circled-numeral sections plus a Hindi/Hinglish decision panel. This is the client-facing version of the same architecture described in §1-4 above — reproduced here section-by-section since it's the closest thing to an official system diagram in the source material.

| § | Section | Key content |
|---|---|---|
| ① | User & Consent Setup | DPDP purpose-wise/versioned consent, profile & preferences (voice/text mode, language), user content (journal, voice notes), data rights (download/delete) |
| ② | KB Ingestion Pipeline (continuous) | Extract & normalize (⚠ flagged "Needs KB structure guideline" — see [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #22), tag concern/severity/language, store interlock trigger vocabulary, embed (Sarvam), vector index (Postgres+pgvector) |
| ③ | Status: Live | Small gate badge — "KB version validated, retrieval enabled," feeding from Ingestion into Storage/Runtime |
| ④ | Storage | Postgres+pgvector + Redis + config store + retention policy engine + session lifecycle (Live → Closed → Tiered → Shared); AWS ap-south-1, field-level encryption for clinical content |
| ⑤ | Pre-Launch Testing & Validation | Grounding/fidelity eval set, adversarial/injection tests, tier-routing validation (**"false negatives on high-risk = primary safety metric"** — the single most explicit KPI in any source document); gate flips KB version to Live only if all pass |
| ⑥ | Prompt & Persona Engineering | Persona/tone, prompt architecture (grounding + guardrails + history window), interlock rule set (versioned, clinical sign-off required), tier thresholds (clinical team config, not model weights); **"prompt is not visible or editable by any user or admin"** |
| ⑦ | Feedback & Incident Loop | Usage signal capture (read-only), KB gap/fallback reporting to clinical team, safety events routed to clinical ops escalation queue, root-cause & rollback to last approved version |
| ⑧ | Observability & Quality Monitoring | Quality metrics (grounding, fallback, tier accuracy), safety events (interlock evals, audit trail), cost & usage (token metering, cache hit-rate, cost per language), model regression checks |
| ⑨ | Runtime | The full 14-step turn sequence (matches [04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md) exactly) plus the tier-routing callout at its base |
| ⑩ | AI Abstraction Layer | "Every provider swappable behind this line" — common interfaces for LLM/STT/TTS-Avatar/Embeddings; adapters: Sarvam (primary, all 4), Deepgram(/Sarvam) for STT, GPT-4o-mini/Claude Haiku (fallback benchmark), **Razorpay, Onfido** (payments/KYC — named only here, see [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #20) |
| ⑪ | Additional Cost-Saving Levers | Trimmed context window, rule-based interlock, incremental re-ingestion, per-user rate limits, compressed audio — **explicitly marked as engineering recommendations, not yet client-confirmed scope** |
| ⑫ | Avatar Rendering | Opt-in, cost-gated, most expensive component — **vendor differs across PDF versions, see [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #8** |

**Diagram layout** (for anyone redrawing it): far-left column stacks ⑥ above ⑦ (with a rollback loop arrow between them and across to ⑧); center-left column stacks ①+② side by side at the top, then the ③ status gate, then ④ Storage, then ⑤ Validation, then ⑧ Observability at the bottom; center-right is one tall column holding all of ⑨ Runtime's 14 steps top-to-bottom; far-right stacks ⑩→⑪→⑫. A full-width Hindi/Hinglish decision panel runs along the bottom (see [13_LANGUAGE_PHASING.md](13_LANGUAGE_PHASING.md) §3). Dashed arrows specifically denote: Storage→Runtime (reads scoped data), Prompt Engineering→Runtime (loads governed prompt), and a bidirectional loop between Feedback & Incident Loop ↔ Prompt Engineering and ↔ Observability.

## 6. Deployment/region notes

- Primary infrastructure target: **AWS ap-south-1 (Mumbai)** — required both for DPDP data-residency compliance and for latency (co-locating with Sarvam/Deepgram endpoints avoids cross-region hops on every single conversational turn).
- If LiveKit Cloud (managed) is used instead of self-hosting, its exact data-residency region must be explicitly confirmed against ap-south-1, not assumed — see [10_LIVEKIT_REALTIME.md](10_LIVEKIT_REALTIME.md) §5.

---
*Source material: `documnets/approch/APPROACH.md` §3, `documnets/approch/CLAUDE.md` §§1,7, and full extraction of `Mindfully_Yours_Phase1_Final.pdf` / `Mindfully_Yours_Phase1.pdf` / `Mindfully_Yours_Phase1_English_Architecture.pdf` (§5 above). The §1-4 diagrams are original ASCII renderings synthesized from the markdown prose; §5 is a direct transcription of the PDFs' own 12-section diagram. Version-to-version differences between the three PDFs are tracked in [03_TECH_STACK.md](03_TECH_STACK.md) and [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md).*
