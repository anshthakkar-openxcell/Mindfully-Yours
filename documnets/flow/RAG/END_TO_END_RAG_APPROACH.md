# Mindfully Yours — End-to-End RAG Approach (Final)

This is the single, consolidated reference for how the knowledge base is stored, chunked, and used in a real conversation — pulling together everything decided across `KNOWLEDGE_BASE_CONTENT.md`, `CONVERSATION_REASONING_FLOW.md`, `LATENCY.md`, and the one-LLM-call correction. Read this file first for the full picture; the others remain as detailed companion references for their specific topics.

---

## 1. The five documents received, and what each one is actually for

Not all of this is "knowledge base content" in the RAG sense. Some of it never touches the vector database at all.

| Document | What it is | Where it's used |
|---|---|---|
| **Clinical Markers Reference Table** | 10 observation categories (Speech, Safety, Emotional State, etc.) with definitions and lower/higher-concern examples | Lives permanently in the triage system prompt — never embedded, never searched |
| **Kb_Phase_I_9.csv** | The Tier 1/2/3 decision logic — 12 clinical categories, each with minimum/must-have signals, thresholds, tie-breaker logic, probing guidance, exit triggers | Split into two derived stores — see Section 2 |
| **Convo_Samples.pdf** | Real example conversations showing tone, pacing, and question style across common scenarios | A curated subset lives as few-shot examples in the prompt; the rest is a held-out evaluation set |
| **Knowledge_Base_Directory** | The table of contents for the whole KB, across four phases | Internal build-planning document only — never reaches the AI at runtime |
| **AI Latency Filler Phrase Library** | Natural filler phrases (English, Hindi, Hinglish) for masking processing gaps, organized by situation | Lives in the response-generation logic, selected based on expected gap length — never embedded either |

---

## 2. What gets stored, where, and in what structure

### 2a. The deterministic rules table — not the vector database

Derived from `Kb_Phase_I_9.csv`, one row per clinical pattern:

```
category                e.g. "Mood Disorders"
pattern_name             e.g. "Persistent Loneliness"
tier                     1 | 2 | 3
minimum_signals     [signal codes]   -- SIG and PHYS codes now defined (see `KNOWLEDGE_BASE_CONTENT.md` v2); EM codes still blocked
must_have_signals   [signal codes]   -- same status
confidence_rule          plain-English threshold description
tie_breaker_logic         what to do when two tiers look equally likely
graceful_exit_trigger     the evidence combination that ends probing
linked_chunk_id           points to 2b
```

Queried by code — a lookup, never a similarity search.

### 2b. The retrievable guidance chunks — the actual vector database

One chunk per pattern, linked back to 2a by `linked_chunk_id`:

```
chunk_id
category, pattern_name, tier    -- filtering tags
language                        -- 'en' for Phase 1
content_type                    -- "probing_guidance" | "psycho_education" | "self_care_tool"
text
embedding
source_document
```

`probing_guidance` chunks are mostly fetched by direct ID once a pattern is known (Section 2a already identifies which one). `psycho_education` and `self_care_tool` chunks (from Phase III/IV, not yet received) are the ones genuinely found through semantic search.

### 2c. What never gets stored as vector content at all

- Clinical Markers table — always-present prompt content, too small and too universally relevant to ever be conditionally retrieved.
- Knowledge_Base_Directory — internal documentation only.
- The full Convo_Samples set — prompt/eval asset, not searched live during a real conversation.
- The filler phrase library — selected by situation type and expected gap length in application logic, not retrieved by meaning.

---

## 3. Chunking technique — finalized, per document, with reasoning

| Document | Technique | Why |
|---|---|---|
| **Kb_Phase_I_9.csv** | **Structure-aware only — one row = one chunk, exactly as given.** No LLM-based re-chunking. | The client already segmented this perfectly; each row is one complete, self-contained pattern. Running it through an LLM chunker would solve a problem that doesn't exist and risks drifting from the clinical team's exact wording. |
| **Convo_Samples.pdf** | One full conversation = one chunk, split at the existing scenario/page breaks. Tagged by scenario category. | Splitting mid-conversation destroys the thing that makes this material useful — watching a question sequence unfold. The natural breaks are already scenario boundaries. |
| **Clinical Markers table** | Not chunked — used whole, as a single static block in the prompt. | Ten items, always needed together; chunking implies partial, conditional retrieval, which is the wrong access pattern here. |
| **Knowledge_Base_Directory** | Not chunked — not ingested at all. | Internal document, never reaches the AI. |
| **Filler phrase library** | Not chunked — structured as a lookup table by situation type (micro filler, thinking, empathetic pause, RAG-checking, Hindi, Hinglish, etc.), not embedded content. | Selection here is rule-based (match the situation and expected gap to a category), not a meaning-based search problem. |
| **Future Phase III/IV content (clinical guidance, self-care library)** | **This is the one case that will need LLM-based chunk-boundary refinement (Sarvam-M), per `INGESTION.md`'s general method.** | Unlike the above, this content is expected to arrive as flowing prose, not a pre-segmented table — the natural boundaries won't already exist, so the more expensive method earns its cost here. |

