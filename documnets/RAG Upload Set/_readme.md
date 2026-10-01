# RAG Upload Set — exactly the 17 files that get embedded and put in the vector database

This folder is a filtered copy of **"2. Search And Match Or Recommend"** (plus one file borrowed
from bucket 3). It answers one narrow question: *if I'm setting up the vector database, which
files actually need to go in, and which don't?*

Not every file in bucket 2 qualifies. A file only belongs here if the ingestion code
(`backend/app/ingestion/`) actually turns one of its columns into a vector embedding stored in
Postgres/pgvector. Being "searchable content" isn't enough — it has to be *embedded* content.

## The 17 files, and exactly what each becomes

| File | Becomes this DB table | Embedded field |
|---|---|---|
| Kb Phase I(A1.csv | `kb_signals` | `phrasing_embedding` |
| Kb Phase I(A2.csv | `kb_symptoms` | `how_described_embedding` |
| Kb Phase I(7.csv | `kb_red_flags` | `trigger_embedding` |
| Kb Phase I(9.csv | `kb_sufficiency_patterns` | `pattern_name_embedding` (narrow — see note below) |
| Layer I Questions and Statments.docx | `kb_layer_content` | `text_embedding` |
| Layer II Question Bank.docx | `kb_layer_content` | `text_embedding` |
| Layer III.docx | `kb_layer_content` | `text_embedding` |
| Layer 2 to 3 Transitions.docx | `kb_layer_content` | `text_embedding` |
| PHASE II Layer I and IV Questions.docx | `kb_layer_content` | `text_embedding` |
| PHASE II_ Emotion Associated user expression.docx | `kb_emotion_phrases` | `phrase_embedding` |
| List of Emotions - Tanisha.docx | `kb_emotion_phrases` | `phrase_embedding` |
| List of Scenarios - Tanisha.docx | `kb_scenarios` | `phrase_embedding` |
| Questions For When AI Is Not Sure - Tanisha.docx | `kb_clarification_phrases` | `phrase_embedding` |
| Career Field & Stream Lookup.csv | `kb_career_lookup` | `career_name_embedding` |
| dbt-skills-workbook.docx | `kb_content_chunks` | `embedding` |
| Questions.docx | `kb_tier_question_bank` | `question_embedding` |
| Question Set - Career.docx | `kb_tier_question_bank` | `question_embedding` |

One note on `Kb Phase I(9.csv`: it normally lives in bucket 3 (it's mostly a deterministic
tier-threshold table, checked directly in code). It's included here too because *one* of its
columns — `pattern_name` — also gets embedded, so a short label ("Career Indecision", "Social
Withdrawal", etc.) can be matched against fuzzy user phrasing before the deterministic thresholds
take over. It genuinely belongs in both places at once; that's not a mistake.

## What's deliberately NOT in this folder, and why

- **Everything in bucket 1** ("Teach The AI How To Talk") — read once into the AI's fixed
  instructions at the start of a conversation. Never chunked, never embedded, never searched. It's
  not RAG content at all.
- **`Kb Phase I(C11.csv`, `Kb Phase I(17.csv`, `Parenting_Child Related.docx`** — pure rule/lookup
  tables (routing rules, fallback logic, parenting guardrails). Checked directly in code
  (`if severity >= 3: ...`), never turned into a vector.
- **`Anxiety Situations.docx`** — parsed and stored in `kb_anxiety_situations`, but that table has
  no embedding column at all. It's used as a coverage checklist, not a search target.
- **`brain-dump-worksheets.pdf`** — intended to become `kb_content_chunks` content eventually (same
  table the DBT workbook uses), but no parser has been written for it yet. Real gap, not embedded
  today.
- **`dbt-skills-workbook-simple.pdf`** — a plain-PDF duplicate of `dbt-skills-workbook.docx`'s same
  5 skills. The .docx is the one actually parsed; the PDF is a human-readable reference copy only.
- **`SELF-HELP CONVERSATIONS.docx`** — has inconsistent internal formatting (confirmed by direct
  inspection) that doesn't follow one reliable pattern, so it's flagged for a future LLM-assisted
  chunking pass instead of a hand-written parser. Not embedded today.

See `documnets/understanding/19_DATA_USAGE_MAP.md` and `21_NEW_CONTENT_INGESTION_PLAN.md` for the
full per-file reasoning this table summarizes.
