"""Guards on which red flags may ever get the gentler soft-zone path."""

from app.safety.interlock import CRITICAL_SELF_HARM_FLAGS, NON_DANGER_SOFT_ZONE_FLAGS, SOFT_ZONE_ELIGIBLE_FLAGS


def test_rf007_is_soft_zone_but_self_harm_flags_never_are():
    assert "RF-007" in SOFT_ZONE_ELIGIBLE_FLAGS
    # The one rule this module will never bend: suicide / self-harm flags always hard-escalate.
    assert not (SOFT_ZONE_ELIGIBLE_FLAGS & CRITICAL_SELF_HARM_FLAGS)
    assert "RF-025" not in SOFT_ZONE_ELIGIBLE_FLAGS


def test_non_danger_flags_are_a_subset_of_soft_zone_and_exclude_violence_flag():
    assert NON_DANGER_SOFT_ZONE_FLAGS <= SOFT_ZONE_ELIGIBLE_FLAGS
    assert "RF-028" not in NON_DANGER_SOFT_ZONE_FLAGS  # possible-violence keeps its doctor-written follow-up
