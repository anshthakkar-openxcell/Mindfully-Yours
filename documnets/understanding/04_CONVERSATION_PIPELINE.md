# 04 — Runtime Conversation Pipeline (exact turn-by-turn order)

> This is the single most important implementation reference in this folder. It merges the canonical 14-step pipeline from `CLAUDE.md` with the corrected "one-LLM-call" flow from `END_TO_END_RAG_APPROACH.md` and the reasoning detail from `CONVERSATION_REASONING_FLOW.md`. **Do not reorder these steps** — the ordering itself encodes the safety guarantee.

## 1. The canonical 14-step pipeline (every single turn, no exceptions)

```
 1. Turn arrives (user_id, session_id, consent check)
 2. Speech-to-text (if voice)
 3. FAQ / exact-match cache check
 4. Semantic cache check
 5. RAG retrieval (only on cache miss)
 6. Silent triage                      ── ALWAYS runs, even if 3/4 hit
 7. Safety interlock                   ── ALWAYS runs, independent of everything above
 8. Prompt assembly (persona + retrieved passages + trimmed recent history + summary
                      — never the full transcript)
 9. Token metering / rate-limit check
10. LLM call (phrasing only — never the safety decision, never the retrieved facts)
11. Output guardrail (grounding + protocol check)
12. Response streamed (voice/text/avatar, with barge-in handling)
13. Audit log (user, session, retrieved passages, which path served it, full trail)
14. Session close (summary + mood tag persisted, feeds next turn's context)
```

**The one rule that governs all of this**: caching (steps 3-4) exists to skip *retrieval and generation cost* — it must never skip *safety* (steps 6-7). A cache hit still runs triage and the interlock, with no exceptions, on every code path including error handling and retries.

## 2. The corrected, detailed version of steps 5-10 (from `END_TO_END_RAG_APPROACH.md`)

The above is the contract; this section is the actual mechanism that satisfies it, including the important "one LLM call, not two" correction that was made to an earlier design.

### Step A — Fast signal pre-filter (replaces naive keyword matching; NOT an LLM call)
The user's message is checked against the ~285 signal-code phrasings (`Kb_Phase_I_A1.csv`, see [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md)) using **embedding-based similarity match**, not plain keyword matching. This is a fast vector lookup, not a model generation call. Rationale: keyword matching misses indirect/differently-worded expressions of a signal ("I just feel so tired of everyone" vs. the literal word "lonely"); an embedding match catches paraphrase and indirection while staying cheap and fast. Output: a candidate pattern/category, or "no match yet."

### Step B — Running understanding (conversation state, carried across turns)
The conversation keeps accumulating state: which signal codes have been observed so far, how many turns have elapsed, whether duration/impact have been established. **Every turn updates this state — it never restarts from zero.** This state is what makes probing feel like it's actually listening across a whole conversation rather than reacting to the last message in isolation. Implementation note: this state needs to live somewhere fast (Redis, keyed by session_id) since it's read and written on every turn — see [11_DATA_MODEL_AND_STORAGE.md](11_DATA_MODEL_AND_STORAGE.md).

### Step C — Safety interlock (always, independently, non-LLM — this is pipeline step 7)
Runs on the raw text every single turn, regardless of everything else happening in Steps A/B. Deterministic, rule-based, fails safe. **Completely unaffected by cache hits, running state, or anything else in this document.** Built directly from `Kb_Phase_I_7.csv` (Red Flags) — both direct and disguised/indirect trigger phrases matter equally, since the client explicitly designed the red-flag list to catch indirect language, not just obvious statements. A red flag hit on turn 1 routes to Tier 3 immediately, even with zero other context gathered — "Immediate — do not wait for full picture," per the client's own Tier 3 rows. See [08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) for the full red-flag mechanism.

### Step D — Sufficiency check (a lookup, not an LLM call)
Using the deterministic rules table (`Kb_Phase_I_C11.csv` routing rules + `Kb_Phase_I_9.csv` sufficiency thresholds — see [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) and [06_SIGNAL_ENRICHMENT_PIPELINE.md](06_SIGNAL_ENRICHMENT_PIPELINE.md)), check whether accumulated signals meet the minimum/must-have threshold for the closest-matching pattern. Rules are evaluated in **`priority` column order (1 → 2 → 3), never `rule_id` order** — these genuinely diverge in the real data. Three possible outcomes:
- **Not enough yet** → go to Step E.
- **Threshold met** → go to Step F (route).
- **Graceful exit trigger hit** → go to Step F immediately, even if the threshold is technically incomplete — this is exactly what the exit-trigger field exists for.
- **(New branch, not in the original design) Insufficient/contradictory/disengaged, and staying that way** → route to the Fallback & Safety Net logic (`Kb_Phase_I_17.csv`) instead of either "keep probing" or "route now." See [08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) §4.

