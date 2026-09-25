"""
Parser for `Kb Phase I(9.csv` -- Signal Sufficiency. 185 confirmed real data rows in the raw CSV
(the authoritative merged workbook independently reports 195 -- see
documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #18, still unresolved which is final).

Confirmed real structure (documnets/understanding/05_KNOWLEDGE_BASE_DEEP_DIVE.md §6): real header
at row 5: Tier, [unnamed pattern-name column], Minimum Signals, Must-Have Signals,
Confidence Threshold, Tie-Breaker Logic, When to Keep Probing, Graceful Exit Trigger. 12 clinical
CATEGORY HEADER ROWS are interspersed as full-row banners (e.g. "MOOD DISORDERS - Depression and
Bipolar Disorder"), and within each category, only the FIRST row of a Tier sub-block carries the
"Tier N (...)" label -- continuation pattern rows leave that cell blank (forward-fill required).

CONFIRMED PLACEHOLDER: the row for "Recurrent Mood Episode Patterns" (and, per the merged
workbook, one more -- "patterns of major depressive episodes") has the literal text
'check----------' in the Tier cell instead of a real tier. `is_placeholder` marks these for
exclusion -- see documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #6.

TODO -- VERIFY AGAINST THE LIVE FILE BEFORE TRUSTING OUTPUT: category-header-row detection below
is a heuristic (a row where the pattern-name cell is empty but the Tier-column cell has text and
no recognizable "Tier N" prefix). This sheet's layout is the messiest of the six real KB sheets;
confirm the heuristic against `documnets/knowledgebase/Kb Phase I(9.csv` directly and adjust before
this feeds anything beyond a synthetic-data dev environment.
"""

import re
from pathlib import Path

from app.ingestion.parsers.common import clean_cell, forward_fill_group_label, read_client_csv

HEADER_ROW = 5
PLACEHOLDER_TIER_TEXT = "check----------"
_TIER_PATTERN = re.compile(r"Tier\s*([123])", re.IGNORECASE)


def parse_sufficiency(path: str | Path) -> list[dict]:
    df = read_client_csv(path, header_row=HEADER_ROW)
    pattern_col = df.columns[1]  # unnamed in the source -- the pattern/type name column

    records: list[dict] = []
    current_category: str | None = None
    df["Tier"] = forward_fill_group_label(df["Tier"])

    for _, row in df.iterrows():
        pattern_name = _clean(row.get(pattern_col))
        tier_cell = _clean(row.get("Tier"))

        if pattern_name is None and tier_cell is not None and not _TIER_PATTERN.search(tier_cell):
            # Heuristic category-header-row detection -- see module TODO above.
            current_category = tier_cell
            continue

        if pattern_name is None:
            continue  # blank padding row (files 9/C11/7/17 all have large trailing blank blocks)

        is_placeholder = tier_cell == PLACEHOLDER_TIER_TEXT
        tier_match = _TIER_PATTERN.search(tier_cell) if tier_cell else None

        records.append(
            {
                "category": current_category or "UNKNOWN",
                "pattern_name": pattern_name,
                "tier": int(tier_match.group(1)) if tier_match else None,
                "is_placeholder": is_placeholder,
                "minimum_signals_raw": _clean(row.get("Minimum Signals")),
                "must_have_signals_raw": _clean(row.get("Must-Have Signals")),
                "confidence_rule": _clean(row.get("Confidence Threshold")),
                "tie_breaker_logic": _clean(row.get("Tie-Breaker Logic")),
                "probing_guidance": _clean(row.get("When to Keep Probing")),
                "graceful_exit_trigger": _clean(row.get("Graceful Exit Trigger")),
                "language": "en",
            }
        )
    return records


def _clean(value) -> str | None:
    # Delegates to the shared, NaN-safe cleaner -- see app.ingestion.parsers.common.clean_cell's
    # docstring for the bug this avoids (pandas NaN stringifying to the literal "nan").
    return clean_cell(value)
