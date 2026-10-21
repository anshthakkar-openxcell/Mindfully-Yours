"""Pure-logic tests for the therapist-first response pieces (no database or network)."""

from app.pipeline.curated_match import classify_band
from app.pipeline.guardrail import check_rephrase_faithful
from app.pipeline.prompt_builder import build_rephrase_prompt
from app.pipeline.welcome import fill_name


def test_bands_follow_thresholds_and_opening_margin():
    # defaults: strong 0.85 (+0.05 for a mid-conversation reply), partial 0.62
    assert classify_band(0.90, is_opening=True) == "strong"
    assert classify_band(0.86, is_opening=True) == "strong"
    assert classify_band(0.86, is_opening=False) == "partial"  # needs 0.90 mid-conversation
    assert classify_band(0.91, is_opening=False) == "strong"
    assert classify_band(0.66, is_opening=True) == "partial"
    assert classify_band(0.55, is_opening=True) == "none"  # the 0.50-0.56 wrong matches seen in testing


def test_rephrase_guard_accepts_a_light_reword():
    original = "It sounds like you feel homesick and lonely in the new place. How can I help you?"
    ok = "It sounds like you feel lonely since moving to a new place for college. How can I help you?"
    assert check_rephrase_faithful(ok, original=original).passed


def test_rephrase_guard_rejects_added_advice_numbers_and_padding():
    original = "That sounds hard. What has been the toughest part?"
    advice = "That sounds hard. You should try meditation and journaling daily, and exercise more often."
    assert not check_rephrase_faithful(advice, original=original).passed  # drifted wording
    assert not check_rephrase_faithful("That sounds hard. Call 9152987821 now.", original=original).passed
    assert not check_rephrase_faithful("That sounds hard. " * 12, original=original).passed  # padded
    assert not check_rephrase_faithful("   ", original=original).passed


def test_rephrase_prompt_carries_the_therapist_reply_and_the_no_additions_rule():
    prompt = build_rephrase_prompt(
        persona="You are warm.",
        user_message="I feel alone here.",
        examples=[("I miss home", "That sounds hard."), ("No friends here", "What has been toughest?")],
        recent_turns=[],
    )
    assert "That sounds hard." in prompt and "What has been toughest?" in prompt  # ALL examples are shown
    assert "I miss home" in prompt and "Do NOT add advice" in prompt and "I feel alone here." in prompt


def test_welcome_name_slot():
    assert fill_name("Hi user, what's on your mind today?", "Asha") == "Hi Asha, what's on your mind today?"
    assert fill_name("Hey user. thank you for taking the step", None) == "Hey there. thank you for taking the step"
    assert "user" not in fill_name("Hi user, welcome.", "  ").lower()
