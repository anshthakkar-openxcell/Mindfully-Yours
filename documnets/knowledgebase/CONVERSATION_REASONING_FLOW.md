# Mindfully Yours — RAG Storage Structure & Conversation Reasoning Flow

Companion reference to `APPROACH.md`, `CLAUDE.md`, `LATENCY.md`, `INGESTION.md`, `LIVEKIT.md`, `DATA_PROTECTION_SECURITY.md`, and `KNOWLEDGE_BASE_CONTENT.md`. That last file decided *what* gets stored and *how it's chunked*. This file explains *why it's structured that way* by walking through what actually happens, turn by turn, when a real conversation runs — because the storage design only makes sense once you see the flow it's built to serve.

---

## 1. The key realization this whole file is built on

**Not every question this data answers is a retrieval question.** Some of it is a lookup, some of it is a rule, and only some of it is genuinely "search for the most relevant thing." Treating all of it as one big RAG problem is what leads to an over-complicated, slower, less accurate system. There are three different retrieval *mechanisms* at play, not one:

| Mechanism | Used for | Why |
|---|---|---|
| **Deterministic rule lookup** | Deciding which tier a detected pattern belongs to | The mapping from signals to tier is fixed and precise — this is exactly what `Kb_Phase_I_9.csv` already encodes; searching for it would be slower and less reliable than just looking it up |
| **Direct ID-linked fetch** | Getting the natural-language probing/exit guidance for a pattern once its tier is known | Once the rule lookup identifies "Mood Disorders -> Persistent Loneliness -> Tier 2," there's exactly one matching guidance chunk -- no need to search for it, just fetch it by its linked ID |
| **Genuine semantic RAG search** | Selecting a self-care exercise, psycho-education content, or clinical guidance that fits the specific situation | This is the one place where "which of many possible things best matches what the user just said" is a real, fuzzy question -- this is what vector similarity search is actually for |

---

## 2. What gets stored, and its structure

### 2a. The deterministic rules table (not the vector database -- a structured lookup table)

One row per pattern, derived directly from `Kb_Phase_I_9.csv`:

```
category            e.g. "Mood Disorders"
pattern_name        e.g. "Persistent Loneliness"
tier                1 | 2 | 3
minimum_signals     [signal codes]   -- BLOCKED until the client provides the code legend
must_have_signals   [signal codes]   -- BLOCKED until the client provides the code legend
confidence_rule     plain-English threshold description
tie_breaker_logic   what to do when two tiers look equally likely
graceful_exit_trigger   the specific evidence combination that ends probing
linked_chunk_id     -- points to 2b below
```

This table is queried by code, not by embedding similarity -- it's read the same way you'd read any configuration table.

### 2b. The retrievable guidance chunks (the vector database)

One chunk per pattern, linked back to the row above by `linked_chunk_id`:

```
chunk_id
category, pattern_name, tier    -- same tags as 2a, used for filtering
language                        -- 'en' for Phase 1
content_type                    -- "probing_guidance" | "psycho_education" | "self_care_tool"
text                            -- the natural-language guidance itself
embedding                       -- vector for semantic search (only meaningfully used for
                                    content_type = psycho_education / self_care_tool;
                                    probing_guidance is usually fetched by ID, not searched)
source_document
```

### 2c. What does NOT go in the vector database at all

- **Clinical Markers Reference Table** -- lives in the triage system prompt, always present, every turn. Ten items is small enough to never need retrieval; it needs to always be fully visible to the model doing the reading.
- **Knowledge_Base_Directory** -- internal build documentation, never reaches the AI at runtime.
- **Convo_Samples.pdf, in full** -- a curated subset lives as few-shot examples in the conversation-layer prompt; the rest is a held-out evaluation set, not something retrieved live during a real conversation.

---

## 3. The turn-by-turn flow -- how a question gets asked at the right time

This is the part that actually answers "how do we know what to ask next."

**Step 1 -- Signal reading.** On every turn, the model reads the user's message against the Clinical Markers (always in the prompt) to notice *which kind* of thing is happening -- is this about Safety, Emotional State, Functional Impact, etc. This is the coarse read.

