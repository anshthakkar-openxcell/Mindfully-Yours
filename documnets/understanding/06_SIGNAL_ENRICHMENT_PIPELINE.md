# 06 — Signal Enrichment & Merge Pipeline (the A1 + A2 + C11 join)

> This is a specific, already-proven ingestion sub-step: joining the client's raw sheets into enriched, retrieval-ready records, computed once at ingestion time so the runtime pipeline never needs a live cross-reference lookup. This was built and validated against the real data — the numbers here are real, not estimated. See [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) for the underlying per-sheet data this pipeline consumes.

## 1. The problem this solves

Each of the client's KB sheets is correct and complete on its own, but a signal in isolation is missing context that lives in a different sheet. A user's message might match `PHYS-003` (a physical symptom), but the thing that actually matters — how severe is this, is it a red flag, which routing rule applies — lives in `A1` and `C11`, not in `A2` itself. Retrieving `PHYS-003` alone gives the AI a bare description with no way to calibrate its response.

**The fix is not to flatten everything into one table** — different sheets operate at genuinely different levels (signal-level, rule-level, category-level, scenario-level, conversation-state-level; see [04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md) §3 for the three distinct retrieval mechanisms this implies). **The fix is to enrich each signal-level record with the specific cross-references it needs, computed once at ingestion, never looked up live during a conversation.**

## 2. Merge 1 — `A1` enriched with matching `C11` rules

**Join key**: the numeric portion of the signal ID, matched against free-text mentions inside each rule's `Trigger Condition`.

**Why numeric matching, not exact string matching**: the client's rules reference signals inconsistently — `SIG002-003`, `SIG 001-017`, `SIG-002` all appear in the real data (confirmed directly in [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) §4). A regex on the number alone, tolerant of prefix variations, is what actually works:

```python
re.search(rf'SIG[\s\-]?0*{num}\b', trigger_condition, re.IGNORECASE)
```

**Result on real data**: 25 of 285 signals matched to at least one rule. Example — `SIG-002` (Suicidal ideation, passive) resolved to `RULE-001 → Tier 3` and `RULE-002 → Tier 2 (escalate)`.

**Known limitation, stated plainly**: most of the 66 rules reference *ranges or combinations* (e.g. "primary signals from SIG 001-017 minus SIG002-003"), which this simple numeric match doesn't fully expand — it catches direct single-number mentions but not range/exclusion logic. This is why only 25 of 285 signals matched, not because most signals genuinely lack an applicable rule. **This needs a proper range-parser or the client's direct input to complete** — treat the current output as a validated starting format, not a finished mapping. This is item #1 in [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md).

**Output schema**: `signal_id, clinical_concept, phrasings, tone_cues, trajectory_cues, category, mh_disorder, severity, red_flag, matched_rules (e.g. "RULE-001 → Tier 3 | RULE-002 → Tier 2")`

## 3. Merge 2 — `A2` enriched via its own `Maps to Signal IDs` column, into Merge 1's output

**This join already existed in the client's design** — `A2` has its own column pointing back to `A1`'s signal IDs. This isn't an inferred relationship; it's explicit in the source data.

**The parsing problem**: `Maps to Signal IDs` contains at least three different formats in the real data, confirmed directly (see [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) §3 for verbatim examples):

| Format | Real example | Parsing approach |
|---|---|---|
| Comma list | `"SIG-044, SIG-045"` | Extract every number in the string |
| Hyphenated range | `"SIG-041-043"` | Detect `SIG-\d+-\d+` specifically, expand as a range |
| Word range | `"SIG-085 to 093"` | Detect `\d+\s*to\s*\d+`, expand as a range |
| No IDs at all | `"Can be seen across all signals - but as a supporting signal"` | Falls through to no match — a real, valid outcome, not a parsing failure |

**Order matters**: check for the range patterns *before* falling back to "extract every number," because naive number-extraction on `"SIG-041-043"` would incorrectly read it as two separate signals (41 and 43) instead of the range 41-42-43.

```python
def parse_signal_ids(text):
    range_to = re.search(r'(\d+)\s*to\s*0*(\d+)', text, re.IGNORECASE)
    if range_to:
        return list(range(int(range_to.group(1)), int(range_to.group(2)) + 1))
    range_hyphen = re.search(r'SIG-(\d+)-0*(\d+)', text, re.IGNORECASE)
    if range_hyphen:
        return list(range(int(range_hyphen.group(1)), int(range_hyphen.group(2)) + 1))
    return [int(n) for n in re.findall(r'\d+', text)]
```

