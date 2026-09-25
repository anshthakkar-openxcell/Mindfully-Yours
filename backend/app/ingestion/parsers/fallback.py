"""
Parser for `Kb Phase I(17.csv` -- Fallback & Safety Net.

Confirmed real structure (documnets/understanding/05_KNOWLEDGE_BASE_DEEP_DIVE.md §7,
08_SAFETY_INTERLOCK_AND_TRIAGE.md §5 -- confirmed twice, independently): header at row 0
(Scenario Type, Trigger Condition, Fallback Action, Bot Script, Escalation Path,
Clinical Reasoning). FOUR lettered sections (A insufficient-signal, B contradictory-signal,
C disengagement, D special-population/adults 20-45), each introduced by a banner row containing
"SECTION <letter>". Below that, a SEPARATE 84-row, 15-group disorder-specific matrix begins at its
own header row ("Disorder / Scenario" instead of "Scenario Type"), with each group introduced by
its own "GROUP <n> <name>" banner row. This is NOT the 3-section structure the earliest design
markdown described -- 99 real data rows total once both tables are counted.

CAUTION -- PII SCRUB: the source data has a real individual's name (e.g. "Shreya") hardcoded into
THREE escalation_path rows, where every other row correctly routes to a role. See
documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #13. `_scrub_hardcoded_names` below is a
STOPGAP denylist-based redaction, not a real PII-detection solution -- the actual fix is the
clinical team correcting the source spreadsheet. Do not let this scrub function grow into a
general-purpose PII filter; escalate the source-data fix instead.
"""

import re
from pathlib import Path

from app.ingestion.parsers.common import clean_cell, read_client_csv

FIRST_HEADER_ROW = 0
SECTION_BANNER = re.compile(r"SECTION\s+([A-D])", re.IGNORECASE)
GROUP_BANNER = re.compile(r"GROUP\s+\d+\s*(.*)", re.IGNORECASE)
DISORDER_MATRIX_HEADER_MARKER = "Disorder / Scenario"

_SECTION_MAP = {
    "A": "A_insufficient",
    "B": "B_contradictory",
    "C": "C_disengagement",
    "D": "D_special_population",
}

# STOPGAP -- see module docstring. Confirmed name from documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #13.
_NAMES_TO_SCRUB = ["Shreya"]


def parse_fallback_scenarios(path: str | Path) -> list[dict]:
    df = read_client_csv(path, header_row=FIRST_HEADER_ROW)
    first_col = df.columns[0]

    records: list[dict] = []
    current_section: str | None = None
    current_disorder_group: str | None = None
    in_disorder_matrix = False

    for _, row in df.iterrows():
        first_cell = _clean(row.get(first_col))
        if first_cell is None:
            continue

        if DISORDER_MATRIX_HEADER_MARKER in first_cell:
            in_disorder_matrix = True
            continue

        section_match = SECTION_BANNER.search(first_cell) if not in_disorder_matrix else None
        if section_match:
            current_section = _SECTION_MAP[section_match.group(1).upper()]
            continue

        group_match = GROUP_BANNER.search(first_cell) if in_disorder_matrix else None
        if group_match:
            current_disorder_group = group_match.group(1).strip() or first_cell
            continue

        # Otherwise: a real data row.
        section = "disorder_matrix" if in_disorder_matrix else current_section
        if section is None:
            continue  # header/preamble row before the first section banner

        records.append(
            {
                "section": section,
                "disorder_group": current_disorder_group if in_disorder_matrix else None,
                "scenario_type": first_cell,
                "trigger_condition": _clean(row.get("Trigger Condition")) or "",
                "fallback_action": _clean(row.get("Fallback Action")),
                "bot_script": _clean(row.get("Bot Script")),
                "escalation_path": _scrub_hardcoded_names(_clean(row.get("Escalation Path"))),
                "clinical_reasoning": _clean(row.get("Clinical Reasoning")),
                "language": "en",
            }
        )
    return records


def _scrub_hardcoded_names(text: str | None) -> str | None:
    if text is None:
        return None
    for name in _NAMES_TO_SCRUB:
        text = re.sub(rf"\b{re.escape(name)}\b", "[on-shift clinician]", text)
    return text


def _clean(value) -> str | None:
    # Delegates to the shared, NaN-safe cleaner -- see app.ingestion.parsers.common.clean_cell's
    # docstring for the bug this avoids (pandas NaN stringifying to the literal "nan").
    return clean_cell(value)
