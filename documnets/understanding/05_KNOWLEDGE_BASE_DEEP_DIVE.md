# 05 — Knowledge Base Deep Dive (every sheet, verified against the real files)

> This is the ground-truth reference for the actual client-supplied data. Every number and example below was extracted by directly parsing the real CSV/XLSX files (not estimated from the design markdown) — where the design docs' own estimates differ from what's actually in the files, that's called out explicitly. **Read this before writing any ingestion or parsing code** — several of the "expected" structures described in the design markdown turn out to be subtly wrong once you look at the real files.

## 0. Global data-quality facts that affect every parser you write

- **Encoding: all the raw CSV exports are Windows-1252 (cp1252), not UTF-8.** Reading them as UTF-8 turns every em-dash/apostrophe into `�`. Decode with `encoding='cp1252'` explicitly.
- **Every raw CSV is a "form template" export, not a clean table**: row 0 = sheet title, row 1 = PURPOSE, row 2 = HOW TO FILL instructions, sometimes an ESTIMATED TIME row, then the real header row, then sometimes an "instructions/example" row, and only then real data. A naive `pandas.read_csv()` will misparse every one of these files — locate the real header row per file (documented per-sheet below) before parsing.
- **Two files (`Kb Phase I(A1.csv` and `Knowledge Base Directory(Sheet1).csv`) are bloated Excel full-width exports** — up to 16,384 columns (Excel's max), with a fake generic `Column1...Column16384` header in row 0 before the real header in row 1. This is why `A1.csv` is 16MB for only 285 real data rows.
- **Trailing blank-row padding**: `Kb_Phase_I_9.csv`, `C11.csv`, `Kb_Phase_I_7.csv`, and `Kb_Phase_I_17.csv` are all padded with hundreds of fully empty rows at the end (e.g. file 9 has 765 trailing blank rows after row 280) — cosmetic Excel-export artifact, safe to trim, but will break a row-count assumption if not handled.
- **"First row of a group carries the label, continuation rows leave it blank"**: files 9 and 7 both use this spreadsheet convention (a Tier or Flag ID is written once, then left blank on subsequent rows belonging to the same group) — **must forward-fill during parsing or data will silently disappear.**
- **SIG/EM/PHYS code formatting is inconsistent across at least 5 distinct styles** in the raw text: `SIG: 001`, `SIG 001-017`, `SIG002-003`, `SIG-168`, unpadded `SIG: 1`. Any code that matches signal IDs must normalize aggressively (strip whitespace/hyphens/colons, zero-pad, handle both hyphen-ranges and word-ranges like "to").
- **`Kb Phase I(A2.csv` and `Kb Phase I(A2 (1).csv` were byte-for-byte identical** (verified via `diff` and matching md5 checksums) — the "(1)" file was a redundant duplicate, not a newer version, and has since been **removed from the repo**. `Kb Phase I(A2.csv` is the single copy going forward.

## 1. The master workbook (`Kb Phase I.xlsx`) — confirms what everything else is an export of

6 sheets, confirmed via `openpyxl`:

| Sheet name | Corresponds to CSV | Row/col size (raw, incl. export padding) |
|---|---|---|
| A1. Signal Library | `Kb Phase I(A1.csv` | 1001 rows × 16384 cols |
| A2. PhysicalEmotional Symptoms | `Kb Phase I(A2.csv` | 162 rows × 26 cols |
| C11. Routing Rules | `Kb Phase I(C11.csv` | 1005 rows × 23 cols |
| 7. Red Flags & Escalation | `Kb Phase I(7.csv` | 980 rows × 6 cols |
| 9. Signal Sufficiency | `Kb Phase I(9.csv` | 1045 rows × 8 cols |
| 17. Fallback & Safety Net | `Kb Phase I(17.csv` | 1030 rows × 7 cols |

The individual CSVs are direct exports of these 6 sheets (headers and first data rows verified identical). Each sheet's own "PURPOSE" row in the workbook is worth quoting since it's the client's own framing:
- **C11**: *"Explicit if/then rules determining which tier a user is routed to... Priority ordering matters — Rule 1 is applied first."* (Note: this framing is actually imprecise — as shown in §4 below, evaluation order is the `Priority` column, 1→2→3, not literal "Rule 1 first" by ID.)
- **Sheet 7**: *"The most clinically critical sheet. Defines phrases and patterns triggering IMMEDIATE escalation... Life-safety."*
- **Sheet 9**: *"How much evidence the AI needs before routing... tells the AI when to stop talking and start routing."*

## 2. `Kb_Phase_I_A1.csv` — Signal Library (the core signal legend)

**Exact columns (9)**: `Signal ID, Clinical Concept, Everyday Phrasings (5-10 examples), Emotional Tone Cues, Trajectory Cues (worsening/stable/improving), Clinical Category, MH Disorder, Severity Weight, Red Flag`

**Exact row count: 285** (`SIG-001` through `SIG-285`; last row is inconsistently cased `Sig-285`).

**Severity Weight is a 1-3 ordinal scale** (not an open numeric range as some design docs implied): `1: 8 rows, 2: 205 rows, 3: 67 rows`, 5 blank. Heavily skewed toward "2."

**Red Flag distribution** (raw values, casing not normalized in the source): `Yes: 136, No: 129, yes: 9, no: 4, blank: 7` → folding case: **145 Yes / 133 No / 7 blank**.

**Category distribution** (38 raw distinct strings due to inconsistent capitalization/multi-value newline-joined entries): Mood 43, Thought/action 35, Behaviour 27, Psychosomatic 20, Dissociation 17, Cognitive 16, Thought 16, "Behaviour - governed by emotion" 14, Medical/Psychological 10, Grief 8, Mood/Biological 6, Anxiety 4, Safety 3, Psychotic 3, Emotional 3, Biological 3, Sexual 3, Sleep 2, plus many small/compound categories (Anxiety+Cognitive combinations, etc.) and 7 blank.

**Representative sample rows** (verbatim):
- **SIG-001** Anhedonia | Mood | Sev 2 | Red Flag No — phrasings include *"Nothing feels fun anymore"*, *"Everything feels flat"*. MH: Major Depressive/Persistent Depressive/Premenstrual Dysphoric Disorder.
- **SIG-002** Suicidal ideation (passive) | Safety | Sev 3 | Red Flag Yes — trajectory cue: *"Any mention = immediate flag regardless of trajectory."*
- **SIG-044** Hallucinations (Auditory/Visual/Olfactory/Tactile/Command/Running commentary) | Psychotic | Sev 3 | Red Flag Yes | MH: Schizophrenia, Schizoaffective, Delusional, Brief Psychotic/Schizophreniform Disorder.
- **SIG-142** Chasing Losses | Behaviour | Sev 3 | Red Flag Yes | MH: Gambling Disorder — *"I lost fifty thousand in one evening and went back the next day to win it back, and lost fifty thousand more."*
- **SIG-258** Yearning and longing | Grief | Sev 2 | Red Flag No | MH: Prolonged Grief Disorder — *"I cook his favourite dal every Sunday without thinking, and then I sit at the table and he is not there."*

This is the primary embedding target described in [06_SIGNAL_ENRICHMENT_PIPELINE.md](06_SIGNAL_ENRICHMENT_PIPELINE.md) — the `Everyday Phrasings` column is exactly the varied, real-world language an embedding-based signal pre-filter needs to match against.

## 3. `Kb_Phase_I_A2.csv` — Physical/Emotional Symptom Map

**Exact columns (6)**: `Symptom ID, Physical/Emotional Symptom, How Users Describe It, Likely Emotional/Mental Root, Maps to Signal IDs, Distinguishing Cues (physical-only vs emotional root)`

**⚠ Major finding, corrects an assumption in the design docs**: this sheet's 154 rows are **not** all `PHYS-` rows. Breakdown by ID prefix:
- **`PHYS-` : 17 rows** (PHYS-001 through PHYS-017)
- **`PHSY-` : 4 rows** (PHYS-018 through 021, but typo'd as `PHSY-` — letters transposed, clearly meant to continue the PHYS series)
- **`EM-`/`EM ` : 133 rows** (EM-001 through EM-057 hyphenated; later rows drift to space-separated `EM 129`...`EM 133`)

**This resolves — and complicates — the "EM codes are missing" blocker described in the design markdown.** The 133 `EM-` rows in this sheet are *not* signal-style entries with an ID + concept + phrasings the way `A1`'s SIG codes are. Instead, their `Maps to Signal IDs` column contains **free-text category labels, not signal IDs**: e.g. `"Can be seen across all signals - but as a supporting signal"`, `"Motivation issue"`, `"Mostly a personality trait"`, `"Cognitive distortion"`, `"Situational difficulties"`, `"Intimacy concerns"`, `"Usually triggers by death"`. **Only the 21 real PHYS/PHSY rows have genuine `SIG-xxx` mappings.** This confirms — independently, from the raw data itself — what `KNOWLEDGE_BASE_CONTENT.md` v2 states as a blocker: *`EM:` codes referenced throughout `Kb_Phase_I_9` and `Kb_Phase_I_C11` point at something that has no proper ID+concept+phrasings legend anywhere in the KB.* The 133 EM rows in `A2` are the closest thing that exists, but they're categorical labels, not a signal legend structured like `A1`.

**Verbatim examples of `Maps to Signal IDs` format inconsistency** (relevant to the parser in [06_SIGNAL_ENRICHMENT_PIPELINE.md](06_SIGNAL_ENRICHMENT_PIPELINE.md)):
- `PHYS-001 → "SIG-044, SIG-045"` (clean comma list)
- `PHYS-003 → "Sig 004, 005, 006, 007, 001, 023, 152,155, 156, 193,"` (lowercase "Sig," prefix only on first number, trailing comma, inconsistent spacing)
- `PHYS-004 → "SIG-041-043"` (hyphenated range)
- `PHYS-005 → "SIG-085 to 093"` (word-form range)
- `PHYS-016 → "Can be seen across all signals - but as a supporting signal"` (no explicit IDs at all, even on a PHYS- row)
- `EM-005 → "Motivation issue"`, `EM-023 → "Usually triggers by death"` (typical EM-row category-label style)

## 4. `Kb_Phase_I_C11.csv` — Routing Rules

**Exact columns (7 populated of 23 raw)**: `Rule ID, Trigger Condition (plain English), Logical Expression (dev-filled, blank for every row), Route To, Override Reason, Trajectory Factor, Priority`

**Exact row count: 66**, matching the design docs' estimate.

**Priority distribution (exact, confirmed)**: Priority 1 = **33 rows**, Priority 2 = **25 rows**, Priority 3 = **7 rows**, **no priority set = 1 row (`Rule-025`)**. 33+25+7+1 = 66. ✓

**⚠ ID-casing inconsistency**: `RULE-001` through `RULE-014` use uppercase `RULE-XXX`; from `RULE-015` onward the format silently switches to title-case `Rule-XXX` for the rest of the file. **Any exact-string-match lookup keyed on `"RULE-"` will silently miss 52 of the 66 rules.** Normalize case before matching.

**Concrete examples where priority order and rule_id order genuinely diverge** (confirms the design docs' warning with real data):
- RULE-001 (prio 1) → RULE-002 (prio 2) → RULE-003 (prio 2) → **RULE-004 (prio 1)**: RULE-004 fires before 002/003 despite the higher ID.
- Rule-041 (prio 1) → Rule-042 (prio 2) → **Rule-043 (prio 1)**: Rule-043 evaluates before Rule-042.
- Rule-062/063 (prio 2) vs. **Rule-064/065 (prio 1)**: 064/065 evaluate first despite higher IDs.
- **All priority-3 rules** (Rule-056 through Rule-061, and Rule-066 — the "Life Transitions," "Interpersonal skills," "identity/self," "Existential Crisis," "career/financial/job," "motivation," "grow and improve self" catch-alls, all routing to Tier 1) sit in the high-50s/60s of ID order but are meant to fire **last** of all 66 rules.

**`Rule-025` — the one incomplete rule**: Trigger = *"For Factitious Disorder, SIG 080, 271-277."* — has **no Route To, no Override Reason, no Trajectory Factor, no Priority**. Exclude from the rules engine until the client completes this row.

**Sample rows**:
- `RULE-001`: Trigger = *"For Major Depressive Disorder (SIG002-003), no other signal required"* → Route: `Tier 3` → Override: *"N/A — any red flag overrides everything"* → Priority `1`.
- `RULE-002`: Trigger = *"For Major Depressive Disorder primary signals (from SIG 001-017), Minus (SIG002-003). At least 5 or more of these should be present at least for 2 weeks"* → Route: `Tier 2 (escalate)` → Priority `2`.
- `RULE-007`: Trigger = *"For Social Anxiety Disorder, primary features involve SIG-168 to 171, EM-001, EM019, PHYS-013... Sig 171 and EM-019 is only for public speaking or performance in public."* → Priority `2`. (Note this rule references `EM` codes directly — one more confirmation that `EM` codes are load-bearing throughout the routing logic, not a peripheral concern.)
- `Rule-056`: Trigger = *"For Life Transitions, EM45 to 54"* → Route: `Tier 1` → Priority `3`.

## 5. `Kb_Phase_I_7.csv` — Red Flags

**Exact columns (6)**: `Flag ID, Trigger Phrase Examples (5+), Clinical Meaning, Immediate Action, Bot Script (verbatim), Escalation Target`

**Exact row count: 31** (`RF-001` through `RF-031`), matching the design docs' estimate.

**Trigger-phrase count per flag is highly inconsistent** — RF-016/017/022/024 have 17-21 examples each; **RF-011, RF-012, RF-018, RF-019, RF-020 each have effectively only 1** (either a single long narrative paragraph, or ~8 phrases crammed onto one unbroken quote-separated line, not one-per-line). This is a **formatting inconsistency, not a real content gap** — a naive per-line parser would wrongly conclude these flags are under-specified. Handle all three formats (newline-separated, quote-mark-separated, single paragraph) when parsing.

**⚠ Critical real gap — see also [08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) §4**: **RF-028, RF-029, RF-030, RF-031 have completely empty Bot Script cells.** These cover *Suspected violence/unsafe environment*, *History of violence*, *Suspected rape*, *Sexual molestation* — some of the most sensitive categories in the sheet. **RF-020 also has an empty Escalation Target** (Clinical Meaning "Psychotic Feature," Action "Tier 3," but no named escalation destination).

**Verbatim samples**:
- **RF-001**: *"he overtook me on the road, so i followed him to beat him up"* / *"they tried to remove me from the project, so made sure they all failed"* → Clinical Meaning: *"aggresive behaviour and irritability/violence risk"* → Action: `Tier 3 + SOS flag` → Bot Script: *"It sounds like things have been really intense lately — feeling that level of frustration or anger can be exhausting. This is something a therapist can really help with. Would you like me to connect you with one?"* → Escalation: `Psychiatrist + crisis review`.
- **RF-018** (passive suicidal ideation): phrases include *"I wish I hadn't woken up"*, *"Everyone would be better off without me"*, *"I don't feel like being here any more"*, *"I want to be dead / I hope I die."* → Bot Script: *"Thank you for trusting me with this. Feeling like you don't want to be here anymore is serious, and you deserve real support. Please reach out to a therapist or a crisis line — I can help you find one right now."*
- **RF-028** (suspected violence/unsafe environment): *"My partner gets really angry with me and blames me for it...He hit me recently, I was shocked...it's all my fault...I don't want to get him in trouble, he is a good person otherwise."* → Action: `Tier 3 + SOS flag` → **Bot Script: empty** → Escalation: `Clinical Psychologist + Crisis review`.

## 6. `Kb_Phase_I_9.csv` — Signal Sufficiency

**Real header (row 5 of the raw export)**: `Tier, [pattern/type name, unlabeled column], Minimum Signals, Must-Have Signals, Confidence Threshold, Tie-Breaker Logic, When to Keep Probing, Graceful Exit Trigger`

**Exact row count: 185 real data rows** (design docs estimated ~195 — the discrepancy is worth noting: the standalone enrichment workbook's "Signal Sufficiency (full)" sheet, described in §7 below, independently reports 195/196 rows, meaning the cleaned/merged version may have added or restructured some rows relative to the raw client export. **Treat 195 (the merged workbook's count) as the more current number, but confirm with the client which is authoritative** — flagged in [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md).)

**12 clinical categories** (each with its own Tier 1/2/3 sub-block): Mood Disorders (Depression and Bipolar Disorder), Anxiety and Related Disorders, Personality Disorder and Trait-Based Situational Issues, ADHD and Related Disorders, Gender and Sexual Dysphoria and Other Related Patterns, Substance Use and Related Patterns, Feeding and Eating Disorders and Related Patterns, Stress/Trauma and Associated Patterns, Somatic and Related Patterns, Dissociative and Related Patterns, Sleep-Related Patterns, Obsessive-Compulsive and Related Patterns.

**⚠ Confirmed placeholder value found in the live data**: row for **"Recurrent Mood Episode Patterns"** has the literal text `check----------` in its Tier column instead of an actual tier label. (The merged-workbook README also independently flags 2 rows total with this exact placeholder — the other being "patterns of major depressive episodes.") **Exclude these from any pattern-matching logic until the client fills them in** — embedding or routing against a placeholder would let the system match against something that isn't actually defined.

**Sample rows**:
- Tier 1 (Self-Help) — "situational low mood": Minimum Signals `SIG: 1, 4, 5, 6/7, 8/9, 10, 12, 13, 16, 18, 19, 20, 21`; Must-Have Signals: `not mandatory`; Graceful Exit: *"duration + situational signal coping strategies are fairly good."*
- Tier 2 (Therapist) — "Persistent Pattern of Low mood": Minimum Signals `SIG: 1, 2/3, 4, 5, 6/7, 8/9, 10, 12, 13, 15, 16, 18, 19, 20, 21, 22, 23, 36, 152, 154, 156, 214-232`.
- Tier 3 (Psychiatrist) — "Depression with suicidal ideations": Confidence Threshold: *"symptoms of depression accompanied by active suicidal ideations; functional and occupational impairment"*; Tie-Breaker Logic: `NA — if red flag present`; Graceful Exit: *"Red flag detected and need for psychiatric assistance is crucial."*
- Tier 3, OCD category — "Harm related OCD patterns": When to Keep Probing includes *"is self harm is present DO NOT probe"* — i.e. this row itself encodes a mid-probe safety override.

## 7. `Kb_Phase_I_17.csv` — Fallback & Safety Net

See [08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) §5 for the full corrected structure (4 sections, not 3, plus a separate 84-row disorder matrix — 99 real data rows total) and the "Shreya" PII issue found in the Section B contradictory-signals data. Not repeated here to avoid duplication — that's the canonical description.

## 8. The enrichment/merge workbooks — which one is authoritative

Two versions of the merged/enriched deliverable exist:
- `/documnets/flow/RAG/Mindfully_Yours_Merged_Signal_Profile (1).xlsx` — 3 sheets: `README` (headed *"Merged Signal Profile — v2, corrected"*), `Merged Signal Profile` (285 signal rows), `Merged PhysEmotional Profile` (154 symptom rows).
- `/documnets/knowledgebase/Mindfully_Yours_Merged_Signal_Profile (2).xlsx` — **6 sheets**: the same 3 above **plus** `Signal Sufficiency (full)` (195 rows), `Red Flags (full)` (31 rows), `Fallback  Safety Net (full)` (100 rows, note the double space in the actual sheet name). README headed *"Complete Merged KB Reference (v3, final check)."*

**Verdict, confirmed by full cell-by-cell diff: file (2) is a strict superset of file (1).** Zero differences found across all shared rows in `Merged Signal Profile` and `Merged PhysEmotional Profile`. **`Mindfully_Yours_Merged_Signal_Profile (2).xlsx` (in `/knowledgebase/`) is the single authoritative enrichment deliverable — file (1) added zero unique information and has since been removed from the repo.**

**Columns added by the enrichment process**, confirmed from the real sheets:
- `Merged Signal Profile`: adds `Linked Routing Rules (ID [Priority] → Tier)` to the raw A1 columns.
- `Merged PhysEmotional Profile`: adds `Conversational Approach to Uncover`, `Linked Signal Concepts`, `Any Linked Red Flag?`, `A2 Native Severity`, `Max Linked Severity`, `Severity Check` (flags 4 rows where A2's own severity disagrees with its linked A1 signals' severity — shaded yellow in the source).

**The v3 README's own stated gaps** (verbatim structure, restated precisely since this is the authoritative current status):
- Only 25 of 285 A1 signals have an auto-matched routing rule — most of C11's 66 rules use range/combination logic ("SIG 001-017 minus SIG002-003") that simple number-matching can't expand.
- `Rule-025` has no priority/route_to, excluded.
- **`EM:` codes are still completely undefined anywhere in the KB** — confirmed independently by this deep-dive's own analysis of `A2`'s 133 EM- rows (§3 above).
- 4 PhysEmotional rows have a severity mismatch between A2's own severity and its linked A1 signals' severity (shaded yellow in the source).
- 2 Signal Sufficiency rows have the `check----------` placeholder instead of a real Tier (shaded grey in the source).

---
*Source material: direct programmatic analysis (python3 csv/openpyxl) of every file under `documnets/knowledgebase/` and `documnets/flow/RAG/`, cross-referenced against `KNOWLEDGE_BASE_CONTENT.md` v2 and `SIGNAL_ENRICHMENT_APPROACH.md`. Where this document's numbers differ from the design markdown's estimates, this document's numbers come from directly parsing the real files and should be treated as more current.*
