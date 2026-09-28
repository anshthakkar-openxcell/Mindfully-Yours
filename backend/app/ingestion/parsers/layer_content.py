"""
Parsers for the "Layer" conversational-depth question/statement banks -- the new axis discovered
in the Sept 2026 convo-data drop, separate from the existing Tier 1/2/3 severity system. See
documnets/understanding/18_NEW_CONVO_DATA_CATALOG.md §1 and
documnets/understanding/21_NEW_CONTENT_INGESTION_PLAN.md for the full reasoning.

Confirmed real structures (via direct python-docx inspection, not assumed):
- `Layer I Questions and Statments.docx`, `Layer III.docx`, `Layer 2 to 3 Transitions.docx` all use
  clean `Title`/`Heading 1`/`List Paragraph` styles -- reliable to parse via heading detection.
- `Layer II Question Bank.docx` uses ZERO heading styles (everything is "Normal") -- requires the
  `is_label_line` heuristic from docx_common.py.
- `PHASE II Layer I and IV Questions.docx` uses only 2 `Title` markers ("Layer 1 : Questions",
  "Layer 4 : Questions") with no further sub-categorization.
- Layer II and Layer III both independently confirmed to use the SAME 28-emotion list (not 23 as
  an earlier summary pass estimated) -- see documnets/understanding/21_NEW_CONTENT_INGESTION_PLAN.md
  §Client Questions for why this is a useful data point for the emotion-taxonomy reconciliation.
"""

from pathlib import Path

from docx import Document

from app.ingestion.parsers.docx_common import is_label_line

# The 7 generic (non-emotion) categories in Layer II's first half -- confirmed via direct
# inspection. Any OTHER label encountered in that file is treated as an emotion-specific section.
LAYER_II_GENERIC_CATEGORIES = {
    "Values",
    "Goals",
    "Boundaries",
    "Strengths & Weaknesses",
    "Pattern Detection",
    "Psycho-education",
    "Introspection",
}

# The 5 generic (non-emotion) categories in Layer III's first half -- confirmed via direct
# inspection (Heading 1 style, appear before the 28 emotion headings).
LAYER_III_GENERIC_CATEGORIES = {
    "Awareness",
    "Self-Regulation Tool Prompts",
    "Reflective Statements",
    "Skill Introduction Statements",
}


def parse_heading_based_layer_file(path: str | Path, *, layer: str) -> list[dict]:
    """
    For `Layer I Questions and Statments.docx`, `Layer III.docx`, and `Layer 2 to 3
    Transitions.docx` -- all confirmed to use real `Heading 1` styles marking each section, with
    the actual question/statement text below as plain paragraphs.
    """
    document = Document(str(path))
    records: list[dict] = []
    current_section: str | None = None
    is_transition_section = False

    for p in document.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        style = p.style.name if p.style else ""

        if style == "Title":
            continue  # the document's own title paragraph, not content

        if style == "Heading 1":
            current_section = text
            is_transition_section = text.lower().startswith("transition statements")
            continue

        if current_section is None:
            continue  # stray text before the first real heading

        section_type = "transition" if is_transition_section else (
            "emotion_specific"
            if current_section not in LAYER_II_GENERIC_CATEGORIES | LAYER_III_GENERIC_CATEGORIES
            and layer in ("III",)  # Layer I has no emotion-specific split; only III does
            else "generic"
        )

        records.append(
            {
                "layer": layer,
                "section": current_section,
                "section_type": section_type,
                "emotion_label": current_section if section_type == "emotion_specific" else None,
                "text": text,
                "source_file": Path(path).name,
            }
        )
    return records


def parse_layer_ii(path: str | Path) -> list[dict]:
    """
    `Layer II Question Bank.docx` -- confirmed to use zero heading styles. Every paragraph is
    "Normal"; section boundaries are detected via `is_label_line` (see docx_common.py for why the
    simpler "doesn't end in '?'" heuristic is NOT used -- it produces false positives here).
    """
    document = Document(str(path))
    records: list[dict] = []
    current_section: str | None = None
    first_line = True

    for p in document.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        if first_line:
            first_line = False
            continue  # the document's own title line ("Layer II — Question Bank - Generic")

        if is_label_line(text):
            current_section = text
            continue

        if current_section is None:
            continue

        section_type = "emotion_specific" if current_section not in LAYER_II_GENERIC_CATEGORIES else "generic"
        records.append(
            {
                "layer": "II",
                "section": current_section,
                "section_type": section_type,
                "emotion_label": current_section if section_type == "emotion_specific" else None,
                "text": text,
                "source_file": Path(path).name,
            }
        )
    return records


def parse_phase_ii_layer_i_and_iv(path: str | Path) -> list[dict]:
    """
    `PHASE II Layer I and IV Questions.docx` -- confirmed to use exactly 2 `Title` markers
    ("Layer 1 : Questions", "Layer 4 : Questions") with no further sub-categorization beneath them.
    """
    document = Document(str(path))
    records: list[dict] = []
    current_layer: str | None = None

    for p in document.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        style = p.style.name if p.style else ""

        if style == "Title":
            current_layer = "I" if "Layer 1" in text else "IV" if "Layer 4" in text else None
            continue

        if current_layer is None:
            continue

        records.append(
            {
                "layer": current_layer,
                "section": None,
                "section_type": "generic",
                "emotion_label": None,
                "text": text,
                "source_file": Path(path).name,
            }
        )
    return records
