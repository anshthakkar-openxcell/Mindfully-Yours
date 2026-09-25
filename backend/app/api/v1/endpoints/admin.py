"""
Read-only operational endpoints for KB version status.

DELIBERATELY DOES NOT expose any write path for prompt_config or the interlock rule set. Per the
architecture PDFs' Prompt & Persona Engineering section (documnets/understanding/02_ARCHITECTURE.md
§5, and app.db.models.kb.PromptConfig's docstring): "Prompt is not visible or editable by any user
or admin -- same governed process for all." That content is written ONLY by the ingestion/
clinical-review tooling (app/ingestion/, run as a script with clinical sign-off), never via a
general-purpose HTTP API, no matter how it's authenticated. Do not add a write route here.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import verify_service_caller
from app.db.models.kb import KBVersion

router = APIRouter()


@router.get("/admin/kb-versions", dependencies=[Depends(verify_service_caller)])
async def list_kb_versions(db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(select(KBVersion).order_by(KBVersion.version_id.desc()))
    versions = result.scalars().all()
    return [
        {
            "version_id": v.version_id,
            "label": v.label,
            "status": v.status,
            "retrieval_hit_rate": v.retrieval_hit_rate,
            "grounding_accuracy": v.grounding_accuracy,
            "tier_routing_accuracy": v.tier_routing_accuracy,
            "adversarial_pass_rate": v.adversarial_pass_rate,
            "activated_at": v.activated_at.isoformat() if v.activated_at else None,
        }
        for v in versions
    ]
