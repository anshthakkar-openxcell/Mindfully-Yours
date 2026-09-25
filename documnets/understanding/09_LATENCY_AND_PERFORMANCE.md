# 09 — Latency & Performance

> Target: **1.5–2.5 seconds, end of user speech to start of response.** This is the hardest constraint in the system: real-time voice, with a safety layer that must never be rushed or skipped to save time. Every technique below respects that — none trade safety for speed.

## 1. Why this is uniquely hard here

- Voice-first — silence after speaking feels broken in a way a slow webpage doesn't.
- The person on the other end may be in real emotional distress — a laggy, robotic-feeling companion actively undermines the product's purpose.
- The pipeline has a safety layer (triage + interlock) that runs on **every turn, no exceptions** — so the goal isn't just "call the LLM fast," it's "call the LLM fast *and* run independent safety checks *and* stay within budget."

## 2. Where the time actually goes (roughly, in order of typical size)

1. **LLM generation** — usually the single biggest chunk, especially time-to-first-token.
2. **TTS / avatar rendering** — avatar adds a real extra stage on top of voice.
3. **Speech-to-text finalization** — small if streamed, large if waiting for a full utterance.
4. **Retrieval (vector search)** — small if indexed properly, meaningful if not.
5. **Triage + interlock** — should be near-zero if implemented correctly (rule-based, not model-based).
6. **Network hops** — every additional cross-region service call adds real time.

**Instrument every stage and measure — don't guess where the time is going.** Optimizing a stage that isn't the bottleneck wastes effort and can introduce risk for no benefit.

## 3. The single biggest lever: stream everything

Never wait for a complete output before sending something back:
- **STT**: process partial transcripts as they arrive; don't wait for end-of-utterance silence alone to start downstream work where safely possible.
- **LLM**: stream tokens as generated — the user starts hearing/seeing a response while the model is still generating the rest.
- **TTS**: start synthesizing from the first completed sentence, not the full response.
- **Avatar**: start rendering as soon as audio for the first chunk is ready.

Perceived latency is about *time to first meaningful feedback*, not total round-trip time — a response starting at 800ms that keeps streaming feels faster than one appearing whole at 1.8s.

## 4. The filler-phrase system — masking processing gaps naturally

This is the concrete mechanism the architecture PDFs call "latency masking": *"on a slower turn, brief natural filler phrases (e.g. 'let me think about that…', 'okay…') play while the real response is still being generated — so a moment of processing time never feels like a stall."* Extracted in full from `Mindfully_Yours_AI_Latency_Filler_Phrases.pdf`. **This library lives in application/response-generation logic, selected by situation type — never embedded, never an LLM decision.**

### Design principles (verbatim, 7 bullets from the source)
- Keep fillers natural and conversational.
- Match the language of the current conversation: English, Hindi, or Hinglish.
- Use empathy carefully in mental-health conversations; do not turn fillers into clinical claims.
- Vary phrases to reduce repetition and avoid a robotic experience.
- Use fillers only when there is actual latency or a conversational reason for a pause.
- Keep technical implementation details invisible to the user.
- Support graceful degradation and text fallback when real-time voice interaction is unavailable.

### The 13 phrase categories (representative examples — full lists live in the source PDF, safe to hardcode as a lookup table)

| # | Category | Count | Representative examples |
|---|---|---|---|
| 1 | Very short natural fillers | 14 | "Hmm…", "Okay…", "Right…", "Got it…", "One moment…" |
| 2 | Thinking / processing | 12 | "Hmm, let me think about that.", "Give me a moment to put that together." |
| 3 | Listening / acknowledging | 12 | "I hear you.", "I'm with you.", "That makes sense." |
| 4 | Empathetic pauses | 12 | "Yeah… that sounds like a lot.", "Let's take this one step at a time.", "You don't have to rush through this." |
| 5 | Information / RAG-style checking | 10 | "Let me check that for you.", "Let me find the most relevant information." *(never says "retrieval," "database," or "search")* |
| 6 | Longer-answer / organization | 10 | "Okay, there's a little to unpack here.", "Let's break this down together." |
| 7 | When the user's meaning is unclear | 8 | "Let me check that I've got this right.", "When you say that, do you mean…?" |
| 8 | Context switching / returning to a topic | 7 | "Okay, let's come back to that.", "Coming back to what you mentioned earlier…" |
| 9 | Hindi | 15 | "Haan, samajh raha hoon.", "Achha… ek pal.", "Theek hai, ek pal." |
| 10 | Hinglish | ~16-18 | "Haan, I get what you mean.", "Okay, ek minute, let me think.", "Thoda sochte hain." |
| 11 | Voice-specific micro fillers | 10 | "Hmm…", "Mm-hmm…", "Yeah…", "Right…" |
| 12 | Longer latency fillers (2-5+ sec) | 7 | "Give me just a moment while I think about that.", "I want to take a moment and give you a thoughtful answer." |

