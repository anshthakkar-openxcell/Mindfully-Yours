# Mindfully Yours — Latency Optimization Guide

Companion reference to `CLAUDE.md`. This file exists because latency is the hardest constraint in this system: it's a real-time voice conversation, with a safety layer that must never be rushed or skipped to save time. Every technique below respects that — none of them trade safety for speed.

**Target: 1.5–2.5 seconds, end of user speech to start of response.**

---

## 1. Why this is the biggest problem, specifically here

- It's voice-first — silence after speaking feels broken in a way a slow webpage doesn't.
- The person on the other end may be in real emotional distress — a laggy, robotic-feeling companion actively undermines the product's entire purpose.
- The pipeline has a safety layer (triage + interlock) that runs on **every turn, no exceptions** — so it isn't just "call the LLM fast," it's "call the LLM fast *and* run independent safety checks *and* stay within budget."

---

## 2. Where the time actually goes — know this before optimizing

Rough contributors to end-to-end latency, roughly in order of typical size:

1. **LLM generation** — usually the single biggest chunk, especially time-to-first-token
2. **TTS / avatar rendering** — avatar adds a real extra stage on top of voice
3. **Speech-to-text finalization** — smaller if streamed, large if you wait for a full utterance
4. **Retrieval (vector search)** — small if indexed properly, meaningful if not
5. **Triage + interlock** — should be near-zero if implemented correctly (see Section 4)
6. **Network hops** — every additional service call across a region boundary adds real time

**Don't guess where the time is going — instrument every stage and measure it.** Optimizing a stage that isn't actually the bottleneck wastes effort and can introduce risk for no benefit.

---

## 3. The single biggest lever: stream everything

Never wait for a complete output before starting to send something back.

- **STT**: process partial transcripts as they arrive, don't wait for end-of-utterance silence detection alone to start downstream work where safely possible.
- **LLM**: stream tokens out as they're generated. The user should start hearing/seeing a response while the model is still generating the rest of it.
- **TTS**: start synthesizing audio from the first completed sentence, not the full response. Don't buffer the entire LLM output before starting voice synthesis.
- **Avatar**: same principle — start rendering as soon as audio for the first chunk is ready, not after the full utterance is synthesized.

Perceived latency is about *time to first meaningful feedback*, not total round-trip time. A response that starts in 800ms and keeps streaming feels faster than one that appears all at once at 1.8s, even if the second one technically finishes sooner.

---

## 4. Keep the safety layer fast by construction, not by rushing it

- The interlock is rule/keyword-based specifically because that's **both safer and faster** than a model call — deterministic pattern matching is milliseconds, an LLM call is hundreds of milliseconds at best.
- Never be tempted to "speed up" the interlock by making it less thorough. If it's slow, the fix is a better-indexed rule engine, not a shorter rule list.
- Triage should be lightweight signal extraction, not a heavy model inference step. If triage ever becomes a latency bottleneck, that's a sign it's been implemented as something heavier than it needs to be.

---

## 5. Two-tier caching: the biggest opportunity to skip work entirely

The fastest request is the one that never hits the LLM at all.

- **Exact-match/FAQ cache**: near-zero latency, checked first.
- **Semantic cache**: catches near-duplicate turns, skips the LLM call, still cheap.
- Cache lookups themselves must be fast — this only works if the cache index is properly indexed (don't implement the cache as a linear scan; use a real key-value store or indexed vector lookup with a tight latency budget of its own, e.g. single-digit milliseconds).
- **Reminder from `CLAUDE.md`**: a cache hit still runs triage and the interlock. Caching skips retrieval and generation, never safety.

---

## 6. Reduce the actual work sent to the LLM

- **Trimmed context window**: send recent turns + a summary, not the full conversation transcript. Smaller prompts process faster, in addition to costing less.
- **Retrieval quality over quantity**: send the LLM the few passages that actually matter, not a large stuffed context "just in case." More tokens in means more time before the first token out.
- Keep the system/persona prompt lean. A bloated static prompt adds fixed latency to every single call.

---

## 7. Parallelize what doesn't have to be sequential

Not everything in the pipeline needs to happen one-after-another:

- **Audit logging, session summary generation, mood tagging**: none of these need to block the response reaching the user. Fire them off asynchronously after (or during) response streaming, not before.
- **Retrieval and triage** don't depend on each other's output — if your implementation currently runs them strictly in series, check whether they can run concurrently.
- Only keep things serial where there's a real dependency (e.g., the interlock's escalation decision genuinely needs to happen before deciding whether the LLM's response is even shown — that one has to stay in order).

---

## 8. Infrastructure-level latency, not just application logic

- **Regional proximity**: host the AI service in the same region as your primary providers (e.g., AWS Mumbai alongside India-based provider endpoints) to avoid cross-region network hops on every call.
- **Warm, persistent connections**: keep connections to STT/LLM/TTS providers open and reused rather than establishing a new connection per request — connection setup (especially TLS handshakes) is a real, avoidable cost repeated needlessly if done per-call.
- **Provider choice should weigh first-token latency, not just quality or raw throughput.** A model that's slightly less capable but meaningfully faster to start responding may be the better real-time choice — this is exactly what the technology review should measure directly, not assume.
- **If a vendor is ever swapped for any reason (cost, quality, or availability), re-benchmark latency on that new vendor specifically** before treating it as production-ready. Don't assume latency parity between vendors just because the underlying model quality is comparable.

---

## 9. Mode-specific latency floors — set expectations accordingly

- **Text** is the fastest mode — no STT, no TTS, no rendering.
- **Voice** adds STT and TTS but stays fast if both are streamed properly.
- **Avatar** adds a real rendering stage on top of voice — it will always have a slightly higher latency floor than voice-only, no matter how well-optimized. This is expected, not a bug — it's why avatar is opt-in and cost/latency-gated rather than the default experience.

---

## 10. What to measure, continuously — not just once before launch

- Per-stage latency, logged on every turn, not sampled occasionally.
- **P50 vs. P95 vs. P99** — a system that's fast on average but has a long tail of slow outliers still feels broken to the users who hit that tail. Optimize for the tail, not just the average.
- Cache hit-rate over time — a dropping hit-rate is often the earliest signal that something upstream changed (e.g., a KB update shifted the query distribution).
- Latency broken down by language once Hindi is added in Phase 2 — don't assume both languages perform identically; measure them separately.

---

## 11. What NOT to do

- Don't buffer a full LLM response before starting TTS — stream sentence-by-sentence instead.
- Don't run audit logging or summary generation synchronously in the response path.
- Don't "optimize" the safety interlock by trimming its rule set — fix the indexing/implementation instead.
- Don't add a heavyweight step (e.g., a second model call) to the critical path without first checking if it can run in parallel with something else or asynchronously after the response.
- Don't assume a provider swap is latency-neutral — re-measure first-token latency specifically, not just overall quality, before treating a new provider as production-ready.

---

*Companion file to `CLAUDE.md` — derived from the finalized Mindfully Yours architecture (OpenXcell Technolabs Pvt. Ltd. / Mindfully Yours Private Limited). Keep both files in sync if either changes.*
