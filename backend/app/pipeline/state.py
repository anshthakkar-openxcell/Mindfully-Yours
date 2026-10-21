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


MAX_STORED_RECENT_TURNS = 10  # bounded, not unbounded growth -- app.pipeline.prompt_builder trims
# this further to MAX_RECENT_TURNS (6) when actually assembling a prompt; this is just storage.


class ConversationState(BaseModel):
    observed_signal_ids: list[str] = Field(default_factory=list)
    turn_count: int = 0
    candidate_pattern_id: int | None = None
    duration_established: bool = False
    impact_established: bool = False
    confidence_score: float = 0.0
    last_response_lengths: list[int] = Field(default_factory=list)  # feeds fallback Section C
    # TEMPORARY fix (2026-10-01): previously always empty (`recent_turns=[]` was hardcoded in
    # orchestrator.py with a TODO to load it from here) -- meaning every turn was answered with no
    # memory of anything said earlier in the conversation. This stores the last few turns' text
    # verbatim so app.pipeline.prompt_builder.build_prompt can actually include them. It is
    # deliberately plain verbatim text, not a summary -- the real intended design (a running
    # summary via ConversationSession, see orchestrator.py's other TODO) is still pending on that
    # session-ownership question; this is the quick, direct fix to restore basic context memory
    # now rather than wait on that larger piece.
    recent_turns: list[str] = Field(default_factory=list)
    # How many therapist clarifying questions in a row have been asked (app.pipeline.curated_match).
    # Reset whenever a therapist reply is served, so it only limits back-to-back clarifying.
    clarifications_asked: int = 0

    def record_turn(self, *, new_signal_ids: list[str], user_text: str, response_text: str) -> None:
        for sid in new_signal_ids:
            if sid not in self.observed_signal_ids:
                self.observed_signal_ids.append(sid)
        self.turn_count += 1
        self.last_response_lengths.append(len(response_text))
        self.last_response_lengths = self.last_response_lengths[-10:]  # bounded, not unbounded growth

        if response_text:  # an interrupted turn can produce an empty response_text -- nothing to record
            self.recent_turns.append(f"User: {user_text}\nAssistant: {response_text}")
            self.recent_turns = self.recent_turns[-MAX_STORED_RECENT_TURNS:]


def _key(session_id: str) -> str:
    return f"{STATE_KEY_PREFIX}:{session_id}:state"


async def load_state(session_id: str, *, redis: Redis) -> ConversationState:
    raw = await redis.get(_key(session_id))
    if raw is None:
        return ConversationState()
    return ConversationState.model_validate(orjson.loads(raw))


async def save_state(session_id: str, state: ConversationState, *, redis: Redis) -> None:
    await redis.set(_key(session_id), orjson.dumps(state.model_dump()), ex=STATE_TTL_SECONDS)
