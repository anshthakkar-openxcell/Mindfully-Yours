# 03 — Tech Stack & Vendor Choices

> Full vendor detail, synthesized from `APPROACH.md`/`CLAUDE.md` and cross-checked against the three Phase 1 architecture PDFs (`Mindfully_Yours_Phase1_Final.pdf`, `Mindfully_Yours_Phase1.pdf`, `Mindfully_Yours_Phase1_English_Architecture.pdf`). **The three PDFs disagree with each other on a few vendor details — those disagreements are called out explicitly below and in [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md); don't silently pick one without flagging it.**

## 1. Application layer

| Layer | Technology | Notes |
|---|---|---|
| Mobile client | Flutter | iOS + Android, full feature parity with web |
| Web client | Next.js / React | Full feature parity with mobile |
| Backend | NestJS | REST APIs, auth, RBAC, orchestration — the layer between clients and the AI service |
| AI service | Python / FastAPI | Isolated deployable — RAG harness, conversation layer, triage, safety interlock |

## 2. Data spine

| Component | Technology | Used for |
|---|---|---|
| Primary datastore | PostgreSQL + pgvector | Structured/relational data AND embeddings, in one store — not two separate databases |
| Cache / session store | Redis | Two-tier cache, session state, working memory — **not** for anything that must survive a cache eviction |
| Config store | (Postgres-backed, per architecture PDF) | Persona prompt, interlock rule set — versioned, clinical sign-off required |

## 3. AI provider stack (behind the provider-abstraction layer — see [02_ARCHITECTURE.md](02_ARCHITECTURE.md) §2)

| Capability | Primary vendor | Confirmed by | Notes |
|---|---|---|---|
| LLM (generation) | **Sarvam-M** | All 3 architecture PDFs, `APPROACH.md`, `CLAUDE.md` | Built for Indian languages + Hinglish tone; materially cheaper than importing a Western model |
| Embeddings | **OpenAI (`text-embedding-3-small`)** — see discrepancy below | All 3 PDFs name Sarvam; **confirmed wrong** by checking Sarvam's live model list + API reference directly (Sept 2026) | **Discrepancy, now resolved in code**: the source PDFs all say "Sarvam" for embeddings, but Sarvam has no embeddings product at all (no `/embeddings` endpoint anywhere in their docs). `app/providers/embeddings/` now implements OpenAI's `text-embedding-3-small` instead — already the documented fallback/benchmark option below, so this promotes an already-vetted vendor rather than introducing a new one. Requests `dimensions=1024` to match the already-migrated `Vector(1024)` columns rather than the model's native 1536. **This is a real vendor substitution and needs the client's written sign-off per [12_SECURITY_COMPLIANCE_DPDP.md](12_SECURITY_COMPLIANCE_DPDP.md) Clause 2.8 before it touches real user data** — fine for dev/test today. Switching vendors later still means a full re-embed of the whole KB either way (see [07_INGESTION_PIPELINE.md](07_INGESTION_PIPELINE.md) §3). |
| Speech-to-text (STT) | **Deepgram** — see discrepancy below | All 3 PDFs list Deepgram; 2 of 3 also list Sarvam as a joint/secondary STT option | **Discrepancy**: `Phase1_Final.pdf` and `Phase1.pdf` label the runtime STT step "Deepgram/Sarvam" (dual vendor); `Phase1_English_Architecture.pdf` lists **Deepgram only**, dropping Sarvam from both the runtime step and the abstraction-layer service box. This looks like the more recent, committed direction, but confirm with the client before hardcoding a single-STT-vendor assumption — see [15_OPEN_QUESTIONS_AND_BLOCKERS.md]. |
| Voice (TTS) | **Sarvam TTS (Bulbul)** | All 3 PDFs, `APPROACH.md` | Natural Hindi voice at a fraction of premium alternatives' cost |
| Avatar rendering | **See discrepancy below** | Differs across the 2 earlier PDFs vs. the Final/Architecture PDFs | **Discrepancy — this is the more material one.** `Phase1.pdf` (earlier draft) uses **Spatius.ai** as an all-in-one lip-sync/avatar-video vendor paired with Sarvam TTS audio, with NO cost/plan opt-in gate (only falls back on provider outage). `Phase1_Final.pdf` and `Phase1_English_Architecture.pdf` (later) both use **HeyGen (or a 2-D fallback)** instead, and add an explicit **opt-in + cost/plan gate** as a precondition before rendering at all — i.e., avatar only renders if the user has opted in AND the plan/cost gate passes AND the provider is healthy. `APPROACH.md`'s own stated preference is actually a **2-D character (Rive/Live2D)**, specifically because it avoids the per-render fee a realistic rendered avatar (like HeyGen or Spatius.ai) charges on top of voice. **Net: there are three different avatar approaches named across the source material (Spatius.ai / HeyGen / Rive-Live2D 2-D) — this must be resolved explicitly at the technology review, not assumed. See [15_OPEN_QUESTIONS_AND_BLOCKERS.md].** |
| Fallback/benchmark LLM | GPT-4o-mini, Claude Haiku | All 3 PDFs (as "fallback benchmark") | Comparison point from the technology review, not a default |
| Fallback/benchmark embeddings | OpenAI embeddings | `APPROACH.md` | Comparison point only |
| Fallback/benchmark TTS | ElevenLabs | `APPROACH.md` | Comparison point only |

