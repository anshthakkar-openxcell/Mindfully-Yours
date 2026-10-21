"""
Parses `AI WELCOME RESPONSES.docx` -- the therapists' opening messages. Confirmed against the real
file: one message per paragraph, mostly "Hi user, ..." / "Hey user, ..."; the first 4 are Word list
items, the 5th carries a typed "5. " prefix, and the first message is a closing-style line
("thank you for sharing this with me") rather than a greeting -- it is kept but flagged, since using
it as the very first thing a stranger sees would read oddly.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document

_NUMBER_PREFIX = re.compile(r"^\s*\d+[.)]\s*")
_TITLE = "ai welcome responses"
# Not a greeting: it assumes the person already shared something.
_NOT_A_GREETING = re.compile(r"thank you for sharing", re.IGNORECASE)


def parse_welcome_responses(path: Path) -> list[dict]:
    seen: set[str] = set()
    rows: list[dict] = []
    for paragraph in Document(str(path)).paragraphs:
        text = _NUMBER_PREFIX.sub("", paragraph.text).strip()
        if not text or text.lower() == _TITLE or text in seen:
            continue
        seen.add(text)
        rows.append(
            {
                "text": text,
                "approved": not _NOT_A_GREETING.search(text),
                "source_file": path.name,
                "language": "en",
            }
        )
    return rows