**Step 2 -- Running understanding, not a fresh guess each turn.** The system keeps an accumulating state for the conversation -- which signals have been observed so far, how many turns have passed, whether duration and impact have been established yet. This is what makes the AI feel like it's actually listening across the whole conversation instead of reacting to just the last message. Each turn *updates* this state; it doesn't start over.

**Step 3 -- Safety interlock, always, independently.** Regardless of everything above, the deterministic interlock scans the raw text for crisis/red-flag language on every single turn. This never depends on the accumulated understanding from Step 2 -- a red flag on turn 1 routes immediately, even with no other context gathered yet, exactly as `Kb_Phase_I_9.csv`'s Tier 3 rows show ("Immediate -- do not wait for full picture").

**Step 4 -- Sufficiency check.** Using the deterministic rules table (2a), check whether the accumulated signals meet the minimum/must-have threshold for a tier decision on the closest-matching pattern. Three outcomes:
- **Not enough yet** -> go to Step 5.
- **Threshold met** -> go to Step 6 (route).
- **Graceful exit trigger hit** -> go to Step 6 immediately, even if the threshold technically isn't "complete" -- this is exactly what the exit-trigger field exists for.

**Step 5 -- This is literally where the "right next question" comes from.** The rules table's `linked_chunk_id` points to a guidance chunk (2b) that says, in plain language, what to probe next -- e.g., "ask about the intensity, duration, and present coping; enquire if they've sought therapy before." This chunk is fetched by direct ID, not searched for, since the pattern is already known from Step 4. The LLM turns that guidance into an actual, warm, naturally-phrased question -- using the Convo_Samples style examples in the prompt to get the tone right, not to copy a script verbatim. Then the conversation continues from Step 1 on the next turn.

**Step 6 -- Route and recommend.** Once a tier is decided:
- **Tier 1** -> stays in self-care conversation. *This* is where genuine semantic RAG search happens -- the system searches the psycho-education/self-care content (2b, once Phase III/IV content is received) for what actually fits the specific concern just understood, and the LLM recommends a specific exercise grounded in what was retrieved.
- **Tier 2** -> practitioner suggestion and booking flow, per the existing architecture.
- **Tier 3** -> immediate SOS routing, per `CLAUDE.md`'s safety rules -- no further probing.

---

## 4. Why this design answers the original question directly

- **"Ask the appropriate question at the right time"** -> Step 5, driven by the deterministic rules table's probing guidance for whichever pattern is closest to what's been observed so far -- not a generic "tell me more" every time.
- **"Understand the context"** -> Step 2's running state, accumulated across turns, not recomputed from scratch each time.
- **"Ask follow-up questions"** -> the natural consequence of Step 4 returning "not enough yet" -- the system knows exactly what's missing (which must-have signals aren't confirmed) and Step 5 asks specifically about that gap.
- **"Understand the whole situation"** -> the combination of Steps 2 and 4: signals accumulate, and the sufficiency check is evaluated against the *whole* pattern, not a single message.
- **"Give exercises and other recommendations"** -> Step 6's Tier 1 path, where semantic RAG search is actually used for what it's good at -- matching a specific concern to the most relevant self-care content, once that content exists in the KB.

---

## 5. What's still blocking full implementation of this flow

Per `KNOWLEDGE_BASE_CONTENT.md`, two things are missing before this can run for real:

1. **The `SIG`/`EM`/`PHYS` code legend** -- without it, Steps 1 and 4 have no way to translate what a user says into the codes the rules table (2a) actually checks against.
2. **Phase III (Clinical Guidance, Psycho-education) and Phase IV (Self-help tools) content** -- without it, Step 6's Tier 1 recommendation step has nothing to search yet.

Until both arrive, this flow can be built and tested structurally, but not validated against real clinical content.

---

*Companion file to `APPROACH.md`, `CLAUDE.md`, `LATENCY.md`, `INGESTION.md`, `LIVEKIT.md`, `DATA_PROTECTION_SECURITY.md`, and `KNOWLEDGE_BASE_CONTENT.md` -- describes the runtime reasoning flow the storage structure in `KNOWLEDGE_BASE_CONTENT.md` is designed to serve. Update this file once the blocking dependencies in Section 5 are resolved.*
