"""
Shared parsing utilities for every raw KB sheet parser in this package.

Every fact encoded here comes directly from documnets/understanding/05_KNOWLEDGE_BASE_DEEP_DIVE.md
§0 (global data-quality facts) -- read that section before touching this file. These are not
defensive guesses; they're confirmed properties of the real client files.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# Confirmed: every raw KB CSV export is Windows-1252, not UTF-8. Reading as UTF-8 corrupts
# em-dashes/apostrophes into replacement characters.
CLIENT_CSV_ENCODING = "cp1252"


def read_client_csv(path: str | Path, *, header_row: int) -> pd.DataFrame:
    """
    Every raw CSV is a "form template" export: a title row, a PURPOSE row, a HOW TO FILL row,
    sometimes an ESTIMATED TIME row, THEN the real header, sometimes followed by an instructions
    row -- and only then real data. `header_row` is the 0-indexed row containing the real column
    names for the specific file being parsed (documented per-sheet in each parser module below).
    """
    return pd.read_csv(path, encoding=CLIENT_CSV_ENCODING, header=header_row, skip_blank_lines=False)


def normalize_signal_id(raw: str) -> str:
    """
    'Sig-285' -> 'SIG-285', 'SIG 002' -> 'SIG-002', 'sig-002' -> 'SIG-002'. Confirmed casing/format
    inconsistencies: A1's last row is lowercase 'Sig-285'; free text elsewhere uses 'SIG: 001',
    'SIG 001-017', 'SIG002-003', 'SIG-168' interchangeably. This function normalizes a SINGLE
    already-isolated ID, not free text containing multiple IDs -- see parse_signal_id_range for that.
    """
    match = re.search(r"(\d+)", raw)
    if not match:
        raise ValueError(f"No numeric signal ID found in {raw!r}")
    return f"SIG-{int(match.group(1)):03d}"


def normalize_rule_id(raw: str) -> str:
    """'RULE-001' and 'Rule-015' both normalize to 'RULE-001'/'RULE-015'. Confirmed: C11 silently
    switches from RULE- (001-014) to Rule- (015+) partway through the file -- an exact-match lookup
    keyed on one casing alone will silently miss over half the rules."""
    match = re.search(r"(\d+)", raw)
    if not match:
        raise ValueError(f"No numeric rule ID found in {raw!r}")
    return f"RULE-{int(match.group(1)):03d}"


def parse_signal_id_range(text: str) -> list[int]:
    """
    Parses a `Maps to Signal IDs`-style free-text cell into a list of signal numbers. Handles the
    three confirmed real formats, in the order that must be checked (ranges before naive number
    extraction, or "SIG-041-043" is misread as two IDs [41, 43] instead of the range 41-42-43):

        "SIG-044, SIG-045"      -> [44, 45]            (comma list)
        "SIG-041-043"           -> [41, 42, 43]        (hyphenated range)
        "SIG-085 to 093"        -> [85, 86, ..., 93]   (word range)

    Per documnets/understanding/06_SIGNAL_ENRICHMENT_PIPELINE.md §3. Returns [] for EM- rows whose
    cell contains a category label instead of signal IDs (e.g. "Motivation issue") -- that is
    CORRECT behavior, not a parsing failure; see 05_KNOWLEDGE_BASE_DEEP_DIVE.md §3.
    """
    range_to = re.search(r"(\d+)\s*to\s*0*(\d+)", text, re.IGNORECASE)
    if range_to:
        return list(range(int(range_to.group(1)), int(range_to.group(2)) + 1))

    range_hyphen = re.search(r"SIG-(\d+)-0*(\d+)", text, re.IGNORECASE)
    if range_hyphen:
        return list(range(int(range_hyphen.group(1)), int(range_hyphen.group(2)) + 1))

    return [int(n) for n in re.findall(r"\d+", text)]


def match_signal_in_trigger_condition(trigger_condition: str, signal_number: int) -> bool:
    """
    Tolerant regex match for whether a routing rule's free-text `trigger_condition` mentions a
    given signal number, regardless of 'SIG002-003' / 'SIG 001-017' / 'SIG-002' prefix style. Per
    documnets/understanding/06_SIGNAL_ENRICHMENT_PIPELINE.md §2.

    KNOWN LIMITATION (documented, not a bug to silently fix here): this only catches direct
    single-number mentions, not range/combination logic like "SIG 001-017 minus SIG002-003" --
    confirmed to resolve only 25/285 signals on the real data. See
    documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #4 for the follow-up work
    (a proper range/combination parser) this function does not attempt.
    """
    pattern = rf"SIG[\s\-]?0*{signal_number}\b"
    return re.search(pattern, trigger_condition, re.IGNORECASE) is not None


def clean_cell(value) -> str | None:
    """
    Normalize a raw pandas cell value to either a stripped string or None.

    BUG THIS FIXES: `pd.read_csv` represents an empty cell as `float('nan')`, and naive
    `str(value).strip() or None` turns that into the literal string `"nan"` (truthy, non-empty) --
    silently corrupting every genuinely-missing cell (e.g. RF-028's missing bot_script) into a
    fake string value instead of a real None. Always use this helper, never a local `str(x) or
    None` one-liner, when cleaning a pandas cell in any KB parser.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def forward_fill_group_label(series: pd.Series) -> pd.Series:
    """
    Several sheets (9, 7) use a spreadsheet convention where a group's identifying label (Tier,
    Flag ID) is written once on the first row of a group and left blank on continuation rows.
    Forward-filling recovers the label for every row -- skipping this silently loses data (rows
    read as unlabeled) rather than raising an error, which is why every parser MUST call this
    explicitly rather than relying on pandas' default NaN behavior.
    """
    return series.ffill()
