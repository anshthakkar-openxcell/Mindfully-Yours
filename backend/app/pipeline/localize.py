"""
Give a fixed English reply to a Hindi / Hinglish user in their own language -- fast (doc 34).

Live translation costs 0.7-1.5 s, too slow for every turn, so fixed replies (therapist replies,
clarifying questions, welcome messages, red-flag scripts) are translated once OFFLINE
(`ingest ... translate-kb`) into kb_translations and just LOOKED UP here (a few ms). A reply that
isn't in the table yet is translated live and stored for next time. Anything that goes wrong returns
the English text -- a reply the user can't fully read is better than no reply, and the crisis
scripts must never be withheld.
"""

from __future__ import annotations

import asyncio
import hashlib

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.kb_convo_content import KBTranslation
from app.db.session import AsyncSessionLocal
from app.providers.factory import get_translator

logger = get_logger(__name__)
_pending_stores: set[asyncio.Task] = set()


def source_hash(text_en: str) -> str:
    return hashlib.sha256(" ".join(text_en.lower().split()).encode()).hexdigest()


async def lookup_translation(text_en: str, style: str) -> str | None:
    from sqlalchemy import select

    try:
        async with AsyncSessionLocal() as db:
            stmt = select(KBTranslation.translated_text).where(
                KBTranslation.source_hash == source_hash(text_en), KBTranslation.style == style
            )
            return (await db.execute(stmt)).scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001
        logger.error("translation_lookup_failed", error=str(exc))
        return None


async def store_translation(text_en: str, style: str, translated: str, *, kind: str | None, model: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                pg_insert(KBTranslation)
                .values(
                    source_hash=source_hash(text_en),
                    style=style,
                    source_text=text_en,
                    translated_text=translated,
                    source_kind=kind,
                    model=model,
                    reviewed=False,
                )
                .on_conflict_do_nothing(constraint="uq_kb_translations_hash_style")
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("translation_store_failed", error=str(exc))


async def localize_reply(text_en: str, style: str, *, kind: str | None = None) -> str:
    """`style` is 'en' (returned unchanged), 'hi' or 'hinglish'. Never raises."""
    if style == "en" or not text_en.strip():
        return text_en
    settings = get_settings()
    cached = await lookup_translation(text_en, style)
    if cached:
        return cached
    if not settings.translation_enabled:
        return text_en
    try:
        translated = await get_translator().from_english(text_en, style=style)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001 -- serve the English reply rather than nothing
        logger.error("reply_translation_failed_serving_english", error=str(exc), style=style)
        return text_en
    task = asyncio.create_task(
        store_translation(text_en, style, translated, kind=kind, model=settings.sarvam_translate_model)
    )
    _pending_stores.add(task)  # keep a reference so the store isn't garbage-collected mid-flight
    task.add_done_callback(_pending_stores.discard)
    return translated
