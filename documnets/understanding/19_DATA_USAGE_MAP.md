# 19 — Data Usage Map: Which File Feeds Which Part of the System

> **Purpose**: a single, permanent reference for implementation. Every real data source this project has received — the original 6 Phase I clinical spreadsheets and the September 2026 "convo data" drop — mapped to exactly one of three usage buckets, with the reasoning for that placement and the concrete mechanism that consumes it. Read this before writing any ingestion or prompt-assembly code — it answers "which table does this file become, and what touches it at runtime" in one place, so nobody has to re-derive it file-by-file.
>
> This document assumes familiarity with [04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md) (the runtime pipeline this feeds), [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) (Phase I sheet detail), and [18_NEW_CONVO_DATA_CATALOG.md](18_NEW_CONVO_DATA_CATALOG.md) (new-drop detail) — this file is the cross-cutting index over both, not a replacement for either.

## The one rule that decides everything below

Ask one question about any piece of content: **is it something a person might say, a real thing to hand back to them, or a number/rule the code just checks?**

| If it is... | It becomes... | It is never... |
|---|---|---|
| Real, varied human phrasing (something a user might say, or the AI's own tone/style) | **Bucket 1 or 2** — embedded for matching, or shown once as a style example | A hardcoded rule |
| A real exercise, script, or piece of guidance worth giving back to a user | **Bucket 2** — searched for and retrieved | Baked into the prompt permanently |
| A count, a threshold, a fixed decision sequence | **Bucket 3** — a code-level rule, checked directly | Embedded or searched at all |

## Bucket 1 — Teach the AI how to talk (style only; loaded once, never searched live)

| File (exact name) | Why it belongs here | How it's actually used |
|---|---|---|
| `Convo_Samples.pdf` | Real example conversations showing tone/pacing across common scenarios — the point is *how* it's said, not looking one up mid-chat | A curated subset becomes fixed few-shot examples inside the system prompt (see [17_PERSONA_AND_CONVERSATION_STYLE.md](17_PERSONA_AND_CONVERSATION_STYLE.md)); the rest is a held-out evaluation set, never live-retrieved |
| `Career and Academic Conversation - Samples.docx`, `Conversation Combinations - Tanisha.docx`, `Conversation Combinations- Anam.docx`, `Conversations - Anxiety .docx`, `Conversations - Depression.docx`, `ED/Eating Disorder - Third Person Reported.docx`, `Miscellaneous Conversations1.docx`, `18-9_Offline Woork Week 6.docx`, and the Tanisha/Ankita/Shreya weekly conversation-script files under `MYPL KB 7th Sept/` | Same reasoning as `Convo_Samples.pdf` — real dialogue showing tone, especially valuable because several of these reach genuine crisis moments the original sample file never did | Curate a fresh few-shot set from these (esp. the crisis-handling examples) and fold into the same persona prompt; the bulk becomes an expanded evaluation set |
| `Clinical Markers Reference Table (1).pdf` | Only 10 items, always relevant, needs to be visible on literally every turn — chunking/searching it would be solving a problem it doesn't have | Lives permanently in the triage system prompt, verbatim (see `app/safety/clinical_markers.py` in the backend) — never embedded, never a retrieval target |

## Bucket 2 — Search for it, then either match against it or hand it back

This bucket has **two different jobs** that must not be confused: **(a) matching** — figuring out what the user means — and **(b) recommending** — finding real content to give them. Both are "search," but the output is different.

### 2a. Matching (detecting what's going on — nothing is shown to the user directly)

| File (exact name) | Why it belongs here | How it's actually used |
|---|---|---|
| `Kb_Phase_I_A1.csv` (Signal Legend) — the `phrasings` column specifically | 285 signals, each with 5-10 real example phrasings — exactly the varied, real-world language a similarity search needs | Embedded; the user's message is compared against these embeddings to detect which clinical signal(s) are present (Step A of [04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md)) |
| `Kb_Phase_I_A2.csv` (Symptom Map) — the `how_described` column | Same reasoning as A1 — real phrasing worth matching against, for the 21 rows that genuinely have it (see [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) §3 for why the other 133 rows don't) | Embedded and matched the same way as A1 |
| `Kb_Phase_I_9.csv` (Signal Sufficiency) — the `pattern_name` field only | The *only* narrow case worth embedding on this sheet — a rough early guess at which of ~185 patterns applies, before the exact signal checklist takes over | Embedded; used for a first coarse match, then the exact minimum/must-have signal check (Bucket 3) takes over |
| `Kb_Phase_I_7.csv` (Red Flags) — the `trigger_phrases` column | Real examples, deliberately written to include disguised/indirect language — a genuine "does this match, by meaning" problem | Embedded with a deliberately *more permissive* match threshold than normal (see [08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) §4) — but see the special case below for what happens *after* a match |
| `PHASE II_ Emotion Associated user expression.docx`, `List of Emotions - Tanisha.docx`, and the `Pathway...` doc's emotion picklist — **once merged into one canonical list** (see §Blockers below) | Real first-person "I feel…" phrasing, meant to teach/pattern-match emotion detection | Embedded and matched against a user's message to tag which emotion is present |
| `List of Scenarios - Tanisha.docx`, `Anxiety Situations.docx` | Master scenario/topic taxonomies — matching "which life situation is this" is a real semantic-similarity problem, not a lookup | Embedded; used to route a conversation toward the right topic-specific question bank or conversation pattern |
| `Layer I Questions and Statments.docx`, `Layer II Question Bank.docx`, `Layer III.docx`, `PHASE II Layer I and IV Questions.docx`, `Layer 2 to 3 Transitions.docx` | These are a *menu* to select the single best-fitting phrase from, given the current conversational depth — a retrieval problem, not free generation | Embedded per layer; the pipeline picks the closest-fitting question/statement for "what layer are we in right now" and hands it to the LLM as phrasing material (never the LLM inventing the question from scratch) |

### 2b. Recommending (real content handed back to the user)

| File (exact name) | Why it belongs here | How it's actually used |
|---|---|---|
| `dbt-skills-workbook.docx` / `dbt-skills-workbook-simple.pdf` | A finished, ready-to-use DBT skills tool — literally the "self-care tool" content [04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md) Step F was designed to search for and previously had nothing to find | Chunked (one skill = one chunk), embedded, and genuinely semantically searched at Tier 1 — the one part of the whole system where full RAG search is used exactly as designed |
| `brain-dump-worksheets.pdf` | Same reasoning — finished, ready-to-hand-out content | Same mechanism as the DBT workbook |
| `SELF-HELP CONVERSATIONS.docx` (the toolkit half — Behavioral Activation, Time Management, Mindfulness/Grounding, Journaling, Tracking Worksheets sections) | Broadest single self-help asset received — real, usable exercises | Same mechanism; each named tool/worksheet becomes its own searchable chunk |
| Phase III/IV content in general, once the client's remaining gaps are filled (see [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #24) | This is the category Phase III (clinical guidance/psycho-education) and Phase IV (self-help tools) were always meant to populate | Same mechanism — this bucket grows as more finished content arrives |

## Bucket 3 — Becomes literal code logic (never text, never embedded, never searched)

| File (exact name) | Why it belongs here | How it's actually used |
|---|---|---|
| `Kb_Phase_I_C11.csv` (Routing Rules) | A fixed, precise signal-combination → tier mapping — searching for it would be slower and less reliable than reading it off a table | Loaded as a direct lookup table, evaluated strictly in `priority` column order (1→2→3), **never** `rule_id` order (see [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) §4) — `app/safety/routing.py` in the backend |
| `Kb_Phase_I_9.csv` (Signal Sufficiency) — every field except `pattern_name` (`minimum_signals`, `must_have_signals`, `confidence_rule`, `graceful_exit_trigger`) | Exact lookup criteria, checked once a candidate pattern is already known from Bucket 2a's coarse match | Read directly off the row matched in 2a — no second search |
| `Kb_Phase_I_17.csv` (Fallback & Safety Net) — the `trigger_condition` field | Describes the *conversation's own shape* (turn count, response length, confidence score) — not something a user says, so there's no phrase to search for | Evaluated as code against the running conversation state (Redis) every turn — `app/safety/fallback.py` |
| `Pathway For AI In Different Situations - Tanisha.docx` | This is, almost verbatim, a 15-step decision flow with explicit branches — the closest thing to pseudocode the client has produced | Becomes the actual control flow of `app/pipeline/orchestrator.py` — identify concern → categorize → safety check → assess emotion/severity → pick intervention → close. Its vocabulary (Severity buckets, the 22-item category list) still needs reconciling with the existing Tier/scenario systems first — see [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #23 |
| `Knowledge_Base_Directory` | Internal build-planning document only | Never reaches the AI at all — not ingested in any form |
| Filler-phrase library (`Mindfully_Yours_AI_Latency_Filler_Phrases.pdf`) | Selection is a rule match (situation type + expected gap length → category), not a meaning-based search | A lookup table in `app/pipeline/filler.py`, picked by rule, never embedded |

## Special case: exact-fetch content (a hybrid of Bucket 2's matching and Bucket 3's "no thinking allowed")

Some content is *found* via a Bucket 2a match, but the response itself must be used **word-for-word**, never paraphrased by the LLM — this is its own category precisely because getting it wrong is the single biggest safety risk in the system:

| File (exact name) | Field | Rule |
|---|---|---|
| `Kb_Phase_I_7.csv` (Red Flags) | `bot_script` | Matched via embedding (Bucket 2a), then fetched **verbatim** — the LLM is never called for this response. See [08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) §4 for the 4 flags (RF-028–031) that currently have no script at all and must hard-alert a human instead. |
| `Kb_Phase_I_17.csv` (Fallback & Safety Net) | `bot_script` | Same rule — fetched verbatim once a fallback scenario is confirmed by Bucket 3's code check. |

## What's explicitly NOT usable yet (don't wire these in)

| File (exact name) | Status | Why |
|---|---|---|
| `Career Conversation Sets 1.docx` | Not real variety | 1 conversation template mechanically repeated ~500 times with only a career-field name swapped — the underlying list of ~500 career names is the only reusable part |
| `Anam/Conversation Combinations- sleep.docx`, `Anam/Conversations Combinations- anxiety 3rd person.docx`, `Anam/Miscellaneous Conversations.docx` | Still password-locked | Didn't decrypt with the password used for the rest of the drop — need a second password from Anam |
| Paraphilic-disorder content in `List of Scenarios - Tanisha.docx` ("Fetishes" section) and the Week 2 conversation-script file | On hold | Needs an explicit clinical + legal governance decision before it goes anywhere near a live index — see [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #26 |
| `Conversations - Depression.docx`, `Conversations Combination ( Bipolar and Psychosis).docx`, `Shreya/Trauma Related Conversations.docx`, `Conversation Combinations- Life Transitions.docx`, `Ankita/Conversations around Parenting.docx` | Partially usable | Each has real, specific content gaps (missing scenarios, cuts off mid-file) — usable for what's actually there, but don't treat as complete; see [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #24 |

## Blockers this data-usage map depends on being resolved first

Before Bucket 2a's emotion-matching and Bucket 3's Pathway-as-code work can be built for real (not just structurally stubbed), these need a decision — full detail in [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md):
- **#23** — merge the three unreconciled emotion lists (19/9/11 labels) into one canonical taxonomy, and reconcile the new Severity (Mild/Moderate/Severe/Crisis) scale and 22-item category list against the existing Tier 1/2/3 and ~9-category systems.
- **#25** — standardize tier-labeling, since different clinical-team contributors used it inconsistently.

---
*Companion to [04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md), [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md), and [18_NEW_CONVO_DATA_CATALOG.md](18_NEW_CONVO_DATA_CATALOG.md). Update this table the moment a new file arrives or a blocker above is resolved — this is meant to be the one place a developer checks before deciding how to treat a new piece of content, not a snapshot to go stale.*