## 4. Real-time transport

| Component | Technology | Notes |
|---|---|---|
| Real-time media transport | **LiveKit** (WebRTC-based) | Replaces an earlier Agora/Daily/Twilio shortlist named in the signed business proposal — a well-justified change, but must be explicitly communicated to the client as a technology-review recommendation, not silently swapped in. Full detail: [10_LIVEKIT_REALTIME.md](10_LIVEKIT_REALTIME.md). |
| Voice pipeline SDK | LiveKit Agents framework | Handles voice-activity detection, turn-taking, barge-in/interruption — don't hand-roll this |
| Recording | LiveKit Egress → S3 | Only for practitioner and SOS calls, never every AI Companion turn |

## 5. Newly discovered vendors (from the architecture PDFs — not previously documented in the markdown files)

These appear **only** in the "Provider adapters" line of the AI Abstraction Layer section across all three architecture PDFs, with no further elaboration anywhere else in the source material:

- **Razorpay** — payments vendor. No further detail given (what's being paid for — subscriptions? practitioner session fees? — is not specified anywhere in the source material). Flagged in [15_OPEN_QUESTIONS_AND_BLOCKERS.md].
- **Onfido** — identity/KYC verification vendor. No further detail given (whose identity is being verified — practitioners during onboarding? users for age/identity checks? — is not specified). Flagged in [15_OPEN_QUESTIONS_AND_BLOCKERS.md].

## 6. Infrastructure

| Component | Choice | Why |
|---|---|---|
| Cloud region | **AWS ap-south-1 (Mumbai)** | DPDP data-residency requirement + latency (co-location with Sarvam/Deepgram endpoints avoids cross-region hops on every turn) |
| Encryption | Field-level encryption for clinical content; standard encryption in transit/at rest everywhere else | Per `CLAUDE.md` §9 and the architecture PDF's storage callout |

## 7. What is explicitly a configuration decision, not an architectural commitment

Per the provider-abstraction principle ([02_ARCHITECTURE.md](02_ARCHITECTURE.md) §2), **every vendor named above except the transport/framework choices (LiveKit, NestJS, FastAPI, Postgres+pgvector, Redis, Flutter, Next.js)** is swappable behind its adapter interface, pending:
1. A pre-launch evaluation re-run (accuracy) — per `CLAUDE.md` §7.
2. A latency re-benchmark (performance) — per `LATENCY.md` §11.
3. The client's prior written consent — per the signed agreement, Clause 2.8 (see [12_SECURITY_COMPLIANCE_DPDP.md](12_SECURITY_COMPLIANCE_DPDP.md) §2).
4. A confirmed no-training/no-retention tier for that vendor before any real data touches it — per Clause 5.7 (see [12_SECURITY_COMPLIANCE_DPDP.md](12_SECURITY_COMPLIANCE_DPDP.md) §1).

---
*Source material: `documnets/approch/APPROACH.md` §7, `documnets/approch/CLAUDE.md` §7, and full extraction of `Mindfully_Yours_Phase1_Final.pdf`, `Mindfully_Yours_Phase1.pdf`, `Mindfully_Yours_Phase1_English_Architecture.pdf` (all three architecture PDFs under `documnets/approch/`). See [15_OPEN_QUESTIONS_AND_BLOCKERS.md] for every vendor discrepancy requiring client clarification.*
