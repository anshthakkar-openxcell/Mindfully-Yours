"""
Parser for `Kb Phase I(A2.csv` -- the Physical/Emotional Symptom Map. 154 rows.

Confirmed real structure (documnets/understanding/05_KNOWLEDGE_BASE_DEEP_DIVE.md §3): rows 0-3 are
preamble, row 4 is the real header, data starts row 5. Real columns: Symptom ID,
Physical/ Emotional Symptom, How Users Describe It, Likely Emotional/Mental Root,
Maps to Signal IDs, Distinguishing Cues (physical-only vs emotional root).

NOTE: `Kb Phase I(A2 (1).csv` is a byte-identical duplicate of this file -- only ingest one of them.

CONFIRMED ID BREAKDOWN, not all rows are "PHYS-": 17 real `PHYS-` rows, 4 `PHSY-` rows (a
letter-transposition typo of PHYS-, normalized here), and 133 `EM-`/`EM ` rows whose
`Maps to Signal IDs` cell contains a free-text category label (e.g. "Motivation issue"), NOT
signal IDs. `linked_signal_ids` being empty for EM- rows is correct output, not a parsing bug.
"""

import re
from pathlib import Path

from app.ingestion.parsers.common import clean_cell, parse_signal_id_range, read_client_csv

HEADER_ROW = 4


def parse_symptom_map(path: str | Path) -> list[dict]:
    df = read_client_csv(path, header_row=HEADER_ROW)
    df = df.dropna(subset=["Symptom ID"])

    records = []
    for _, row in df.iterrows():
        raw_id = str(row["Symptom ID"]).strip()
        symptom_id, id_family = _normalize_symptom_id(raw_id)

        maps_to_raw = clean_cell(row.get("Maps to Signal IDs")) or ""
        linked_numbers = parse_signal_id_range(maps_to_raw) if id_family == "PHYS" else []
        linked_signal_ids = [f"SIG-{n:03d}" for n in linked_numbers]

        records.append(
            {
                "symptom_id": symptom_id,
                "id_family": id_family,
                "symptom": clean_cell(row.get("Physical/ Emotional Symptom")) or "",
                "how_described": clean_cell(row.get("How Users Describe It")),
                "likely_root": clean_cell(row.get("Likely Emotional/Mental Root")),
                "linked_signal_ids": linked_signal_ids or None,
                "linked_concepts": None,  # filled in by app.ingestion.enrichment, not here
                "any_linked_red_flag": False,  # filled in by app.ingestion.enrichment, not here
                "max_linked_severity": None,  # filled in by app.ingestion.enrichment, not here
                "distinguishing_cues": clean_cell(
                    row.get("Distinguishing Cues (physical-only vs emotional root)")
                ),
                "language": "en",
            }
        )
    return records


def _normalize_symptom_id(raw_id: str) -> tuple[str, str]:
    """Returns (normalized_id, id_family). Normalizes the PHSY- typo to PHYS-, and EM/EM- to EM-."""
    match = re.match(r"(PHYS|PHSY|EM)[\s\-]*0*(\d+)", raw_id, re.IGNORECASE)
    if not match:
        raise ValueError(f"Unrecognized symptom ID format: {raw_id!r}")
    prefix, number = match.group(1).upper(), int(match.group(2))
    family = "PHYS" if prefix in ("PHYS", "PHSY") else "EM"
    return f"{family}-{number:03d}", family
