"""
Parser for `Questions For When AI Is Not Sure - Tanisha.docx` -- a cross-cutting NLU/clarification
fallback bank, usable at any Layer or Tier when the AI's confidence in what the user means is low.
See documnets/understanding/19_DATA_USAGE_MAP.md Bucket 2a.

Confirmed real structure: zero heading styles (all "Normal"), 16 categories detected via the
`is_label_line` heuristic (see docx_common.py) -- confirmed to correctly separate exactly 16 real
categories from content with no false positives, once the heuristic checks for absence of
terminal punctuation rather than just "doesn't end in '?'" (many lines here are statements, not
questions, and end in periods).

KNOWN DATA-QUALITY ISSUE, preserved not silently cleaned: at least 2 lines in the real source
contain literal drafting notes left inside the content itself, e.g. "What emotions are coming up
for you? ( could be followed up with some options)". This parser does NOT strip these
automatically -- see documnets/understanding/18_NEW_CONVO_DATA_CATALOG.md §4a. Strip them during
the clinical-team review pass before this content ships, not silently in code, since a silent
strip could accidentally remove real content if the heuristic for "this looks like a note" is ever
wrong.
"""

from pathlib import Path

from docx import Document

from app.ingestion.parsers.docx_common import is_label_line


def parse_clarification_bank(path: str | Path) -> list[dict]:
    document = Document(str(path))
    records: list[dict] = []
    current_category: str | None = None
    first_line = True

    for p in document.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        if first_line:
            first_line = False
            continue  # document title line

        if is_label_line(text):
            current_category = text
            continue

        if current_category is None:
            continue

        records.append(
            {
                "category": current_category,
                "phrase": text,
                "has_drafting_note": "(" in text and ")" in text,
                "source_file": Path(path).name,
            }
        )
    return records
