"""
Parses `Situational Routing.xlsx` (Sheet1). Confirmed against the real file: header row, then group
rows (a name in column A with nothing in B -- e.g. "Work / career / study", also "General Guidelines")
followed by situation rows whose column A is "SID -001". Columns: situation, Tier 1 outcome, Tier 2
outcome, Tier 3 outcome, self-care strategy. 137 situations in 13 groups; 12 have no self-care
strategy, kept as NULL, not invented. Sheet2 holds the three general tier definitions; it is not a
per-situation table, so it is not loaded here (see
documnets/understanding/33_CLIENT_DROP_2_ADDITIONS.md).
"""

from __future__ import annotations

import re
from pathlib import Path

import openpyxl

_SID = re.compile(r"^\s*SID\s*-?\s*(\d+)\s*$", re.IGNORECASE)


def _clean(value) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def parse_situational_routing(path: Path) -> list[dict]:
    sheet = openpyxl.load_workbook(path, data_only=True)["Sheet1"]
    category: str | None = None
    rows: list[dict] = []
    for r in sheet.iter_rows(values_only=True):
        first = _clean(r[0])
        if not first:
            continue
        match = _SID.match(first)
        if not match:
            if first.lower() != "situation id" and not any(_clean(c) for c in r[1:]):
                category = first
            continue
        situation = _clean(r[1])
        if not situation or category is None:
            continue
        rows.append(
            {
                "situation_id": f"SID-{int(match.group(1)):03d}",
                "category": category,
                "situation": situation,
                "tier1_outcome": _clean(r[2]),
                "tier2_outcome": _clean(r[3]),
                "tier3_outcome": _clean(r[4]),
                "self_care_strategy": _clean(r[5]),
                "source_file": path.name,
                "language": "en",
            }
        )
    return rows
