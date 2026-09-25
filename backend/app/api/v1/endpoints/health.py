"""Liveness/readiness endpoint. No auth -- used by infra health checks."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
