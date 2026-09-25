# Mindfully Yours — Real-Time RAG System: Implementation Rules

This file is a reference for anyone (human or AI coding assistant) implementing the AI conversation pipeline. It captures decisions already made — don't re-derive or second-guess these without a real reason; they were chosen deliberately, often to satisfy a safety or cost constraint, not out of preference.

---

## 1. What this system is

A real-time, voice/text/avatar conversational AI for a mental-wellness app. A user talks; the system retrieves grounded knowledge, silently assesses risk, generates a natural reply, and — completely independently of the AI — can force a safety escalation. This is not a generic chatbot. Safety correctness matters more than conversational cleverness anywhere the two conflict.

---

## 2. The non-negotiable rule, above everything else

**The safety interlock is never skipped, never bypassed, and never delegated to the LLM.**

- It is rule/keyword-based, not a model call — deterministic, same input always produces the same output.
- It runs on **every single turn**, including turns served entirely from cache.
- It can force an escalation regardless of what retrieval or the LLM would otherwise produce.
- It fails **safe, upward** — on timeout, low confidence, or a provider outage, it defaults to the more cautious path, never the more permissive one.
- Crisis/interlock vocabulary is **hand-authored by the clinical team**, never machine-translated, never inferred by a model.

If you're implementing a change and you're unsure whether it touches this layer — assume it does, and don't let a cache hit, a retry, or an error path route around it.

---

## 3. Runtime pipeline — exact order, every turn

```
1. Turn arrives (user_id, session_id, consent check)
2. Speech-to-text (if voice)
3. FAQ / exact-match cache check
4. Semantic cache check
5. RAG retrieval (only on cache miss)
6. Silent triage (ALWAYS runs — even steps 3/4 hit)
7. Safety interlock (ALWAYS runs, independent of steps above)
8. Prompt assembly (persona + retrieved passages + trimmed recent history + summary — not full transcript)
9. Token metering / rate limit check
10. LLM call (generates phrasing only — not the safety decision, not the retrieved facts)
11. Output guardrail (grounding + protocol check)
12. Response streamed (voice/text/avatar, with barge-in handling)
13. Audit log (user, session, retrieved passages, which path served it, full trail)
14. Session close (summary + mood tag persisted, feeds next turn's context)
```

Do not reorder steps 6–7 relative to caching. Caching exists to skip *retrieval and generation cost*, not to skip *safety*.

---

## 4. Caching rules

- **Two tiers**: exact-match/FAQ cache first (near-zero cost), then semantic cache (skips the LLM call on near-duplicate turns).
- A cache hit still passes through triage and the interlock. No exceptions.
- Cache keys should account for language — an English cache entry and a Hindi cache entry for the same underlying answer are different entries, not the same one with a translation layer bolted on.

---

## 5. Language handling

**Phase 1 ships English only. Design for Hindi from day one without building it yet:**

- Every stored chunk and every logged row carries a `language` field. Phase 1 sets it to `en` everywhere — don't skip the field because it's unused today.
- Do not hardcode English-only assumptions into the retrieval or prompt-assembly logic. When Hindi is added (Phase 2), it should be an additive row in the same tables, not a schema migration.
- When Hindi is added: the knowledge base gets translated **once, offline** (not translated live, per-query — that adds latency and recurring cost on every turn). The crisis/interlock vocabulary for Hindi/Hinglish is **hand-authored**, not machine-translated, for the same reason English vocabulary is hand-authored.
- The LLM always replies in whatever language the user used in that turn — this is independent of which language the retrieved chunk happened to be stored in. Don't build a separate "reply language" configuration; let the model's own instruction-following handle it.

---

## 6. Retrieval & knowledge base

- Retrieval is confidence-scored. Below-threshold matches should route to a safe, generic, pre-approved fallback — never let a low-confidence match get treated as grounded fact.
- Every chunk carries a `user_id` tag for isolation — one user's logged history must never leak into another user's retrieval context.
- Grounding is not optional: the output guardrail must verify the LLM's response is actually supported by what was retrieved, not just plausible-sounding.

---

## 7. Provider abstraction

- Every external AI service (LLM, STT, TTS/avatar, embeddings) sits behind a common interface. Application code calls the interface, never a vendor SDK directly.
- Current primary vendor: Sarvam (LLM, embeddings, TTS), Deepgram (STT). These are configuration, not hardcoded dependencies — a provider swap should never require touching business logic, only the adapter.
- When benchmarking or swapping a provider, re-run the pre-launch evaluation set before treating the new provider as production-ready. A provider swap is not a drop-in replacement until it's been measured.

---

## 8. Performance targets

- Target end-of-speech-to-response latency: **1.5–2.5 seconds**. Streaming (partial STT, streamed LLM output, streamed voice/avatar) is how this target is met — don't wait for a full response before starting to render/speak it.
- Graceful degradation ladder on provider trouble: **avatar → voice → text**. Never let an avatar/voice provider outage break the conversation entirely — always fall back a tier rather than failing the turn.
- If the model API itself is unavailable, the system falls back to an **interlock-only safe path** — i.e., safety detection keeps running even if generation can't.

---

## 9. Storage

- Single data spine: PostgreSQL + pgvector (structured data and embeddings together, not two separate databases).
- Redis for session state, working memory, and cache layers — not for anything that needs to survive a cache eviction.
- Field-level encryption for clinical content; standard encryption in transit and at rest everywhere else.
- Retention timers are independent per data type (transcript, audio, consent record, audit log) — don't apply one blanket retention policy to everything.
- DPDP-specific additions: consent is captured purpose-wise and versioned; users can request download or deletion of their data; data resides in AWS India (ap-south-1).

---

## 10. What NOT to do

- Don't let the LLM decide *whether* something is safe to say — that's the interlock's job, decided before the LLM is even called.
- Don't translate live, per-query, as the primary path for any language — it's slower and costs more than translating the source content once.
- Don't skip triage/interlock on any code path, including error handling, retries, or cache hits.
- Don't hardcode a provider's SDK into business logic — go through the abstraction layer.
- Don't treat a retrieved passage as ground truth without confidence scoring — low confidence means fallback, not a best-effort guess.
- Don't build Hindi support as a bolt-on later if it means a schema migration — the `language` field should already be there.

---

*Reference document for implementation — derived from the finalized Mindfully Yours architecture (OpenXcell Technolabs Pvt. Ltd. / Mindfully Yours Private Limited). Keep this file updated if a documented decision above changes — don't let code and this file drift apart.*
