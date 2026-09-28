"""
Shared utilities for parsing the new "convo data" drop's .docx files
(documnets/knowledgebase/convo data/decrypted/). Every fact encoded here was confirmed by directly
inspecting the real decrypted files with python-docx/lxml -- not assumed from the earlier catalog
summaries. See documnets/understanding/21_NEW_CONTENT_INGESTION_PLAN.md for the file-by-file
reasoning that led to each function here.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

_LABEL_PUNCTUATION = re.compile(r"[.?!…]$")


def iter_block_items(document: DocumentObject):
    """
    Yield each paragraph and table in a .docx file in the order they actually appear in the
    document body. python-docx's own `.paragraphs` and `.tables` are two SEPARATE flat lists with
    no ordering between them -- for files like Questions.docx and Question Set - Career.docx,
    where a topic-name paragraph is immediately followed by its own table, you cannot correctly
    pair them without walking the body in document order. This is the standard, well-known
    python-docx recipe for that; there is no built-in API for it.
    """
    body = document.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def is_label_line(text: str, max_len: int = 55) -> bool:
    """
    Heuristic for detecting a category/section LABEL line in a .docx that uses no heading styles
    at all (confirmed necessary for `Layer II Question Bank.docx` and
    `Questions For When AI Is Not Sure - Tanisha.docx`, both of which are 100% "Normal"-styled
    paragraphs with zero heading markup).

    Confirmed rule, verified against both real files: a label is short (under ~55 characters) and
    does NOT end in terminal punctuation (. ? ! …) -- every real content line (a question or a
    statement) in both files ends in one of those, while every real category name doesn't. This
    correctly separated 16/16 and 28+7/28+7 labels from content with zero false positives when
    checked against the real files -- see 21_NEW_CONTENT_INGESTION_PLAN.md for the verification.

    Do not use the simpler "doesn't end in '?'" version -- that alone false-positives on any
    label-less statement line (confirmed: it wrongly flagged "I'd like to understand your
    perspective better." as a label in the real file, because it ends in "." not "?").
    """
    text = text.strip()
    if not text or len(text) >= max_len:
        return False
    return not _LABEL_PUNCTUATION.search(text)


def extract_all_paragraph_text(path: str | Path) -> list[str]:
    """
    Extracts paragraph text from a .docx, INCLUDING text sitting inside DrawingML text
    boxes/shapes (confirmed necessary for `dbt-skills-workbook.docx` -- python-docx's normal
    `Document(path).paragraphs` walk finds only ~21 real paragraphs in that file, while the actual
    content (893 word-level `w:t` text runs) lives inside floating text-box shapes that the normal
    paragraph API does not descend into).

    Confirmed real quirk this function must handle: many `w:p` elements in a DrawingML-built
    document store each WORD as its own separate `w:t` run (e.g. "SMALL", "SKILLS", "FOR", "BIG",
    "MOMENTS" as five separate text nodes in one paragraph) -- naively concatenating them with no
    separator produces "SMALLSKILLSFORBIGMOMENTS". This joins runs with a single space and then
    cleans up spacing before punctuation, which reconstructs readable sentences correctly (verified
    against the real file).

    Confirmed real artifact this function also handles: some documents repeat a short label
    paragraph back-to-back (e.g. "Wise Mind" appearing as its own paragraph twice in a row) as a
    side effect of how the DrawingML shapes were laid out -- this is NOT new content, just a
    rendering duplicate, so consecutive identical short (<30 char) paragraphs are collapsed to one.
    """
    document = Document(str(path))
    w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    paragraphs: list[str] = []
    for p_elem in document.element.body.findall(f".//{w_ns}p"):
        parts: list[str] = []
        for node in p_elem.iter():
            tag = node.tag.split("}")[-1]
            if tag == "t":
                parts.append(node.text or "")
            elif tag == "tab":
                parts.append("\t")
            elif tag == "br":
                parts.append("\n")
        text = " ".join(x for x in parts if x != "")
        text = re.sub(r"\s+([,.'!?%:;])", r"\1", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        # Collapse a short paragraph that's an exact repeat of the previous one -- a rendering
        # artifact, not new content (see docstring).
        if paragraphs and len(text) < 30 and paragraphs[-1] == text:
            continue
        paragraphs.append(text)

    return paragraphs


def collapse_doubled_runs(paragraphs: list[str], max_run: int = 8) -> list[str]:
    """
    Collapses a sequence that repeats itself immediately (`[A, B, C, A, B, C]` -> `[A, B, C]`),
    checking run lengths from `max_run` down to 1 at each position. Confirmed necessary for
    `dbt-skills-workbook.docx` specifically: its DrawingML shapes duplicate entire multi-line
    groups back-to-back (e.g. "S" / "Stop" / "freeze -- don't act on the urge yet" appearing twice
    in a row) -- a simple single-line duplicate check does not catch this, since the repeated unit
    is a GROUP of lines, not one line.

    This is opt-in, not applied automatically inside `extract_all_paragraph_text` -- only call it
    for files independently confirmed to have this specific doubling artifact. Applying it blindly
    to every file risks deleting genuinely-intended repeated content elsewhere.
    """
    out: list[str] = []
    i = 0
    n = len(paragraphs)
    while i < n:
        collapsed = False
        for run_len in range(max_run, 0, -1):
            if i + 2 * run_len <= n and paragraphs[i : i + run_len] == paragraphs[i + run_len : i + 2 * run_len]:
                out.extend(paragraphs[i : i + run_len])
                i += 2 * run_len
                collapsed = True
                break
        if not collapsed:
            out.append(paragraphs[i])
            i += 1
    return out


def get_table_data(table: Table) -> list[list[str]]:
    """Plain 2D text grid from a python-docx Table, cell text stripped."""
    return [[cell.text.strip() for cell in row.cells] for row in table.rows]
