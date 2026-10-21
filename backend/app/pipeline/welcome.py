"""
The first message of a conversation -- one of the therapists' own welcome messages
(`kb_welcome_responses`, from AI WELCOME RESPONSES.docx), served exactly as written. No LLM call, no
embedding, one tiny query, so the opening is instant (doc 33).

The source text uses the literal word "user" as the name slot ("Hi user, what's on your mind
today?"). With a name it is replaced by the name; without one it becomes "there" ("Hi there, ...") --
never left as the word "user", which would read as a bug.
"""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.kb_convo_content import KBWelcomeResponse
from app.pipeline.localize import localize_reply

logger = get_logger(__name__)

_NAME_SLOT = re.compile(r"\buser\b", re.IGNORECASE)
# Only used if the table is empty (e.g. a fresh database before ingestion) -- the conversation must
# never fail to open. Plain and neutral; the real messages are the therapists'.
FALLBACK_WELCOME = "Hi there, welcome. What would you like to talk about today?"


def fill_name(template: str, name: str | None) -> str:
    """Replace the "user" name slot with `name`, or "there" when the name is unknown."""
    replacement = (name or "").strip() or "there"
    return _NAME_SLOT.sub(replacement, template)


async def pick_welcome(
    db: AsyncSession, *, name: str | None = None, language: str = "en", reply_style: str = "en"
) -> str:
    """A random approved welcome message, with the name slot filled, in the user's language
    (`reply_style`: 'en' | 'hi' | 'hinglish'). Never raises. Without a name the message is a pre-translated
    lookup (instant); with a name it is translated live, once, then remembered."""
    try:
        stmt = (
            select(KBWelcomeResponse.text)
            .where(KBWelcomeResponse.approved.is_(True), KBWelcomeResponse.language == language)
            .order_by(func.random())
            .limit(1)
        )
        text = (await db.execute(stmt)).scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001 -- opening a conversation must not fail over a greeting
        logger.error("welcome_lookup_failed", error=str(exc))
        text = None
    filled = fill_name(text or FALLBACK_WELCOME, name)
    return await localize_reply(filled, reply_style, kind="welcome")
