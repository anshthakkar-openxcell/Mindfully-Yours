"""
Session summary + mood-tag generation -- pipeline step 14 of
documnets/understanding/04_CONVERSATION_PIPELINE.md ("Session close: summary + mood tag
persisted, feeds next turn's context"). Runs async, after the response has streamed, per
documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §8.
"""

from uuid import UUID

from app.core.logging import get_logger
from app.providers.base import LLMProvider

logger = get_logger(__name__)


async def generate_and_persist_summary(
    *, session_id: UUID, recent_turns: list[str], llm: LLMProvider
) -> None:
    """
    TODO: prompt the LLM (briefly -- this is a small, cheap summarization call, not the main
    conversation call) for a 1-2 sentence running summary + a single mood tag, then update
    app.db.models.conversation_session.ConversationSession.summary / .mood_tag for this session_id.
    Left unimplemented pending the ConversationSession ownership decision noted in that model's
    docstring (11_DATA_MODEL_AND_STORAGE.md §4).
    """
    logger.info("summary_generation_skipped_not_implemented", session_id=str(session_id))
