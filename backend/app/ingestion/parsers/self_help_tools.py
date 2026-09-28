"""
Parser for `dbt-skills-workbook.docx` -- confirmed to be genuinely finished, ready-to-recommend
Phase IV self-help content (documnets/understanding/18_NEW_CONVO_DATA_CATALOG.md §4f). This is
Bucket 2b content (documnets/understanding/19_DATA_USAGE_MAP.md) -- embedded and genuinely searched
at Tier 1, not a style example and not a rule.

CONFIRMED STRUCTURAL QUIRK, the reason this file needs its own parser instead of the normal
heading-based one: the whole document is built from DrawingML text-box shapes (see
docx_common.extract_all_paragraph_text's docstring), and the shapes duplicate entire multi-line
groups back-to-back throughout the file -- confirmed by direct extraction, not assumed. This
parser applies `collapse_doubled_runs` (docx_common.py) to clean that up, then splits into the 5
real DBT skills using the document's own "page N of 6" footer markers as chunk boundaries --
confirmed present exactly once per page, a reliable, non-heuristic boundary.

The `dbt-skills-workbook-simple.pdf` (a plain fillable-PDF version of the same 5 skills) and
`brain-dump-worksheets.pdf` are NOT parsed here -- they're PDFs, read directly via a PDF text
extraction step (or the Read tool) rather than this docx-specific pipeline; their content is short
enough (6 and 2 pages respectively) to review and transcribe once by hand rather than build a
dedicated parser for two files. `SELF-HELP CONVERSATIONS.docx` is also NOT parsed here -- confirmed
via direct inspection to have inconsistent, Google-Docs-paste-artifact styling (a mix of "Heading
3", "Normal (Web)", and a stray custom style name) that doesn't follow a single reliable pattern
the way this file's page markers do. See documnets/understanding/21_NEW_CONTENT_INGESTION_PLAN.md
§SELF-HELP CONVERSATIONS.docx for why this one is flagged for the LLM-based chunk-boundary
technique (07_INGESTION_PIPELINE.md §2 step 2) instead of a hand-written parser.
"""

import re
from pathlib import Path

from app.ingestion.parsers.docx_common import collapse_doubled_runs, extract_all_paragraph_text

# Confirmed order via direct extraction (the workbook's own page sequence, pages 2-6 of 6):
_SKILL_ORDER = ["Wise Mind", "STOP", "TIPP", "Opposite Action", "PLEASE"]
_PAGE_MARKER = re.compile(r"^page (\d+) of \d+$", re.IGNORECASE)


def parse_dbt_skills_workbook(path: str | Path) -> list[dict]:
    raw_paragraphs = extract_all_paragraph_text(path)
    paragraphs = collapse_doubled_runs(raw_paragraphs)

    # Split into pages using the confirmed "page N of 6" footer marker.
    pages: list[list[str]] = [[]]
    for text in paragraphs:
        match = _PAGE_MARKER.match(text)
        if match:
            pages.append([])
            continue
        pages[-1].append(text)

    # Page 1 (index 0) is the cover/intro -- not a skill. Pages 2-6 (indices 1-5) are the 5 skills,
    # in the confirmed fixed order.
    records = []
    for skill_name, page_lines in zip(_SKILL_ORDER, pages[1:], strict=False):
        records.append(
            {
                "tool_name": skill_name,
                "tool_type": "dbt_skill",
                "text": "\n".join(page_lines),
                "source_file": Path(path).name,
            }
        )
    return records
