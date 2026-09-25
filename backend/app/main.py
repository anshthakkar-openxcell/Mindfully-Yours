"""
FastAPI app factory. This process is the AI service's HTTP surface for text-mode conversation and
admin/observability reads. Voice/avatar mode is served by a separate LiveKit Agent process
(app/realtime/agent.py) that calls the same app.pipeline.orchestrator.run_turn function directly.
"""

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging()
settings = get_settings()

app = FastAPI(
    title="Mindfully Yours AI Service",
    description=(
        "RAG conversation pipeline, silent triage, and safety interlock. "
        "See documnets/understanding/ for the full design reference this service implements."
    ),
    version="0.1.0",
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
