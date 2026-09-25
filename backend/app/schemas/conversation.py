"""
Request/response models for the conversation endpoint -- the AI service's external API contract,
per documnets/understanding/14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md §4.

NOTE on `crisis_flag`: documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #7 -- whether
Tier 3 and "Crisis" are the same outcome or two distinct ones is UNRESOLVED across the source
architecture PDFs. `crisis_flag` is included here, separate from `tier`, so the API contract
doesn't need to change again once that's resolved -- it's simply unset (False) until then.
"""

from uuid import UUID

from pydantic import BaseModel, Field


class TurnRequestSchema(BaseModel):
    session_id: UUID
    user_id: UUID | None = None
    language: str = Field(default="en", description="'en' in Phase 1 -- see 13_LANGUAGE_PHASING.md")
    text: str = Field(..., min_length=1, description="Already-transcribed text (STT happens upstream for voice).")
    consent_verified: bool = Field(
        ..., description="Trusted from the caller (NestJS backend) -- this service does not re-verify consent."
    )


class TurnResponseSchema(BaseModel):
    response_text: str
    served_from: str
    tier: int | None = None
    crisis_flag: bool = False  # see docstring above -- unresolved 3-tier vs 4-state question
    interlock_triggered: bool = False
    requires_human_alert: bool = False