**⚠ Important correction from direct data analysis** (not in the original design doc): **only 21 of A2's 154 rows are actually `PHYS-`/`PHSY-` rows with real SIG-xxx mappings to parse.** The other 133 rows are `EM-` rows whose "Maps to Signal IDs" column contains **free-text category labels, not signal IDs at all** (e.g. `"Motivation issue"`, `"Usually triggers by death"`) — the parser above will correctly find zero numbers in these and should treat that as an expected "no signal mapping" result for EM rows, not an error. See [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) §3 for the full breakdown.

**Result on the 21 real PHYS/PHSY rows**: resolves cleanly. Example — `PHYS-003` (Psychomotor retardation) had the messy raw value `"Sig 004, 005, 006, 007, 001, 023, 152,155, 156, 193,"` and correctly expands to all 10 named signals using the parser above.

**What gets pulled forward from the resolved signals** — not the full signal record (that would bloat every row with duplicate content), just the fields needed to calibrate a response without a second lookup:
```
linked_signal_count, linked_signals_resolved, linked_concepts (up to 6, named),
any_linked_red_flag (Yes if ANY resolved signal is a red flag),
max_linked_severity (the highest severity among resolved signals)
```

## 4. What this means for chunking

**No new chunking technique needed.** Each row in both merged outputs is already one complete, self-contained unit. The enrichment adds *fields* to each row; it doesn't change chunk boundaries. One row = one chunk, before and after enrichment. Full chunking-technique table: [07_INGESTION_PIPELINE.md](07_INGESTION_PIPELINE.md) §4.

## 5. What this means for storage — the embed/rule split still holds

- **`phrasings` / `how_described`** — worth embedding for semantic search; real, varied user phrasing.
- **`matched_rules`, `linked_concepts`, `any_linked_red_flag`, `max_linked_severity`** — precomputed lookup data, resolved at ingestion so the runtime pipeline never needs a second retrieval or live join. This is the concrete mechanism behind the "Direct ID-linked fetch" retrieval mechanism in [04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md) §3 — enrichment is *what makes* that direct fetch possible, by doing the cross-referencing once, offline.

## 6. What's deliberately NOT merged into these tables, and why

- **Sheet 9 (Signal Sufficiency)** — operates at the whole-conversation/category level, aggregating multiple signals over time. Doesn't belong on a single signal's row.
- **Sheet 17 (Fallback & Safety Net)** — about conversation shape (vague, contradictory, disengaged), not clinical content. Unrelated to any individual signal.
- **Sheet 7 (Red Flags & Escalation)** — frequently describes *scenarios* or behavioral patterns, not single signals, so they don't map cleanly 1:1 into a per-signal row. Checked independently, alongside each row's own `red_flag`/`any_linked_red_flag` field.

## 7. Current status and what's blocking full completion

The authoritative current-state deliverable is `Mindfully_Yours_Merged_Signal_Profile (2).xlsx` (confirmed the superset version, see [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) §8). Its own README states these open items, confirmed accurate by independent analysis:

1. **Complete the rule-matching for the other 260 signals** — needs a real range/combination parser for `Trigger Condition` text (e.g. "SIG 001-017 minus SIG002-003"), not just single-number regex matching. Materially harder than the `Maps to Signal IDs` range parsing in §3, since rule conditions combine ranges, exclusions, and multi-signal requirements in free text.
2. **The `EM` code legend is still missing** as a proper ID+concept+phrasings structure (matching `A1`'s format) — this same enrichment approach should be repeated once/if that legend arrives. In the meantime, the 133 `EM-` rows already in `A2` are the closest existing material, but they're categorical labels, not a matchable phrase legend.
3. **Validate the enrichment output with the clinical team** before treating it as system of record — the rule-matching gaps above mean it isn't a complete mapping yet.

---
*Source material: `documnets/flow/RAG/SIGNAL_ENRICHMENT_APPROACH.md` (full), cross-verified against direct analysis of `Kb_Phase_I_A1.csv`, `Kb_Phase_I_A2.csv`, `Kb_Phase_I_C11.csv`, and both `Mindfully_Yours_Merged_Signal_Profile` workbooks — see [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md).*
