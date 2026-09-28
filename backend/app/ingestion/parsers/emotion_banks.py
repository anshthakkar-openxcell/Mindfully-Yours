"""
Parsers for the emotion phrase banks -- confirmed to be THREE separate, unreconciled lists (19
labels, 9 labels, and Layer II/III's shared 28-label list). See
documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #23 -- this module deliberately does NOT
merge them into one canonical taxonomy; it tags each source so the merge can happen later as an
explicit, reviewed step (see documnets/understanding/21_NEW_CONTENT_INGESTION_PLAN.md §Client
Questions). Loading three unreconciled lists into one un-tagged table would make that later merge
harder, not easier.

Confirmed real structure (via direct python-docx inspection) for both files parsed here:
each emotion is marked by a `Title`-style paragraph, immediately followed by a fixed boilerplate
line, sometimes a repeated copy of the emotion name, then the real phrases as plain paragraphs
until the next `Title`. Confirmed emotion counts from direct extraction: 19
(`PHASE II_ Emotion Associated user expression.docx`), 9 (`List of Emotions - Tanisha.docx`).
"""

from pathlib import Path

from docx import Document

_BOILERPLATE_LINES = {
    "phase ii: emotion associated user expression",
    "list of emotions",
}


def _parse_title_marked_emotion_doc(path: str | Path, *, source_list: str, skip_toc_block: bool) -> list[dict]:
    document = Document(str(path))
    paragraphs = document.paragraphs

    title_indices = [i for i, p in enumerate(paragraphs) if p.style and p.style.name == "Title"]
    title_texts = {paragraphs[i].text.strip() for i in title_indices}

    records: list[dict] = []
    for pos, idx in enumerate(title_indices):
        emotion_label = paragraphs[idx].text.strip()
        end = title_indices[pos + 1] if pos + 1 < len(title_indices) else len(paragraphs)
        block = paragraphs[idx + 1 : end]

        block_texts = [p.text.strip() for p in block if p.text.strip()]

        if skip_toc_block and pos == 0 and set(block_texts) <= title_texts:
            # The document's own title block is a table-of-contents listing every other emotion
            # name -- confirmed present in `List of Emotions - Tanisha.docx` (its first "Title" is
            # the document title, not a real emotion), absent in the PHASE II file (whose first
            # Title is a real emotion with real phrases immediately following).
            continue

        for text in block_texts:
            lowered = text.lower()
            if lowered in _BOILERPLATE_LINES:
                continue
            if lowered == emotion_label.lower():
                continue  # the repeated emotion-name line seen in both files
            records.append(
                {
                    "emotion_label": emotion_label,
                    "phrase": text,
                    "source_list": source_list,
                    "source_file": Path(path).name,
                }
            )
    return records


def parse_phase_ii_emotion_expression(path: str | Path) -> list[dict]:
    """19 emotions, confirmed via direct extraction: Anxiety, Confusion, Anger, Frustration,
    Stress, Helplessness, Guilt, Hopelessness, Shame, Jealousy, Worry, Sadness, Hopeful, Numbness,
    Disgust, Burnout, Conflicted, Resentment, Panic."""
    return _parse_title_marked_emotion_doc(path, source_list="phase_ii_emotion_expression", skip_toc_block=False)


def parse_list_of_emotions_tanisha(path: str | Path) -> list[dict]:
    """9 emotions, confirmed via direct extraction: Overwhelm, Demotivation, Irritation, Tensed,
    Curious, Embarrassed, Grief, Loneliness, Concerned."""
    return _parse_title_marked_emotion_doc(path, source_list="list_of_emotions_tanisha", skip_toc_block=True)
