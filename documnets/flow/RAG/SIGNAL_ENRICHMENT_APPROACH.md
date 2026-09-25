# Mindfully Yours — Signal Enrichment & Merge Approach

Companion reference to `APPROACH.md`, `CLAUDE.md`, `LATENCY.md`, `INGESTION.md`, `LIVEKIT.md`, `DATA_PROTECTION_SECURITY.md`, `KNOWLEDGE_BASE_CONTENT.md`, `CONVERSATION_REASONING_FLOW.md`, and `END_TO_END_RAG_APPROACH.md`. This file documents a specific, already-proven step in the ingestion pipeline: how the raw client spreadsheets (`A1`, `A2`, `C11`) get joined into enriched, retrieval-ready records. This was built and validated against the real data, not designed in the abstract — the numbers below are real.

---

## 1. The problem this solves

Each of the client's six KB sheets is correct and complete on its own, but a signal on its own is missing context that lives in a different sheet. A user's message might match `PHYS-003` (a physical symptom), but the thing that actually matters — how severe is this, is it a red flag, which routing rule applies — lives in `A1` and `C11`, not in `A2` itself. Retrieving `PHYS-003` alone gives the AI a bare description with no way to calibrate its response.

**The fix is not to flatten everything into one table** (see `KNOWLEDGE_BASE_CONTENT.md` Section 2 for why — different sheets operate at genuinely different levels: signal-level, rule-level, category-level, scenario-level, conversation-state-level). **The fix is to enrich each signal-level record with the specific cross-references it needs, computed once at ingestion time, not looked up live during a conversation.**

---

## 2. Source tables, with their real columns

### `A1` — Signal Library (285 rows)
```
signal_id (e.g. "SIG-002"), clinical_concept, phrasings (5-10 examples),
tone_cues, trajectory_cues, category, mh_disorder, severity (numeric), red_flag (Yes/No)
```

### `A2` — Physical/Emotional Symptom Map (154 rows)
```
symptom_id (e.g. "PHYS-003"), physical_emotional_symptom, how_described,
likely_root, maps_to_signal_ids (free text, inconsistent format), distinguishing_cues
```

### `C11` — Routing Rules (66 rows)
```
rule_id (e.g. "RULE-001"), trigger_condition (free text, references signal IDs),
logical_expr (blank, dev-filled), route_to (e.g. "Tier 3"), override_reason, trajectory_factor,
priority (1, 2, or 3 -- a real column, missed in the first pass; does NOT follow rule_id order)
```

**Correction to an earlier assumption**: this file previously implied rules are evaluated in `RULE-ID` order. That was wrong -- `C11` has a genuine `Priority` column (1/2/3) that is the real evaluation order, and it does not track rule numbering. Example: `RULE-004` carries priority 1 while `RULE-002` and `RULE-003` carry priority 2, so `RULE-004` must be evaluated first despite its higher ID number. 33 rules are priority 1, 25 are priority 2, 7 are priority 3, and one rule (`Rule-025`) has no priority or route_to set at all -- exclude it from the rules engine until the client completes that row.

---

## 3. Merge 1: `A1` enriched with matching `C11` rules

**Join key**: the numeric portion of the signal ID, matched against free-text mentions inside each rule's `trigger_condition`.

**Why numeric matching, not exact string matching**: the client's rules reference signals inconsistently — `SIG002-003`, `SIG 001-017`, `SIG-002` all appear in the real data. A regex on the number alone, tolerant of the `SIG`/`SIG-`/`SIG ` prefix variations, is what actually works against this data:

```python
re.search(rf'SIG[\s\-]?0*{num}\b', trigger_condition, re.IGNORECASE)
```

**Result on real data**: 25 of 285 signals matched to at least one rule. Example — `SIG-002` (Suicidal ideation, passive) resolved to:
```
RULE-001 → Tier 3
RULE-002 → Tier 2 (escalate)
```

**Known limitation, stated plainly**: most of the 66 rules reference *ranges or combinations* ("primary signals from SIG 001-017 minus SIG002-003"), which this simple numeric match doesn't fully expand — it catches direct single-number mentions but not range logic. This is why only 25 of 285 signals got a match, not because most signals genuinely have no applicable rule. **This needs a proper range-parser or the client's direct input to complete** — treat the current output as a validated starting format, not a finished mapping.

**Output schema**:
```
signal_id, clinical_concept, phrasings, tone_cues, trajectory_cues, category,
mh_disorder, severity, red_flag, matched_rules (e.g. "RULE-001 → Tier 3 | RULE-002 → Tier 2")
```

---

## 4. Merge 2: `A2` enriched via its own `maps_to_signal_ids` column, into Merge 1's output

**This join already existed in the client's design** — `A2` has its own column pointing back to `A1`'s signal IDs. This isn't an inferred relationship; it's explicit in the source data, which is a useful signal that the client thought about this cross-referencing need already.

