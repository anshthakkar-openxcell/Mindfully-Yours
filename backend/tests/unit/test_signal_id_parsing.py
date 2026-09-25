"""
Unit tests for the regex/range-parsing utilities in app.ingestion.parsers.common, using the exact
example inputs documented (from the real client data) in
documnets/understanding/06_SIGNAL_ENRICHMENT_PIPELINE.md §3-4.
"""

from app.ingestion.parsers.common import (
    match_signal_in_trigger_condition,
    normalize_signal_id,
    parse_signal_id_range,
)


def test_parse_signal_id_range_comma_list():
    assert parse_signal_id_range("SIG-044, SIG-045") == [44, 45]


def test_parse_signal_id_range_hyphenated_range():
    # Must expand the range, not misread "SIG-041-043" as two IDs (41 and 43).
    assert parse_signal_id_range("SIG-041-043") == [41, 42, 43]


def test_parse_signal_id_range_word_range():
    assert parse_signal_id_range("SIG-085 to 093") == list(range(85, 94))


def test_parse_signal_id_range_messy_real_example():
    # Verbatim real-data example from documnets/understanding/06_SIGNAL_ENRICHMENT_PIPELINE.md §4
    # (PHYS-003's raw value) -- inconsistent spacing, no repeated "SIG-" prefix, trailing comma.
    result = parse_signal_id_range("Sig 004, 005, 006, 007, 001, 023, 152,155, 156, 193,")
    assert result == [4, 5, 6, 7, 1, 23, 152, 155, 156, 193]


def test_parse_signal_id_range_category_label_returns_empty():
    # EM- rows contain free-text category labels, not signal IDs -- this must return [], not raise.
    assert parse_signal_id_range("Motivation issue") == []


def test_normalize_signal_id_handles_lowercase_and_spacing():
    assert normalize_signal_id("Sig-285") == "SIG-285"
    assert normalize_signal_id("SIG 002") == "SIG-002"


def test_match_signal_in_trigger_condition_tolerant_of_prefix_styles():
    assert match_signal_in_trigger_condition("For MDD (SIG002-003), no other signal required", 2)
    assert match_signal_in_trigger_condition("primary signals from SIG 001-017", 1)
    assert not match_signal_in_trigger_condition("primary signals from SIG 001-017", 99)
