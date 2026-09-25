"""
The AI service's core external contract: one turn in, one streamed response out.

Per documnets/understanding/14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md §4, the caller is the
(out-of-scope) NestJS backend, not an end-user client directly -- see app.core.security for the
service-to-service auth this route requires. `consent_verified` on the request is TRUSTED, not
re-checked here.

Text mode calls this directly. Voice mode (via app.realtime.agent, a LiveKit Agent) calls
app.pipeline.orchestrator.run_turn directly rather than going through HTTP, but drives the exact
same pipeline function -- so this route and the LiveKit Agent never have divergent logic.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_embeddings, get_llm, get_redis
from app.core.security import verify_service_caller
from app.pipeline.orchestrator import TurnRequest, run_turn
from app.providers.base import EmbeddingProvider, LLMProvider
from app.schemas.conversation import TurnRequestSchema

router = APIRouter()


@router.post("/conversation/turn", dependencies=[Depends(verify_service_caller)])
async def submit_turn(
    payload: TurnRequestSchema,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    llm: LLMProvider = Depends(get_llm),
    embeddings: EmbeddingProvider = Depends(get_embeddings),
) -> StreamingResponse:
    if not payload.consent_verified:
        # The AI service trusts the caller's consent check but still refuses to proceed without
        # it being explicitly asserted true -- this is a fail-closed default, not a re-verification.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="consent_verified must be true.")

    request = TurnRequest(
        session_id=payload.session_id,
        user_id=payload.user_id,
        language=payload.language,
        text=payload.text,
    )

    stream = run_turn(request, db=db, redis=redis, llm=llm, embedding_provider=embeddings)
    return StreamingResponse(stream, media_type="text/plain")
