# 21 — New Content Ingestion Plan (the Sept 2026 convo-data drop)

> **This closes the gap identified on 2026-09-28**: "we know which bucket each file belongs to and what general technique applies, but nobody has written the specific 'here's exactly how to turn this docx into database rows' plan the way we did for the 6 sheets." This document is that plan for the new drop, at the same precision as [07_INGESTION_PIPELINE.md](07_INGESTION_PIPELINE.md) gave the original 6 sheets — and unlike that gap-identification, **this one comes with working, tested code**, not just a plan. Every structural claim below was confirmed by directly inspecting the real decrypted files with python-docx (not assumed from the earlier catalog pass) — see the docstrings in `backend/app/ingestion/parsers/` for the exact evidence behind each rule.

## 1. What's implemented, verified, and runnable today

| Source file(s) | Parser module | Target table | Verified row count |
|---|---|---|---|
| `Layer I Questions and Statments.docx` | `layer_content.parse_heading_based_layer_file(layer='I')` | `kb_layer_content` | 156 |
| `Layer II Question Bank.docx` | `layer_content.parse_layer_ii` | `kb_layer_content` | 576 |
| `Layer III.docx` | `layer_content.parse_heading_based_layer_file(layer='III')` | `kb_layer_content` | 515 |
| `Layer 2 to 3 Transitions.docx` | `layer_content.parse_heading_based_layer_file(layer='II-III')` | `kb_layer_content` | 81 |
| `PHASE II Layer I and IV Questions.docx` | `layer_content.parse_phase_ii_layer_i_and_iv` | `kb_layer_content` | 184 |
| `PHASE II_ Emotion Associated user expression.docx` | `emotion_banks.parse_phase_ii_emotion_expression` | `kb_emotion_phrases` | 884 (19 emotions) |
| `List of Emotions - Tanisha.docx` | `emotion_banks.parse_list_of_emotions_tanisha` | `kb_emotion_phrases` | 392 (9 emotions) |
| `List of Scenarios - Tanisha.docx` | `scenario_taxonomy.parse_list_of_scenarios` | `kb_scenarios` | 2,809 (18 categories, 270 flagged `pending_governance_review`) |
| `Anxiety Situations.docx` | `scenario_taxonomy.parse_anxiety_situations` | `kb_anxiety_situations` | 35 |
| `Questions For When AI Is Not Sure - Tanisha.docx` | `clarification_bank.parse_clarification_bank` | `kb_clarification_phrases` | 115 (16 categories) |
| `Parenting_Child Related.docx` (table 4 of 4 only) | `guardrail_rules.parse_guardrail_table` | `kb_guardrail_rules` | 18 |
| `Career Field & Stream Lookup.csv` | `career_lookup.parse_career_lookup` | `kb_career_lookup` | 500 |
| `dbt-skills-workbook.docx` | `self_help_tools.parse_dbt_skills_workbook` | `kb_content_chunks` (existing table, `content_type='self_care_tool'`) | 5 (one per DBT skill) |
| `Questions.docx` (6 of 9 scenarios — see §3) | `tier_question_banks.parse_questions_by_scenario` | `kb_tier_question_bank` | 698 open + 343 close-ended |
| `Question Set - Career.docx` | `tier_question_banks.parse_career_question_set` | `kb_tier_question_bank` | 372 |

Run it: `python -m app.ingestion.cli ingest-convo-data --convo-dir "documnets/knowledgebase/convo data/decrypted/MYPL - Mindfully Yours Work" --career-csv "documnets/The Real Useful Knowledge/2. Search And Match Or Recommend (Real Content)/Career Field & Stream Lookup.csv" --label convo-v1`

Every parser above was verified two ways: (a) run directly against the real decrypted files with exact row/section counts checked against expectations, and (b) every output dict constructed into its target SQLAlchemy model with zero field-name mismatches. Shared parsing utilities (the two trickiest heuristics) have unit tests with synthetic inputs at `backend/tests/unit/test_docx_common.py`.

