"""
Import every model here so `Base.metadata` is fully populated for Alembic autogenerate and for
`Base.metadata.create_all()` in tests. Do not import models directly from app.db.models.kb etc.
in application code paths that need to stay decoupled -- prefer importing from this package.
"""

from app.db.models.audit import TurnAuditLog
from app.db.models.conversation_session import ConversationSession
from app.db.models.kb import (
    KBContentChunk,
    KBFallbackScenario,
    KBRedFlag,
    KBRoutingRule,
    KBSignal,
    KBSufficiencyPattern,
    KBSymptom,
    KBVersion,
    PromptConfig,
)
from app.db.models.kb_convo_content import (
    KBAnxietySituation,
    KBCareerLookup,
    KBClarificationPhrase,
    KBEmotionPhrase,
    KBGuardrailRule,
    KBLayerContent,
    KBScenario,
    KBTierQuestionBank,
)

__all__ = [
    "TurnAuditLog",
    "ConversationSession",
    "KBContentChunk",
    "KBFallbackScenario",
    "KBRedFlag",
    "KBRoutingRule",
    "KBSignal",
    "KBSufficiencyPattern",
    "KBSymptom",
    "KBVersion",
    "PromptConfig",
    "KBAnxietySituation",
    "KBCareerLookup",
    "KBClarificationPhrase",
    "KBEmotionPhrase",
    "KBGuardrailRule",
    "KBLayerContent",
    "KBScenario",
    "KBTierQuestionBank",
]