### Situation → style mapping (exact table from the source — implement as a direct lookup)

| Situation | Suggested style | Example |
|---|---|---|
| Very short delay | Micro filler | "Hmm…", "Okay…", "I see…" |
| Thinking | Natural processing phrase | "Let me think about that." |
| Listening | Acknowledgement | "I hear you.", "I'm listening." |
| Emotional conversation | Gentle empathetic pause | "Let's take a moment." |
| Information lookup | Natural checking phrase | "Let me check that for you." |
| Longer answer | Organization phrase | "Let's break this down together." |
| Unclear input | Clarification lead-in | "Let me make sure I understood you." |
| Hindi conversation | Hindi filler | "Haan, samajh raha hoon." |
| Hinglish conversation | Mixed-language filler | "Okay, ek minute, let me think." |
| Longer latency | Extended filler | "Give me just a moment while I think about that." |

### Phrases to NEVER surface to the user (implementation-leak risk)

Explicitly forbidden: *"I'm processing embeddings," "Searching the vector database," "Retrieving chunks," "Running the RAG pipeline," "The LLM is generating a response."* Use the natural equivalents above instead. **Note**: `Phase1_English_Architecture.pdf`'s footer omits the latency-masking callout that both other architecture PDFs include — treat the filler system as a required cross-cutting feature regardless of which architecture PDF is treated as canonical; it's directly specified in its own dedicated deliverable document.

## 5. Keep the safety layer fast by construction, not by rushing it

- The interlock is rule/keyword-based specifically because that's **both safer and faster** than a model call — deterministic pattern matching is milliseconds; an LLM call is hundreds of milliseconds at best.
- Never "speed up" the interlock by making it less thorough — if it's slow, fix the indexing/rule engine, not the rule list.
- Triage should be lightweight signal extraction, not heavy model inference.

## 6. Two-tier caching — the biggest opportunity to skip work entirely

The fastest request is the one that never hits the LLM at all.
- **Exact-match/FAQ cache**: near-zero latency, checked first.
- **Semantic cache**: catches near-duplicate turns, skips the LLM call.
- Cache lookups must themselves be fast — a real key-value store or indexed vector lookup with a single-digit-millisecond budget, never a linear scan.
- **A cache hit still runs triage and the interlock, no exceptions** (per [04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md)).

## 7. Reduce the work sent to the LLM

- Trimmed context window: recent turns + summary, not the full transcript.
- Retrieval quality over quantity: send the few passages that matter, not a stuffed context "just in case."
- Keep the system/persona prompt lean — a bloated static prompt adds fixed latency to every call.

## 8. Parallelize what doesn't have to be sequential

- Audit logging, session summary generation, mood tagging — none block the response; fire asynchronously.
- Retrieval and triage don't depend on each other's output — run concurrently if currently serial.
- Keep serial only where there's a real dependency (e.g., the interlock's decision genuinely must happen before deciding whether the LLM's response is even shown).

## 9. Infrastructure-level latency

- **Regional proximity**: host the AI service in the same region as primary providers (AWS ap-south-1 alongside India-based provider endpoints).
- **Warm, persistent connections**: keep STT/LLM/TTS connections open and reused — TLS handshake setup per-call is a real, avoidable cost.
- **First-token latency, not just quality**, should drive provider choice — the technology review should measure this directly.
- **Re-benchmark latency on any vendor swap** — don't assume parity just because model quality is comparable.

## 10. Mode-specific latency floors

- **Text** — fastest, no STT/TTS/rendering.
- **Voice** — adds STT+TTS but stays fast if both are streamed.
- **Avatar** — always has a slightly higher latency floor than voice-only, no matter how optimized — expected, not a bug, which is why avatar is opt-in and cost/latency-gated.

## 11. What to measure, continuously

- Per-stage latency, logged every turn, not sampled.
- **P50 vs. P95 vs. P99** — optimize for the tail, not just the average.
- Cache hit-rate over time — a dropping rate is often the earliest signal something upstream changed (e.g. a KB update shifted the query distribution).
- Latency broken down by language once Hindi ships — don't assume both languages perform identically.

## 12. What NOT to do

- Don't buffer a full LLM response before starting TTS.
- Don't run audit logging or summary generation synchronously in the response path.
- Don't "optimize" the safety interlock by trimming its rule set.
- Don't add a heavyweight step to the critical path without checking if it can run in parallel or async.
- Don't assume a provider swap is latency-neutral.

---
*Source material: `documnets/approch/LATENCY.md` (full), `documnets/approch/Mindfully_Yours_AI_Latency_Filler_Phrases.pdf` (full, verbatim extraction), and the "Latency masking" / "streaming at every stage" callouts in the architecture PDFs.*