## 2. The confirmed structural rules that make this possible (per-pattern, not per-file)

Five real `.docx` structures recur across this whole drop — every parser above is one of these five, not a bespoke one-off:

1. **Clean `Heading 1`-styled sections** (Layer I, Layer III, Layer 2-3 Transitions): iterate paragraphs, track the last-seen `Heading 1` text as the current section, collect subsequent paragraph text under it. Reliable, no heuristics needed.
2. **Zero heading styles at all** (Layer II, Questions For When AI Is Not Sure): every paragraph is `Normal`. Section boundaries are detected with `is_label_line()` — confirmed rule: a label is under 55 characters AND does not end in terminal punctuation (`. ? ! …`). **Do not use "doesn't end in `?`" alone** — confirmed to false-positive on real statement lines that end in a period instead.
3. **`Title`-per-item with a repeated-label artifact** (the two emotion-phrase files): each item (an emotion) is its own `Title`-style paragraph; a fixed boilerplate line and often a repeated copy of the label follow before the real content starts. Both stripped by exact string match, not a heuristic.
4. **Bold-line-marks-a-new-topic, within `Title`/`Heading 1` categories** (List of Scenarios): `paragraph.runs[0].bold` marks a new topic; an optional `"Scenario: ..."` line and a literal `"Example Statements"` marker are recognized and skipped; everything else is a phrase. **Documented simplification**: some sections have a third level of nesting (short non-bold sub-labels between topic and phrases) that this parser does not separate out — they end up stored as ordinary phrases. Not fixed, because detecting that third level reliably would need a fragile heuristic for very little added value.
5. **Paragraphs and tables interleaved in document order** (Questions.docx, Question Set - Career.docx): python-docx's `.paragraphs` and `.tables` are two separate flat lists with no ordering between them — `docx_common.iter_block_items()` is the standard recipe for walking the actual document body in order, which is required whenever a table's meaning depends on the paragraph immediately before it (a topic name, a "Close Ended Questions" marker).