### Step E — The one LLM call (this is pipeline step 10)
The system hands the model, in a **single prompt, single generation**:
- the linked guidance chunk (fetched by ID from Step D's result — not searched for),
- the Clinical Markers Reference Table (always present),
- the recent conversation history (trimmed, not full transcript) + running summary,
- a few Convo_Samples-style examples for tone (few-shot, not verbatim script).

In one generation the model composes the actual next question. It is **not** separately "figuring out what's going on" and then "phrasing a reply" as two calls — the narrower, already-informed task of *phrasing the right question given what's already known* is what a single call handles reliably. If a processing gap is expected before the response is ready, a filler phrase plays first (see [09_LATENCY_AND_PERFORMANCE.md](09_LATENCY_AND_PERFORMANCE.md) §3 and the filler-phrase library extraction in [15_OPEN_QUESTIONS_AND_BLOCKERS.md]/PDF extraction).

**Why one call doesn't sacrifice accuracy, if built right**: the embedding pre-filter (Step A) already does most of the "understanding" work a second LLM call would have done, at a fraction of the latency cost. The single call's job shrinks to something narrow and reliable — compose the right question given a *known* pattern and *known* guidance, not simultaneously diagnose from scratch and phrase a response. The actual fix for the earlier accuracy concern was never "add a second LLM call" — it was "make the free, non-LLM pre-filter smarter" (embeddings instead of keywords).

### Step F — Route and recommend (this is where tier logic terminates)
- **Tier 1** → stays in self-care conversation. **This is the one place genuine semantic RAG search happens** — searching Phase III/IV content (psycho-education, self-care tools — not yet received from the client, see [15_OPEN_QUESTIONS_AND_BLOCKERS.md]) for what fits the specific concern, with the LLM recommending a grounded exercise.
- **Tier 2** → practitioner suggestion + booking flow.
- **Tier 3** → immediate SOS routing, no further probing, human alerted.

## 3. Three distinct retrieval *mechanisms* — do not treat this whole system as one big RAG problem

This is the key realization the whole storage design is built on. Not every question the KB answers is a "search for the most relevant thing" question:

| Mechanism | Used for | Why not the others |
|---|---|---|
| **Deterministic rule lookup** | Deciding which tier a detected pattern belongs to (`C11` rules, `9` thresholds) | The mapping is fixed and precise — searching for it would be slower and less reliable than reading it off a table |
| **Direct ID-linked fetch** | Getting the exact probing/exit guidance for a pattern once the tier logic has already identified it | Once the rule lookup resolves to one pattern, there's exactly one matching guidance chunk — fetch it, don't search for it |
| **Genuine semantic RAG search** | Selecting a self-care exercise / psycho-education / clinical-guidance passage that fits the specific situation (Tier 1, Step F) | This is the one place "which of many possible things best matches what the user just said" is a real, fuzzy question — what vector similarity is actually for |

Building all three as one undifferentiated "search the vector DB" system would be both slower (searching structured lookup data that should be a direct table read) and less accurate (treating precise deterministic logic as fuzzy).

## 4. Why this design satisfies every original conversational requirement

| Requirement | Satisfied by |
|---|---|
| "Ask the appropriate question at the right time" | Step E, driven by Step D's probing guidance for whichever pattern is closest to what's observed so far — never a generic "tell me more" |
| "Understand the context" | Step B's running state, accumulated across turns |
| "Ask follow-up questions" | The natural consequence of Step D returning "not enough yet" — the system knows exactly which must-have signal is still unconfirmed, and Step E asks specifically about that gap |
| "Understand the whole situation" | Steps B + D combined: signals accumulate, sufficiency is evaluated against the whole pattern, not one message |
| "Give exercises/recommendations" | Step F's Tier 1 path — genuine semantic RAG, once Phase III/IV content exists |

## 5. What still blocks a fully validated implementation of this exact flow

See [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) for the complete, current list. The two structurally important ones for this pipeline specifically:
1. **`EM` signal codes are confirmed missing** — every `EM:` reference in `Kb_Phase_I_9` and `Kb_Phase_I_C11` still points at an undefined code. Steps A and D cannot fully resolve any rule that depends on an `EM:` code until the client supplies that legend (same structure as `A1`: an ID, a concept, example phrasings).
2. **Phase III/Phase IV content (clinical guidance, self-care library) not yet received** — Step F's Tier 1 recommendation has nothing to semantically search yet. The pipeline can and should be built and tested structurally now; the Tier 1 recommendation quality can't be validated until this content arrives.

The flow can be fully built and structurally tested today using synthetic placeholder content for the two gaps above — do not block writing code on these arriving (see [12_SECURITY_COMPLIANCE_DPDP.md](12_SECURITY_COMPLIANCE_DPDP.md) for why synthetic data specifically, not real clinical content, belongs in any test/dev environment anyway).

---
*Source material: `documnets/approch/CLAUDE.md` §3-4, `documnets/flow/RAG/END_TO_END_RAG_APPROACH.md` (full), `documnets/knowledgebase/CONVERSATION_REASONING_FLOW.md` (full).*