**The parsing problem**: `maps_to_signal_ids` contains three different formats in the real data, and a naive parser breaks on at least two of them:

| Format | Real example | Parsing approach |
|---|---|---|
| Comma list | `"SIG-044, SIG-045"` | Extract every number in the string |
| Hyphenated range | `"SIG-041-043"` | Detect `SIG-\d+-\d+` specifically, expand as a range |
| Word range | `"SIG-085 to 093"` | Detect `\d+\s*to\s*\d+`, expand as a range |

**Order matters**: check for the range patterns *before* falling back to "extract every number," because a naive number-extraction on `"SIG-041-043"` would incorrectly read it as two separate signals (41 and 43) instead of the range 41–42–43.

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

**Result on real data**: 154 of 154 physical/emotional symptoms resolved cleanly. Example — `PHYS-003` (Psychomotor retardation) had the messy raw value `"Sig 004, 005, 006, 007, 001, 023, 152,155, 156, 193,"` (inconsistent spacing, no `SIG-` prefix repeated, trailing comma) and correctly expanded to all 10 named signals.

**What gets pulled forward from the resolved signals**: not the full signal record (that would bloat every `PHYS` row with duplicate content already available elsewhere) — just the specific fields needed to calibrate a response without a second lookup:
```
linked_signal_count, linked_signals_resolved, linked_concepts (up to 6, named),
any_linked_red_flag (Yes if ANY resolved signal is a red flag),
max_linked_severity (the highest severity among resolved signals)
```

**Result**: 9 of 154 physical/emotional symptoms touch at least one red-flag signal, now visible directly on the `PHYS` row without a second query.

---

## 5. What this means for chunking (ties to `INGESTION.md`)

**No new chunking technique needed.** Each row in both merged outputs is already one complete, self-contained unit — exactly the "the client already organized this into clean pieces" case `INGESTION.md` describes. The enrichment adds *fields* to each row; it doesn't change chunk boundaries. One row = one chunk, before and after enrichment.

---

## 6. What this means for storage — the split still holds

Per `END_TO_END_RAG_APPROACH.md`'s two-store design:

- **`phrasings` / `how_described`** — the fields worth embedding for semantic search. This is real, varied user phrasing, which is exactly what a similarity search needs to match against indirect or non-obvious language.
- **`matched_rules`, `linked_concepts`, `any_linked_red_flag`, `max_linked_severity`** — precomputed lookup data, not search targets. These are already resolved at ingestion time specifically so the runtime pipeline never needs a second retrieval or a live join to get them — they arrive already attached to the chunk that matched.

This is the concrete version of the "Direct ID-linked fetch" mechanism described in `CONVERSATION_REASONING_FLOW.md` Section 1 — the enrichment step is *what makes* that direct fetch possible, by doing the cross-referencing once, offline, instead of on every conversation turn.

---

## 7. What's deliberately not merged into these tables, and why

- **Sheet 9 (Signal Sufficiency)** — operates at the whole-conversation/category level, aggregating multiple signals over time. Doesn't belong on a single signal's row.
- **Sheet 17 (Fallback & Safety Net)** — about conversation shape (vague, contradictory, disengaged), not clinical content. Unrelated to any individual signal.
- **Sheet 7 (Red Flags & Escalation)** — these are frequently described *scenarios* or behavioral patterns, not single signals, so they don't map cleanly 1:1 into a per-signal row. Checked independently, alongside each row's own `red_flag`/`any_linked_red_flag` field, not folded into it.

---

## 8. What still needs to happen before this is production-ready

1. **Complete the rule-matching for the other 260 signals** — needs a real range/combination parser for `trigger_condition` text (e.g. "SIG 001-017 minus SIG002-003"), not just single-number regex matching. This is a materially harder parsing problem than the `maps_to_signal_ids` ranges in Section 4, since rule conditions combine ranges, exclusions, and multi-signal requirements in free text.
2. **The `EM` code legend is still missing** (per `KNOWLEDGE_BASE_CONTENT.md` v2) — this same enrichment approach should be repeated once that legend arrives, since `EM:` references appear throughout `C11` the same way `SIG:` and `PHYS:` references do.
3. **Validate the enrichment output with the clinical team** before it becomes the system of record — this was built and proven against the real data, but the *rule-matching gaps* (Section 3) mean it isn't a complete mapping yet, and shouldn't be treated as clinically validated without their review.

---

*Companion file to `APPROACH.md`, `CLAUDE.md`, `LATENCY.md`, `INGESTION.md`, `LIVEKIT.md`, `DATA_PROTECTION_SECURITY.md`, `KNOWLEDGE_BASE_CONTENT.md`, `CONVERSATION_REASONING_FLOW.md`, and `END_TO_END_RAG_APPROACH.md`. Derived from the actual merge performed against `Kb_Phase_I_A1.csv`, `Kb_Phase_I_A2.csv`, and `Kb_Phase_I_C11.csv`. Update this file once the rule range-parser is completed and the EM-code legend is merged in the same way.*