**The one-sentence rule underlying this whole table**: use the cheap, structure-respecting method whenever the source is already organized into complete units; reserve the LLM-based method for genuinely unstructured prose where the boundaries aren't given for free.

---

## 4. The end-to-end flow, corrected — one LLM call per turn, not two

This is the flow with the fix applied: signal detection is fast and non-LLM, and the single Hosted LLM call does all the actual composing.

**Step 1 — Fast signal pre-filter (not an LLM call).** The user's message is checked against the pattern signal codes using an **embedding-based similarity match**, not plain keyword matching. This is the upgrade from the earlier version of this design — keyword matching alone misses indirect or differently-worded expressions of a signal; an embedding-based match catches those while still being a fast vector lookup, not a slow LLM generation. This step narrows things down to a candidate pattern (or confirms none apply yet).

**Step 2 — Running understanding, carried across turns.** The conversation keeps an accumulating state — which signals have been observed, how long the conversation has run, whether duration/impact have been established. Each turn updates this; it never starts from zero.

**Step 3 — Safety interlock, always, independently, non-LLM.** Runs on the raw text every turn, regardless of everything else — deterministic, rule-based, fails safe. Unaffected by anything in this document.

**Step 4 — Sufficiency check (a lookup, not an LLM call).** Using the rules table (2a), check whether accumulated signals meet the tier threshold for the closest-matching pattern. Three outcomes: not enough yet (→ Step 5), threshold met (→ Step 6), or graceful exit triggered (→ Step 6 immediately).

**Step 5 — The one LLM call, doing everything it needs to in a single pass.** The system hands the model, in one prompt: the linked guidance chunk (fetched by ID from Step 4's result, not searched for), the Clinical Markers, the recent conversation history, and a few Convo_Samples-style examples for tone. In **one generation**, the model composes the actual next question — it isn't separately "figuring out what's going on" and then "phrasing a reply" as two calls; the narrower, already-informed task of *phrasing the right question given what's already known* is what one call handles well. If there's an expected processing gap before this response is ready, a filler phrase (Section 1, matched to the situation and gap length) plays first.

**Step 6 — Route and recommend.** Tier 1 stays in self-care conversation, and *this* is where genuine semantic RAG search happens — searching Phase III/IV content (once received) for what fits the specific concern, with the LLM recommending a grounded exercise. Tier 2 moves to the practitioner booking flow. Tier 3 triggers immediate SOS routing, no further probing, per `CLAUDE.md`.

---

## 5. Why one LLM call doesn't mean lower accuracy, if this is built right

The accuracy risk isn't really "one call vs. two" — it's what the model has to figure out unaided versus what's already been resolved for it before it's called at all.

- The embedding-based pre-filter (Step 1) already does most of the "understanding" work that a second LLM call would have done, at a fraction of the latency cost.
- The single LLM call's job shrinks to something narrower and more reliable: compose the right question given a known pattern and known guidance, not simultaneously diagnose the situation from scratch *and* phrase a response.
- The running state (Step 2) means the model isn't reasoning from zero each turn — only what's new gets added to an already-informed picture.
- The safety interlock (Step 3) is completely independent of any of this and carries none of this trade-off.

**The actual fix for the accuracy concern was never "add a second LLM call" — it's "make the free, non-LLM pre-filtering step smarter" (embeddings instead of plain keywords), so the one LLM call that does run has better material to work with.**

---

## 6. What's still blocking full implementation

**Major update: the client has now sent the full Phase I knowledge base** -- the signal legend, routing rules, red flags, and fallback logic, detailed fully in `KNOWLEDGE_BASE_CONTENT.md` v2. Most of what was blocked here is resolved.

1. ~~The `SIG`/`EM`/`PHYS` code legend~~ -- **`SIG` and `PHYS` are now fully defined** (285 signal codes in `Kb_Phase_I_A1.csv`, physical/emotional symptom mapping in `Kb_Phase_I_A2.csv`). **`EM` codes remain undefined** -- confirmed missing after checking the full legend, not just unfound. This is now the one real blocker on the rules table and the embedding-based pre-filter (Step 1).
2. **Phase III (Clinical Guidance, Psycho-education) and Phase IV (Self-help tools) content** -- still not received. Without it, Step 6's Tier 1 recommendation has nothing to search yet.
3. **Confirmation on the Convo_Samples usage question** -- whether they're a close script or a loose style guide, which affects how tightly Step 5's tone examples should be followed. Still open.
4. **New, resolved**: Red Flags (`Kb_Phase_I_7.csv`) and Fallback & Safety Net (`Kb_Phase_I_17.csv`) are now available with exact, client-authored bot scripts -- these should be used close to verbatim in Steps 3 and 5, not paraphrased by the LLM.

---

*Consolidated end-to-end reference. Companion detail lives in `KNOWLEDGE_BASE_CONTENT.md` v2 (document-by-document depth, now with the real signal/rules/red-flag structure), `CONVERSATION_REASONING_FLOW.md` (flow depth, pre-correction), `LATENCY.md` Section 4 (the filler phrase system in full), and `CLAUDE.md`/`APPROACH.md` (the architecture this all sits inside). Derived from OpenXcell Technolabs Pvt. Ltd. / Mindfully Yours Private Limited project materials. Update this file if the EM-code legend arrives, or if the one-LLM-call design changes.*