One structure needed unusually heavy handling, documented in full in `self_help_tools.py`: `dbt-skills-workbook.docx` stores its text inside Word DrawingML text-box shapes, not normal paragraphs (python-docx's default walk finds ~21 paragraphs; the real content is ~900 word-level XML text nodes inside floating shapes). `docx_common.extract_all_paragraph_text()` walks the raw XML directly and reconstructs sentences; `docx_common.collapse_doubled_runs()` then removes a confirmed rendering artifact where entire multi-line groups repeat back-to-back. The cleaned result is chunked into its 5 real DBT skills using the document's own "page N of 6" footer markers — a reliable, non-heuristic boundary.

## 3. What's deliberately NOT parsed, and the exact reason for each

| File / section | Status | Why |
|---|---|---|
| 3 of `Questions.docx`'s 9 scenarios ("Friendship Issues", "Gender and sexuality", "Caregiver Issues") | **Not parsed — confirmed structurally different** | These 3 skip the `Heading 1` subsections and the "Close Ended Questions" marker that the other 6 scenarios use, going straight from the scenario title into tables. Matches the independently-documented finding that these 3 are "noticeably less developed." A second, dedicated parser function is needed for their shape — not built here to avoid a fragile catch-all that silently mishandles the other 6. |
| `Parenting_Child Related.docx`'s tables 1-3 (the `Questions \| Options` intake-question tables) | **Not parsed yet** | Lower priority than the Guardrail table (table 4, which is parsed). Same 2-column shape as the Guardrail table — extending `guardrail_rules.py` (or a sibling function) to cover these is mechanical, not blocked on anything; simply not done in this pass. |
| `Pathway For AI In Different Situations - Tanisha.docx` | **Intentionally not parsed — becomes code, not data** | Per [20_IMPLEMENTATION_STRATEGIES_AND_PIPELINE.md](20_IMPLEMENTATION_STRATEGIES_AND_PIPELINE.md) §4, this 15-step decision flow is the literal blueprint for `app/pipeline/orchestrator.py`'s control flow — a developer reads it once and writes code from it. There is no "turn this into database rows" step for this file, by design. |
| `SELF-HELP CONVERSATIONS.docx` | **Not parsed — confirmed inconsistent structure** | Direct inspection confirms this file mixes `Heading 3`, `Normal (Web)`, and a stray custom style name (`pdq2pg_selectionanchorcontainer`) — clear Google-Docs-paste artifacts with no single reliable pattern the way the DBT workbook's page markers provide. This is exactly the case [07_INGESTION_PIPELINE.md](07_INGESTION_PIPELINE.md) §2 step 2 reserves for LLM-based chunk-boundary refinement (Sarvam-M marks split points, never rewrites text) rather than a hand-written parser. Recommend running that technique on this file specifically once the embedding pipeline is live, rather than writing a fragile heuristic parser for a one-off messy file. |
| `dbt-skills-workbook-simple.pdf` | **Not separately parsed — redundant with the .docx version already ingested** | Confirmed same 5-skill content as `dbt-skills-workbook.docx`, just a plain fillable-PDF rendering. Useful as a literal downloadable asset to hand a user, not as separate searchable content. |
| `brain-dump-worksheets.pdf` | **Not ingested — served as a static asset, not searchable content** | A 2-page, mostly-blank fill-in-yourself worksheet (5 short section prompts, no real body text to search). There's nothing here for a semantic search to match against; the correct design is to let the AI attach/link this file directly when recommending it, not chunk-and-embed it. |
| The 3 still-locked Anam files | **Cannot be parsed** | Never decrypted — see [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #27. |

## 4. New database tables added

All in `backend/app/db/models/kb_convo_content.py`, registered in `app/db/models/__init__.py`: `kb_layer_content`, `kb_emotion_phrases`, `kb_scenarios`, `kb_anxiety_situations`, `kb_clarification_phrases`, `kb_career_lookup`, `kb_guardrail_rules`, `kb_tier_question_bank` — 8 new tables. Self-help tools deliberately reuse the **existing** `kb_content_chunks` table (already designed for exactly this purpose in the original schema) rather than adding a parallel one.

Two fields are worth calling out specifically:
- `kb_scenarios.pending_governance_review` (boolean) — `True` for every row from the "Fetishes" category (270 rows). **Application code must exclude these from any live retrieval index until the clinical + legal governance decision in [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #26 is made.** They are loaded, not dropped, specifically so nothing needs re-ingesting once that decision lands.
- `kb_emotion_phrases.canonical_emotion_group` (nullable string) — stays `NULL` until the three-way emotion-list merge happens (see §6 below and [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #23). Do not populate this as a guess.

## 5. A genuinely useful finding from building this: Layer II and Layer III share one 28-emotion list

Programmatically confirmed (not eyeballed): `Layer II Question Bank.docx`'s emotion-specific question bank and `Layer III.docx`'s emotion-specific reframing bank use the **exact same 28 emotion labels**, in the same order. This is more than the 23 an earlier summary pass estimated, and it's strong, ready-made evidence for what a merged canonical emotion list might already look like in the client's own materials — see the question list in §6.

## 6. Client questions this ingestion work surfaced (for the emotion/Tier/Layer/Severity reconciliation)

See the separate, non-technical question list already prepared for the clinical team — these are the exact same open items as [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #23, phrased for a non-technical audience rather than a developer.

---
*Source: direct python-docx/lxml inspection of every file in `documnets/knowledgebase/convo data/decrypted/`, cross-referenced against [18_NEW_CONVO_DATA_CATALOG.md](18_NEW_CONVO_DATA_CATALOG.md) and [19_DATA_USAGE_MAP.md](19_DATA_USAGE_MAP.md). Update §3's "not yet parsed" list as each remaining item is picked up.*
