"""
FastAPI app factory. This process is the AI service's HTTP surface for text-mode conversation and
admin/observability reads. Voice/avatar mode is served by a separate LiveKit Agent process
(app/realtime/agent.py) that calls the same app.pipeline.orchestrator.run_turn function directly.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.providers.factory import get_embedding_provider

configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    # Closes the embedding provider's persistent HTTP connection (see
    # app.providers.embeddings.openai_embeddings's LATENCY note for why it's kept open across
    # requests instead of per-call) cleanly on shutdown, rather than leaking it.
    await get_embedding_provider().aclose()


app = FastAPI(
    title="Mindfully Yours AI Service",
    description=(
        "RAG conversation pipeline, silent triage, and safety interlock. "
        "See documnets/understanding/ for the full design reference this service implements."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
