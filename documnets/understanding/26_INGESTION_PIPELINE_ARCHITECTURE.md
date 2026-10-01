# 26. Ingestion Pipeline Architecture — How the Client's Data Became a Searchable Knowledge Base

## Purpose

This document explains how every doctor-written file the client provided was turned into a
structured, searchable database — the foundation everything else in this project is built on. It
covers **ingestion only** (raw files → database), not how the AI later retrieves and uses that data
in a live conversation, which is documented separately.

## 1. The architecture, end to end

<!--DIAGRAM:ingestion-pipeline-->

## 2. What happens at each stage

**Stage 1 — Raw client files.** 21 distinct files across two drops: 6 original clinical
spreadsheets (signals, symptoms, red flags, routing rules, severity thresholds, fallback logic) and
15 files from a September 2026 drop (layer/depth question banks, emotion phrasing, scenario and
career data, self-help material). Formats: CSV, Excel-derived CSV exports, and Word documents —
some password-protected, one built entirely from image-style text boxes rather than normal
paragraphs.

**Stage 2 — Structure-aware parsing.** Each file gets its own dedicated parser, because each one is
laid out differently — some are clean spreadsheets, some mix tables and headings in a single Word
document, one is built from Microsoft Word's drawing-canvas feature instead of plain text. A shared
parsing toolkit handles the common problems (Windows-1252 encoding instead of UTF-8, forward-filling
labels that were only written once per group, walking documents in their real reading order rather
than paragraphs-then-tables).

**Stage 3 — Cleaning & validation.** Real spreadsheet exports carry real mess: instructional
template rows left behind by the client's form, duplicated content from Word's internal rendering
quirks, missing values that could silently corrupt data if handled carelessly. Every file was
checked against its own real structure — not assumed — before being trusted.

**Stage 4 — Chunking.** For every file received so far, the client's own structure already *is* the
right chunk boundary — one spreadsheet row, or one paragraph under a heading, is already one
complete, self-contained idea. No AI is used to decide how to split content; that's reserved for
future prose-style content that isn't pre-segmented, which hasn't arrived yet.

**Stage 5 — Embedding.** Specific fields — never a whole record — are converted into a numeric
"fingerprint" (an embedding) that captures meaning, not exact wording, using OpenAI's
`text-embedding-3-small` model. This is what later lets the system recognize *"I feel like I have
nothing left to give"* as the same idea as a differently-worded example in the database.

**Stage 6 — Structured storage.** Everything lands in one PostgreSQL database with the `pgvector`
extension enabled — plain columns (IDs, categories, real text) and the numeric fingerprint sitting
in the very same row, the same table. There is no separate "vector database" to keep in sync.

**Stage 7 — Versioning & safe rollout.** Every ingestion run creates a new, clearly labeled version
(`building` → validated → `live`), so a knowledge-base update can be tested before it ever reaches
a real conversation, and rolled back cleanly if something's wrong with it.

## 3. The real numbers

| | Count |
|---|---|
| Source files ingested | 21 |
| Database tables populated | 15 |
| Total rows stored | 8,513 |
| Rows with a real vector embedding | 8,294 (97%) |

| Table | Rows | What it holds |
|---|---|---|
| `kb_scenarios` | 2,809 | Real-life situation phrases |
| `kb_tier_question_bank` | 1,413 | Follow-up questions per scenario/career topic |
| `kb_layer_content` | 1,512 | Conversational-depth question/statement bank |
| `kb_emotion_phrases` | 1,276 | Real first-person emotion phrasing |
| `kb_career_lookup` | 500 | Career → field/stream reference |
| `kb_signals` | 285 | Clinical warning signs |
| `kb_sufficiency_patterns` | 195 | "How much evidence is enough" thresholds |
| `kb_symptoms` | 154 | Physical/emotional symptom descriptions |
| `kb_clarification_phrases` | 115 | "I'm not sure, let me ask" phrases |
| `kb_fallback_scenarios` | 99 | What to do when a conversation goes off-script |
| `kb_routing_rules` | 66 | Deterministic severity-routing rules |
| `kb_anxiety_situations` | 35 | Anxiety topic coverage checklist |
| `kb_red_flags` | 31 | Danger phrases + safety scripts |
| `kb_guardrail_rules` | 18 | Parenting-concern urgency rules |
| `kb_content_chunks` | 5 | Self-help tools (DBT skills) |

## 4. A concrete, worked example

**Before (one raw spreadsheet cell):**
```
flag_id: RF-001
trigger_phrases: "he overtook me on the road, so i followed him to beat him up" | (4 more)
clinical_meaning: aggressive behaviour and irritability/violence risk
immediate_action: Tier 3 + SOS flag
escalation_target: Psychiatrist + crisis review
```

**After ingestion (one database row, `kb_red_flags`):**

| Column | Value |
|---|---|
| `flag_id` | `RF-001` |
| `trigger_phrases` | the 5 phrases, as real text |
| `trigger_embedding` | `[0.0231, -0.114, 0.442, ...]` — 1024 numbers |
| `clinical_meaning` | `"aggressive behaviour and irritability/violence risk"` |
| `escalation_target` | `"Psychiatrist + crisis review"` |

Nothing about the row's real content changed — the embedding is simply one more column sitting
alongside it, in the same table, in the same database.

## 5. Quality and reliability measures taken

Every one of the 21 files was inspected directly against its own real structure before a parser was
written for it — not assumed from a template. This surfaced and fixed several real, previously
undiscovered issues along the way: hidden template-instruction rows in spreadsheet exports that
looked like real data, a Word document built entirely from image-style drawing objects rather than
normal text, duplicated content from a rendering quirk in one workbook, and column names containing
a typographic dash character that a first-pass parser missed by one character — each confirmed
against the live file and corrected before being trusted.

## 6. Honest scope — what's not in here yet

- **Phase III/IV self-care and psycho-education content** (beyond the 5 DBT skills already
  ingested) has not been received from the client yet — this is a content gap, not an ingestion
  limitation.
- **~20 style/tone example conversations** (Bucket 1 content) are deliberately *not* part of this
  pipeline — they're meant to teach the AI's tone directly, not be searched, and are handled
  separately.
- **3 files remain password-locked** with a different password than the rest of the September drop.
- **A small number of files** (a couple of self-help worksheets, one inconsistently-formatted
  conversation file) are reviewed and catalogued, but don't yet have a dedicated parser.
