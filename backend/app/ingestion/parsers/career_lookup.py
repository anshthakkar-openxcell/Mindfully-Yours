"""
Parser for `Career Field & Stream Lookup.csv` -- the clean, deduplicated data extracted from
`Career Conversation Sets 1.docx`'s 500x-duplicated template (see
documnets/understanding/18_NEW_CONVO_DATA_CATALOG.md §4c and
documnets/The Real Useful Knowledge/2. Search And Match Or Recommend (Real Content)/README notes).

This file is already clean, plain CSV -- no docx quirks, no encoding issues (it's our own derived
output, written as UTF-8). This parser exists mainly so ingestion has one consistent entrypoint per
source file, matching the pattern of every other parser in this package.
"""

import csv
from pathlib import Path


def parse_career_lookup(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [
            {
                "entry_no": int(row["entry_no"]),
                "career_name": row["career_name"].strip(),
                "field_category": row["field_category"].strip(),
                "likely_academic_stream": row["likely_academic_stream"].strip(),
            }
            for row in reader
        ]
