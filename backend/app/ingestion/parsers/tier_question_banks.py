"""
Parsers for `Questions.docx` and `Question Set - Career.docx` -- confirmed to be the two richest
files for calibrating the existing Tier 1/2/3 system against real scenarios
(documnets/understanding/18_NEW_CONVO_DATA_CATALOG.md §4a). Both mix paragraphs AND tables in the
same document, in an order that matters -- see docx_common.iter_block_items for why a normal
`.paragraphs`/`.tables` walk cannot correctly parse these.

Confirmed real structure of `Questions.docx` (9 life-situation scenarios):
- Each scenario's name appears as a `Title`-style paragraph, TWICE in a row (a confirmed copy/paste
  artifact in the source, not two different scenarios -- deduplicated here).
- Within a scenario, `Heading 1` paragraphs mark subsections: "General Questions (...)", "Tier
  Determination Questions", "Tier 1 Questions (...)", "Tier 2 Questions (...)", "Tier 3 Questions
  (...)". Plain paragraphs beneath each are open-ended questions (some are short topic sub-labels
  like "Understanding the situation" rather than real questions -- treated as regular entries here,
  same documented simplification as scenario_taxonomy.py, not a bug).
- A bold "Close Ended Questions" paragraph, followed immediately by a TABLE, appears once per
  subsection. Confirmed table shape: row 0 is a banner row repeating the subsection name in every
  cell (not real data, skipped); rows 1+ are `[topic_label, question, answer_options]`.

Confirmed real structure of `Question Set - Career.docx` (9 career topics):
- No Title/Heading styles at all -- a topic name is simply the plain paragraph immediately
  preceding its table (10 tables total). Table columns are `Sr.No | Possible Questions |
  Possible Responses` (3-col) or `Sr.No | Possible Questions | Possible Responses | Tier Routing`
  (4-col) -- confirmed the 4th column exists in some tables but is empty in EVERY row where it's
  present (see documnets/understanding/18_NEW_CONVO_DATA_CATALOG.md §4a's "Tier Routing column ...
  left completely blank" finding) -- preserved as `tier_routing: None`, not silently dropped.
"""

from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.ingestion.parsers.docx_common import get_table_data, iter_block_items


def parse_questions_by_scenario(path: str | Path) -> dict[str, list[dict]]:
    """
    Returns {'open_questions': [...], 'close_ended_questions': [...]}.

    CONFIRMED LIMITATION, not a bug: only 6 of the file's 9 scenarios are captured by this parser
    -- "Moving out for the first time", "Dealing with the death of a loved one", "Failing an
    examination", "Dealing with chronic pain/illness", "Having financial troubles", and "LGBTQIA+
    Issues". The last 3 ("Friendship Issues", "Gender and sexuality", "Caregiver Issues") are
    confirmed to use a genuinely different, simpler structure in the real file -- no "General
    Questions"/"Tier Determination" Heading 1 subsections and no bold "Close Ended Questions"
    marker before their tables, going straight from the Title into Yes/No tables instead. Since
    this parser's section-tracking relies on those markers, their content is silently skipped
    rather than mis-attributed. This matches the independently-documented finding in
    documnets/understanding/18_NEW_CONVO_DATA_CATALOG.md §4a that these 3 are "noticeably less
    developed than the first 5/6". Handling their different shape needs a second, dedicated parser
    function once that content is prioritized -- deliberately not attempted here as a fragile
    catch-all.
    """
    document = Document(str(path))

    open_questions: list[dict] = []
    close_ended: list[dict] = []

    current_scenario: str | None = None
    current_subsection: str | None = None
    awaiting_table_for_close_ended = False

    for item in iter_block_items(document):
        if isinstance(item, Table):
            if awaiting_table_for_close_ended and current_scenario and current_subsection:
                rows = get_table_data(item)
                for row in rows[1:]:  # skip the banner row (repeats the subsection name)
                    if len(row) < 3 or not row[1].strip():
                        continue
                    close_ended.append(
                        {
                            "scenario": current_scenario,
                            "subsection": current_subsection,
                            "topic_label": row[0].strip(),
                            "question": row[1].strip(),
                            "answer_options_raw": row[2].strip(),
                            "source_file": Path(path).name,
                        }
                    )
            awaiting_table_for_close_ended = False
            continue

        assert isinstance(item, Paragraph)
        text = item.text.strip()
        if not text:
            continue
        style = item.style.name if item.style else ""
        is_bold = bool(item.runs and item.runs[0].bold)

        if style == "Title":
            if text != current_scenario:  # collapse the confirmed duplicated-title artifact
                current_scenario = text
                current_subsection = None
            continue

        if style == "Heading 1":
            current_subsection = text
            continue

        if is_bold and text == "Close Ended Questions":
            awaiting_table_for_close_ended = True
            continue

        if current_scenario is None or current_subsection is None:
            continue

        open_questions.append(
            {
                "scenario": current_scenario,
                "subsection": current_subsection,
                "text": text,
                "source_file": Path(path).name,
            }
        )

    return {"open_questions": open_questions, "close_ended_questions": close_ended}


def parse_career_question_set(path: str | Path) -> list[dict]:
    document = Document(str(path))
    records: list[dict] = []
    current_topic: str | None = None

    for item in iter_block_items(document):
        if isinstance(item, Paragraph):
            text = item.text.strip()
            if text:
                current_topic = text
            continue

        assert isinstance(item, Table)
        if current_topic is None:
            continue
        rows = get_table_data(item)
        if not rows:
            continue
        has_tier_routing_column = len(rows[0]) >= 4

        for row in rows[1:]:  # skip the real header row (Sr.No | Possible Questions | ...)
            if len(row) < 2 or not row[1].strip():
                continue
            records.append(
                {
                    "topic": current_topic,
                    "question": row[1].strip(),
                    "possible_responses_raw": row[2].strip() if len(row) > 2 else None,
                    # Confirmed: present as a column header in some tables but empty in every row
                    # -- kept as None, not coerced to an empty string, so "column exists but blank"
                    # stays distinguishable from "column doesn't exist in this table at all".
                    "tier_routing": (row[3].strip() or None) if has_tier_routing_column and len(row) > 3 else None,
                    "source_file": Path(path).name,
                }
            )
    return records
