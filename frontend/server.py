"""
Tiny local test harness for the Mindfully Yours AI service -- lets you send a message through the
REAL conversation API and see exactly what happened internally, step by step, in a sidebar.

This is a TESTING TOOL, not part of the AI service. It does not change any backend code or
behavior -- it only:
  1. Calls the AI service's existing POST /api/v1/conversation/turn endpoint, exactly as any real
     caller (the NestJS backend) would.
  2. Reads the `turn_audit_log` row that call already writes (every turn writes one, always --
     see app/pipeline/orchestrator.py steps 13-14) and returns it alongside the response, so the
     UI can show the internal trace without the AI service needing any new endpoint.

Run with the backend's own virtualenv, which already has every dependency this needs:
    ../backend/.venv/bin/python server.py
Then open http://localhost:5173 in a browser. Requires the real stack running (`docker compose up
-d` in backend/) since this talks to Postgres directly on localhost:5432 and the API on :8000.
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path

import asyncpg
import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Lets this script import the backend's app.* modules as a LIBRARY (reusing its already-existing,
# already-tested retrieval code directly) without copying any logic here or touching a single file
# under backend/app/. This is the only reason backend/ needs to be on sys.path at all.
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
# app.core.config.Settings reads `.env` relative to the process's CWD, not this file's location --
# without this, OPENAI_API_KEY etc. would silently come back empty when imported from frontend/.
os.chdir(BACKEND_DIR)

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.models.kb import KBSignal, KBSymptom  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline.retrieval import search_self_care_content  # noqa: E402
from app.providers.factory import get_embedding_provider  # noqa: E402
from app.safety.interlock import check_interlock  # noqa: E402

AI_SERVICE_URL = "http://localhost:8000/api/v1/conversation/turn"
DATABASE_URL = "postgresql://mindfully:mindfully@localhost:5432/mindfully_ai"  # plain asyncpg DSN, not the +asyncpg SQLAlchemy one

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Mindfully Yours -- local test harness")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class SendMessageRequest(BaseModel):
    session_id: str
    text: str
    use_llm: bool = False  # default OFF: see dataset-only mode below


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/send")
async def send_message(payload: SendMessageRequest) -> dict:
    # This whole handler is a TEST TOOL -- any failure here (a transient embedding-call timeout, a
    # DB hiccup) must come back as a clean JSON error the UI can render, never FastAPI's default
    # plain-text 500 (which the frontend's res.json() can't parse at all -- confirmed happening
    # live, not hypothetical).
    try:
        return await _handle_send(payload)
    except Exception as exc:  # noqa: BLE001
        return {
            "response_text": f"(test harness error: {type(exc).__name__}: {exc})",
            "round_trip_ms": None,
            "trace": {"note": "Request failed before a trace could be built -- see error above."},
        }


async def _handle_send(payload: SendMessageRequest) -> dict:
    if not payload.use_llm:
        return await _dataset_only_flow(payload.text)

    # turn_audit_log.session_id has a foreign key into `sessions` -- in production the (out-of-
    # scope) NestJS backend creates that row before ever calling the AI service. This test harness
    # stands in for that missing step so audit logging actually works when testing this service
    # standalone -- without this, every audit write silently fails (caught and logged, never
    # crashes the response, so it's easy to not notice at all -- confirmed happening on every turn
    # tested so far today).
    await _ensure_session_exists(payload.session_id)

    t0 = time.monotonic()
    response_text = ""
    stream_error = None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                AI_SERVICE_URL,
                json={
                    "session_id": payload.session_id,
                    "language": "en",
                    "consent_verified": True,
                    "text": payload.text,
                },
            ) as response:
                async for chunk in response.aiter_text():
                    response_text += chunk
    except httpx.RemoteProtocolError:
        # The AI service's stream cut off mid-response -- today this almost always means the turn
        # fell through to the LLM step (no cache hit, no interlock/routing match) and hit the
        # known, separate Sarvam LLM gap (SARVAM_API_KEY / real request shape not finalized yet --
        # see app/providers/llm/sarvam.py). NOT a bug in this test tool: show whatever text was
        # streamed before the cutoff (e.g. a filler phrase) plus the real trace up to that point,
        # instead of a raw 500.
        stream_error = (
            "(stream cut off before a full response -- the turn didn't hit cache/interlock/routing, "
            "so it reached the LLM step, which is not fully wired up yet: see app/providers/llm/sarvam.py)"
        )

    round_trip_ms = round((time.monotonic() - t0) * 1000)
    if stream_error and not response_text:
        response_text = stream_error
    elif stream_error:
        response_text += " " + stream_error

    trace = await _fetch_latest_trace(payload.session_id)
    try:
        trace["retrieval_preview"] = await _run_retrieval_preview(payload.text)
    except Exception as exc:  # noqa: BLE001 -- this is a supplementary side lookup; it must never
        # take down the whole test result if the embedding call hiccups (e.g. a transient timeout
        # -- confirmed happening live, not hypothetical).
        trace["retrieval_preview"] = {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "response_text": response_text,
        "round_trip_ms": round_trip_ms,
        "trace": trace,
    }


async def _run_signal_symptom_preview(text: str) -> dict:
    """
    Searches kb_signals (285 rows) and kb_symptoms (154 rows) directly -- tables that are fully
    embedded and full of exactly the content needed to recognize "I feel emotional and have
    stomach pain"-type messages, but that NOTHING currently searches, live or in this tool, because
    the function meant to (app.safety.triage.read_turn) is still a stub that always returns empty.

    Unlike search_self_care_content, there's no validated threshold for these tables yet -- nobody
    has tuned one, because nothing has ever queried them before. So this shows the raw top-3
    similarity scores for each, unfiltered, rather than silently hiding anything below a guessed
    cutoff -- you decide what counts as a real match by looking at the actual numbers.
    """
    embedding_provider = get_embedding_provider()
    [query_embedding] = await embedding_provider.embed([text])

    async with AsyncSessionLocal() as db:
        sig_distance = KBSignal.phrasing_embedding.cosine_distance(query_embedding)
        sig_stmt = (
            select(KBSignal.signal_id, KBSignal.clinical_concept, sig_distance.label("distance"))
            .where(KBSignal.phrasing_embedding.is_not(None))
            .order_by(sig_distance)
            .limit(3)
        )
        signals = [
            {"id": r.signal_id, "label": r.clinical_concept, "similarity": round(1 - r.distance, 3)}
            for r in (await db.execute(sig_stmt)).all()
        ]

        sym_distance = KBSymptom.how_described_embedding.cosine_distance(query_embedding)
        sym_stmt = (
            select(KBSymptom.symptom_id, KBSymptom.symptom, sym_distance.label("distance"))
            .where(KBSymptom.how_described_embedding.is_not(None))
            .order_by(sym_distance)
            .limit(3)
        )
        symptoms = [
            {"id": r.symptom_id, "label": r.symptom, "similarity": round(1 - r.distance, 3)}
            for r in (await db.execute(sym_stmt)).all()
        ]

    return {"signals": signals, "symptoms": symptoms}


async def _dataset_only_flow(text: str) -> dict:
    """
    DATASET-ONLY MODE (the default): shows exactly what your knowledge base -- and nothing else --
    has to say about this message, with ZERO LLM calls. This exists because unless a message trips
    the safety interlock, the only thing currently producing a visible reply is Sarvam, freely
    improvising text that never touches kb_* at all -- which makes it impossible to judge retrieval
    quality by reading the chat window alone. This calls real, already-tested functions
    (app.safety.interlock.check_interlock, app.pipeline.retrieval.search_self_care_content) plus a
    direct kb_signals/kb_symptoms lookup (see _run_signal_symptom_preview -- those two tables have
    no search function of their own yet), skips app.pipeline.orchestrator.run_turn and the LLM
    entirely, and shows the actual matched database content, verbatim, as the "response".
    """
    t0 = time.monotonic()
    embedding_provider = get_embedding_provider()
    top_k = get_settings().retrieval_top_k

    async with AsyncSessionLocal() as db:
        interlock_result = await check_interlock(text, db=db, embedding_provider=embedding_provider)

    matches: list[dict] = []
    sig_sym: dict = {"signals": [], "symptoms": []}
    if interlock_result.triggered:
        response_text = interlock_result.bot_script or (
            "(interlock triggered, but RF-028..031-style: this flag has no verbatim script in the "
            "source data -- in the real system this is a hard human-alert path, not a text reply)"
        )
        response_source = "safety_interlock"
    else:
        async with AsyncSessionLocal() as db:
            results = await search_self_care_content(
                text, tier=1, language="en", db=db, embedding_provider=embedding_provider, top_k=top_k
            )
        matches = [
            {"chunk_id": r.chunk_id, "category": r.category, "tier": r.tier, "text": r.text}
            for r in results
        ]
        sig_sym = await _run_signal_symptom_preview(text)

        if matches:
            top = matches[0]
            response_text = f"[Retrieved: {top['chunk_id']}]\n\n{top['text']}"
            response_source = "retrieved_chunk"
        else:
            best_sig = sig_sym["signals"][0] if sig_sym["signals"] else None
            best_sym = sig_sym["symptoms"][0] if sig_sym["symptoms"] else None
            best = max(
                [x for x in (best_sig, best_sym) if x],
                key=lambda x: x["similarity"],
                default=None,
            )
            if best and best["similarity"] >= get_settings().retrieval_confidence_threshold:
                response_text = (
                    f"[Recognized as: {best['id']} — {best['label']}]\n\n"
                    "No self-care tool exists for this yet (kb_content_chunks only has 5 DBT "
                    "skills) -- but the knowledge base DOES correctly recognize what kind of "
                    "thing this is. This is exactly the content app.safety.triage should be using "
                    "once it's wired up, instead of being a stub."
                )
                response_source = "recognized_no_action"
            else:
                response_text = (
                    "(no dataset match cleared RETRIEVAL_CONFIDENCE_THRESHOLD in any of the 3 "
                    "searchable tables -- this is exactly where the LLM would currently take over "
                    "and improvise freely; not shown here since this mode exists specifically to "
                    "judge the dataset on its own)"
                )
                response_source = "no_match"

    return {
        "response_text": response_text,
        "round_trip_ms": round((time.monotonic() - t0) * 1000),
        "trace": {
            "mode": "dataset_only",
            "response_source": response_source,
            "interlock_triggered": interlock_result.triggered,
            "interlock_flag_id": interlock_result.flag_id,
            "interlock_detail": (
                {
                    "clinical_meaning": interlock_result.clinical_meaning,
                    "escalation_target": interlock_result.escalation_target,
                    "has_script": interlock_result.bot_script is not None,
                }
                if interlock_result.triggered
                else None
            ),
            "retrieval_preview": {"top_k": top_k, "matches": matches},
            "signal_symptom_preview": sig_sym,
        },
    }


async def _run_retrieval_preview(text: str) -> dict:
    """
    Runs app.pipeline.retrieval.search_self_care_content DIRECTLY -- the real, already-tested
    retrieval function, imported and called exactly as it exists in the backend -- against the
    message just sent. This is NOT part of what actually produced the reply above (that function
    isn't wired into app.pipeline.orchestrator.run_turn yet, a known gap, not something this tool
    fakes around). It's a read-only side lookup so you can see retrieval quality directly instead
    of waiting for that wiring to happen.

    Tier is fixed at 1 because that's the only tier self-care content applies to by design, and
    the only tier any real content has been loaded for so far.
    """
    embedding_provider = get_embedding_provider()
    top_k = get_settings().retrieval_top_k  # RETRIEVAL_TOP_K from .env -- not hardcoded here either
    async with AsyncSessionLocal() as db:
        results = await search_self_care_content(
            text, tier=1, language="en", db=db, embedding_provider=embedding_provider, top_k=top_k
        )
    return {
        "top_k": top_k,
        "matches": [
            {"chunk_id": r.chunk_id, "category": r.category, "tier": r.tier, "text": r.text}
            for r in results
        ],
    }


async def _ensure_session_exists(session_id: str) -> None:
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(
            """
            INSERT INTO sessions (session_id, mode, language, lifecycle_state)
            VALUES ($1, 'text', 'en', 'live')
            ON CONFLICT (session_id) DO NOTHING
            """,
            uuid.UUID(session_id),
        )
    finally:
        await conn.close()


def _build_summary(trace: dict) -> str:
    """
    A single plain-English sentence narrating the real turn_audit_log row, in pipeline order --
    so you don't have to mentally reconstruct the sequence from 6 separate cards.

    IMPORTANT: triage + interlock run on EVERY turn, even a cache hit -- that's a non-negotiable
    safety rule (01_PROJECT_OVERVIEW.md principle #2), not something a cache hit skips. An earlier
    version of this summary said "nothing else ran" on a cache hit, which was flatly wrong -- the
    real latency breakdown (see that card) shows the interlock genuinely running and taking real
    time even when the response itself came from cache.
    """
    served_from = trace.get("served_from")
    cache_hit = served_from in ("exact_cache", "semantic_cache")
    steps = [f"Cache: HIT ({served_from})" if cache_hit else "Cache: MISS"]

    steps.append("Triage: no signals (stub)")

    if trace.get("interlock_triggered"):
        flag = trace.get("interlock_flag_id")
        steps.append(f"Interlock: TRIGGERED ({flag}) → real safety script returned, LLM never called")
        return " → ".join(steps)

    steps.append("Interlock: safe, did not trigger (always runs, even on a cache hit)")

    if cache_hit:
        steps.append("Response served from cache — LLM not called this turn")
        return " → ".join(steps)

    steps.append("Routing: no rule matched (stub)")

    if served_from == "rag_retrieval":
        # NOTE: despite the name, this label just means "normal path, not cache/interlock" -- it
        # does NOT mean retrieval actually ran (search_self_care_content isn't wired in yet).
        steps.append("LLM: generated a free-form reply (dataset not consulted)")
    else:
        steps.append(f"Ended at: {served_from or 'unknown'}")

    return " → ".join(steps)


async def _fetch_latest_trace(session_id: str) -> dict:
    """
    Reads the turn_audit_log row app.pipeline.orchestrator.run_turn already writes for every turn
    (steps 13-14 -- fired after the response, but by the time our HTTP call above has finished
    streaming, it's already committed). Enriches interlock/red-flag hits and retrieved chunks with
    their real content by joining back to kb_red_flags / kb_content_chunks, purely for display.
    """
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        row = await conn.fetchrow(
            """
            SELECT served_from, retrieved_chunk_ids, matched_signal_ids, matched_rule_id,
                   triage_tier, interlock_triggered, interlock_flag_id, latency_ms, created_at
            FROM turn_audit_log
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            uuid.UUID(session_id),
        )
        if row is None:
            return {"note": "No audit log row found yet for this session -- see README."}

        trace: dict = dict(row)
        trace["created_at"] = trace["created_at"].isoformat() if trace["created_at"] else None
        # asyncpg returns JSONB columns as a raw JSON string, not a parsed dict -- without this,
        # the UI was double-JSON-encoding it into an unreadable `"{\"llm_ms\": ...}"` blob.
        if trace.get("latency_ms"):
            trace["latency_ms"] = json.loads(trace["latency_ms"])
        trace["summary"] = _build_summary(trace)

        if trace.get("interlock_flag_id"):
            flag = await conn.fetchrow(
                "SELECT clinical_meaning, escalation_target, bot_script IS NOT NULL AS has_script "
                "FROM kb_red_flags WHERE flag_id = $1",
                trace["interlock_flag_id"],
            )
            if flag:
                trace["interlock_detail"] = dict(flag)

        chunk_ids = trace.get("retrieved_chunk_ids") or []
        if chunk_ids:
            chunks = await conn.fetch(
                "SELECT chunk_id, category, tier, text FROM kb_content_chunks WHERE chunk_id = ANY($1::text[])",
                chunk_ids,
            )
            trace["retrieved_chunk_detail"] = [dict(c) for c in chunks]

        return trace
    finally:
        await conn.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5173)
