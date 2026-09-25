"""Unit tests for the pure, code-evaluated fallback logic in app.safety.fallback."""

from app.safety.fallback import ConversationShapeState, evaluate_fallback


def _base_state(**overrides) -> ConversationShapeState:
    defaults = dict(
        turn_count=1,
        consecutive_short_responses=0,
        confidence_score=1.0,
        topic_diversity_score=0.0,
        stated_wellbeing_contradicts_content=False,
        seconds_since_last_response=1.0,
    )
    defaults.update(overrides)
    return ConversationShapeState(**defaults)


def test_no_fallback_when_conversation_is_healthy():
    result = evaluate_fallback(_base_state(), confidence_threshold=0.5)
    assert result.triggered is False


def test_section_a_insufficient_signal_on_long_low_confidence_conversation():
    state = _base_state(turn_count=16, confidence_score=0.2)
    result = evaluate_fallback(state, confidence_threshold=0.5)
    assert result.triggered is True
    assert result.section == "A_insufficient"


def test_section_b_contradictory_signal():
    state = _base_state(stated_wellbeing_contradicts_content=True)
    result = evaluate_fallback(state, confidence_threshold=0.5)
    assert result.triggered is True
    assert result.section == "B_contradictory"


def test_section_c_disengagement_on_repeated_short_responses():
    state = _base_state(consecutive_short_responses=8)
    result = evaluate_fallback(state, confidence_threshold=0.5)
    assert result.triggered is True
    assert result.section == "C_disengagement"
