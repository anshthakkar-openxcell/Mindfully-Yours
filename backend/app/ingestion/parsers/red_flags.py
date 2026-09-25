"""
Parser for `Kb Phase I(7.csv` -- Red Flags. 31 flags (RF-001..RF-031).

Confirmed real structure (documnets/understanding/05_KNOWLEDGE_BASE_DEEP_DIVE.md §5): real header
at row 4: Flag ID, Trigger Phrase Examples (5+), Clinical Meaning, Immediate Action,
Bot Script (verbatim), Escalation Target. Multi-phrase flags spread across several physical rows
with the Flag ID left blank on continuation rows (forward-fill required, or data silently
disappears). Trigger phrases appear in THREE different raw formats across flags -- one-per-line,
quote-mark-separated on one line, or a single long paragraph -- this parser must handle all three.

CONFIRMED HARD GAP, not a parsing artifact: RF-028, RF-029, RF-030, RF-031 have an EMPTY Bot
Script cell in the source data. This parser preserves that as `bot_script: None` -- it must NOT be
coerced into an empty string or a placeholder, since app.safety.interlock and
app.core.exceptions.MissingBotScriptError specifically check for None to trigger the hard
human-alert path. See documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #1.
"""

import re
from pathlib import Path

from app.ingestion.parsers.common import clean_cell, forward_fill_group_label, read_client_csv

HEADER_ROW = 4


def parse_red_flags(path: str | Path) -> list[dict]:
    df = read_client_csv(path, header_row=HEADER_ROW)
    df["Flag ID"] = forward_fill_group_label(df["Flag ID"])
    df = df.dropna(subset=["Flag ID"])

    records = []
    for flag_id, group in df.groupby("Flag ID", sort=False):
        phrases: list[str] = []
        for raw_cell in group["Trigger Phrase Examples (5+)"].dropna():
            phrases.extend(_split_trigger_phrases(str(raw_cell)))

        first_row = group.iloc[0]
        records.append(
            {
                "flag_id": str(flag_id).strip(),
                "trigger_phrases": phrases,
                "clinical_meaning": _clean(first_row.get("Clinical Meaning")),
                "immediate_action": _clean(first_row.get("Immediate Action")),
                "bot_script": _clean(first_row.get("Bot Script (YOU write -- verbatim)")),  # None for RF-028..031
                "escalation_target": _clean(first_row.get("Escalation Target")),  # None for RF-020
                "language": "en",
            }
        )
    return records


def _split_trigger_phrases(raw: str) -> list[str]:
    """Handles all three confirmed raw formats -- see module docstring."""
    if "\n" in raw and raw.count("\n") >= 2:
        return [p.strip() for p in raw.split("\n") if p.strip()]

    quoted = re.findall(r'"([^"]+)"', raw)
    if len(quoted) >= 2:
        return [p.strip() for p in quoted]

    # Single long paragraph (e.g. RF-011/RF-012) -- treat the whole cell as one phrase.
    return [raw.strip()] if raw.strip() else []


def _clean(value) -> str | None:
    # Delegates to the shared, NaN-safe cleaner -- see app.ingestion.parsers.common.clean_cell's
    # docstring for the bug this avoids (pandas NaN stringifying to the literal "nan").
    return clean_cell(value)
