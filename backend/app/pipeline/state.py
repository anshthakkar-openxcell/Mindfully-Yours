"""
Running conversation state -- Step B of documnets/understanding/04_CONVERSATION_PIPELINE.md.
Read and written on EVERY turn, so it lives in Redis (single-digit-ms budget), not Postgres --
see documnets/understanding/11_DATA_MODEL_AND_STORAGE.md §4's Redis schema note.

"Each turn updates this state; it never starts from zero" -- this is what makes the AI feel like
it's listening across the whole conversation instead of reacting to only the last message.
"""

from __future__ import annotations

import orjson
from pydantic import BaseModel, Field
from redis.asyncio import Redis

STATE_KEY_PREFIX = "session"
STATE_TTL_SECONDS = 60 * 60 * 6  # 6 hours of inactivity -- align with product's session-timeout decision


class ConversationState(BaseModel):
    observed_signal_ids: list[str] = Field(default_factory=list)
    turn_count: int = 0
    candidate_pattern_id: int | None = None
    duration_established: bool = False
    impact_established: bool = False
    confidence_score: float = 0.0
    last_response_lengths: list[int] = Field(default_factory=list)  # feeds fallback Section C

    def record_turn(self, *, new_signal_ids: list[str], response_length: int) -> None:
        for sid in new_signal_ids:
            if sid not in self.observed_signal_ids:
                self.observed_signal_ids.append(sid)
        self.turn_count += 1
        self.last_response_lengths.append(response_length)
        self.last_response_lengths = self.last_response_lengths[-10:]  # bounded, not unbounded growth


def _key(session_id: str) -> str:
    return f"{STATE_KEY_PREFIX}:{session_id}:state"


async def load_state(session_id: str, *, redis: Redis) -> ConversationState:
    raw = await redis.get(_key(session_id))
    if raw is None:
        return ConversationState()
    return ConversationState.model_validate(orjson.loads(raw))


async def save_state(session_id: str, state: ConversationState, *, redis: Redis) -> None:
    await redis.set(_key(session_id), orjson.dumps(state.model_dump()), ex=STATE_TTL_SECONDS)
