"""
Parser for `Kb Phase I(A1.csv` -- the Signal Library. 285 rows, SIG-001..SIG-285.

Confirmed real structure (documnets/understanding/05_KNOWLEDGE_BASE_DEEP_DIVE.md §2): row 0 is a
junk `Column1..Column16384` Excel-full-width-export header; the REAL header is row 1; data starts
row 2. Real columns: Signal ID, Clinical Concept, Everyday Phrasings (5-10 examples), Emotional
Tone Cues, Trajectory Cues, Clinical Category, MH Disorder, Severity Weight, Red Flag.

Do not `pd.read_csv` this file without `header=1` (see app.ingestion.parsers.common.read_client_csv)
-- the file is ~16MB for only 285 real rows because of the full-width export artifact; reading it
naively will misparse the header entirely.
"""

from pathlib import Path

from app.ingestion.parsers.common import clean_cell, normalize_signal_id, read_client_csv

HEADER_ROW = 1


def parse_signal_legend(path: str | Path) -> list[dict]:
    df = read_client_csv(path, header_row=HEADER_ROW)
    df = df.dropna(subset=["Signal ID"])

    records = []
    for _, row in df.iterrows():
        red_flag_raw = (clean_cell(row.get("Red Flag")) or "").lower()
        mh_disorder_raw = clean_cell(row.get("MH Disorder")) or ""

        records.append(
            {
                "signal_id": normalize_signal_id(str(row["Signal ID"])),
                "clinical_concept": clean_cell(row.get("Clinical Concept")) or "",
                "category": clean_cell(row.get("Clinical Category")),
                # Multi-value cells are newline-joined in the source -- split into a real list.
                "mh_disorder": [d.strip() for d in mh_disorder_raw.split("\n") if d.strip()] or None,
                "severity": _parse_severity(row.get("Severity Weight")),
                "red_flag": red_flag_raw == "yes",  # normalizes Yes/yes/No/no/blank -- confirmed inconsistent casing
                "tone_cues": clean_cell(row.get("Emotional Tone Cues")),
                "trajectory_cues": clean_cell(row.get("Trajectory Cues")),
                "language": "en",
                "phrasings_text": clean_cell(row.get("Everyday Phrasings (5-10 examples)")),
            }
        )
    return records


def _parse_severity(value) -> int | None:
    try:
        sev = int(value)
    except (TypeError, ValueError):
        return None
    return sev if sev in (1, 2, 3) else None
