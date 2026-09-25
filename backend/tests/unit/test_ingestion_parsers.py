"""
Unit tests for app.ingestion.parsers against synthetic fixtures (tests/fixtures/synthetic_kb/) --
never real KB content, per documnets/understanding/12_SECURITY_COMPLIANCE_DPDP.md §8.
"""

from app.ingestion.parsers.red_flags import parse_red_flags
from app.ingestion.parsers.signal_legend import parse_signal_legend


def test_parse_signal_legend_normalizes_red_flag_casing(synthetic_kb_dir):
    records = parse_signal_legend(synthetic_kb_dir / "signals_sample.csv")

    by_id = {r["signal_id"]: r for r in records}
    assert by_id["SIG-001"]["red_flag"] is False
    assert by_id["SIG-002"]["red_flag"] is True
    # Confirmed real-data quirk: lowercase 'no' must normalize the same as 'No'.
    assert by_id["SIG-003"]["red_flag"] is False


def test_parse_signal_legend_severity_range(synthetic_kb_dir):
    records = parse_signal_legend(synthetic_kb_dir / "signals_sample.csv")
    assert all(r["severity"] in (1, 2, 3) for r in records)


def test_parse_red_flags_forward_fills_flag_id_and_merges_phrases(synthetic_kb_dir):
    records = parse_red_flags(synthetic_kb_dir / "red_flags_sample.csv")
    by_id = {r["flag_id"]: r for r in records}

    assert set(by_id) == {"RF-901", "RF-902"}
    # Two source rows for RF-901 (continuation row has a blank Flag ID) must merge into one record
    # with both trigger phrases -- this is the forward-fill behavior confirmed necessary for the
    # real sheet 7 layout.
    assert len(by_id["RF-901"]["trigger_phrases"]) == 2


def test_parse_red_flags_preserves_missing_bot_script_as_none(synthetic_kb_dir):
    """
    Confirmed real-data gap (RF-028..031 in the actual sheet, see
    documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #1): a flag with no bot_script must
    parse to `None`, never an empty string or a placeholder -- app.safety.interlock and
    MissingBotScriptError specifically branch on `is None`.
    """
    records = parse_red_flags(synthetic_kb_dir / "red_flags_sample.csv")
    by_id = {r["flag_id"]: r for r in records}

    assert by_id["RF-901"]["bot_script"] == "This is a synthetic verbatim script for testing."
    assert by_id["RF-902"]["bot_script"] is None
