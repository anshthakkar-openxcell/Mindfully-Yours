"""
Developer tool: run messages through the REAL pipeline (run_turn) and show where each reply came from.

    cd backend && .venv/bin/python scripts/try_turn.py "I just moved to a new city and feel alone" "another message"

Uses the real database, Redis, embedding provider and LLM from .env, so it needs `docker compose up` running.
Each message is a separate, fresh conversation (a new session row is created -- the audit log has a foreign key to
`sessions`), and the audit row is read back so you see `served_from`, similarity and per-step timings.
Test sessions accumulate in the dev DB (marked summary = 'dev_try_turn'); clean up with:
    delete from turn_audit_log where session_id in (select session_id from sessions where summary = 'dev_try_turn');
    delete from sessions where summary = 'dev_try_turn';
"""

import asyncio
import logging
import sys
import time
import uuid

from redis.asyncio import from_url
from sqlalchemy import text

from app.core.config import get_settings
from app.db.models.conversation_session import ConversationSession
from app.db.session import AsyncSessionLocal
from app.pipeline.orchestrator import TurnRequest, run_turn
from app.providers.factory import get_embedding_provider, get_llm_provider

logging.disable(logging.CRITICAL)  # keep the output readable; the audit row has what matters


async def main(messages: list[str]) -> None:
    settings = get_settings()
    redis = from_url(settings.redis_url, decode_responses=False)
    embeddings, llm = get_embedding_provider(), get_llm_provider()
    for message in messages:
        session_id = uuid.uuid4()
        async with AsyncSessionLocal() as db:
            db.add(ConversationSession(session_id=session_id, mode="text", language="en", summary="dev_try_turn"))
            await db.commit()
        started, first, parts = time.monotonic(), None, []
        async with AsyncSessionLocal() as db:
            request = TurnRequest(session_id=session_id, user_id=None, language="en", text=message)
            async for chunk in run_turn(request, db=db, redis=redis, llm=llm, embedding_provider=embeddings):
                first = first if first is not None else (time.monotonic() - started) * 1000
                parts.append(chunk)
        total = (time.monotonic() - started) * 1000
        await asyncio.sleep(0.6)  # the audit write is fire-and-forget
        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                text("select served_from, retrieved_chunk_ids, latency_ms from turn_audit_log "
                     "where session_id = :s order by created_at desc limit 1"), {"s": str(session_id)})).first()
        lat = (row.latency_ms or {}) if row else {}
        print(f"\nUSER:   {message}")
        print(f"SOURCE: {row.served_from if row else '?'}   ids={row.retrieved_chunk_ids if row else None}")
        print(f"TIMING: first_chunk={first:.0f}ms total={total:.0f}ms | " + ", ".join(
            f"{k}={v:.0f}" if isinstance(v, (int, float)) and k.endswith("_ms") else f"{k}={v}" for k, v in lat.items()
            if k in ("translate_in_ms", "embed_ms", "triage_ms", "interlock_ms", "curated_wait_ms", "curated_similarity", "clarify_similarity", "llm_ms")))
        print(f"REPLY:  {''.join(parts)[:400]}")
    await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or ["I just moved to a new city for college and I feel so alone, I don't know anyone here"]))
