"""
Unit tests for the shared docx-parsing utilities in app.ingestion.parsers.docx_common. These are
pure-logic functions (no file I/O), tested with plain synthetic strings/lists -- no docx fixtures
needed. The heuristics themselves were derived from and verified against the real decrypted convo-
data files (see documnets/understanding/21_NEW_CONTENT_INGESTION_PLAN.md); these tests lock in that
verified behavior with fast, synthetic inputs.
"""

from app.ingestion.parsers.docx_common import collapse_doubled_runs, is_label_line


def test_is_label_line_accepts_short_lines_without_terminal_punctuation():
    assert is_label_line("Values")
    assert is_label_line("Anxiety")
    assert is_label_line("Clarifying Emotions")


def test_is_label_line_rejects_questions_and_statements():
    assert not is_label_line("What matters most to you in your life right now?")
    assert not is_label_line("I'd like to understand your perspective better.")
    assert not is_label_line("Let's take this one step at a time...")


def test_is_label_line_rejects_long_lines_even_without_punctuation():
    # A synthetic 60+ character line with no terminal punctuation should NOT be treated as a label
    # -- length is part of the heuristic specifically to avoid this false positive.
    long_line = "this is a very long line that happens to have no ending mark at all"
    assert len(long_line) >= 55
    assert not is_label_line(long_line)


def test_collapse_doubled_runs_collapses_a_repeated_group():
    # Confirmed real-data pattern (dbt-skills-workbook.docx): a multi-line group repeats back to
    # back due to overlapping DrawingML shapes.
    doubled = ["S", "Stop", "freeze", "S", "Stop", "freeze", "T", "Take a step back"]
    assert collapse_doubled_runs(doubled) == ["S", "Stop", "freeze", "T", "Take a step back"]


def test_collapse_doubled_runs_leaves_non_repeated_content_untouched():
    clean = ["Wise Mind", "STOP", "TIPP", "Opposite Action", "PLEASE"]
    assert collapse_doubled_runs(clean) == clean


def test_collapse_doubled_runs_handles_single_line_repeats():
    assert collapse_doubled_runs(["page 1 of 6", "page 1 of 6", "next"]) == ["page 1 of 6", "next"]


def test_collapse_doubled_runs_handles_nested_repeat_sizes():
    # A repeated pair sitting inside a longer sequence that also repeats -- collapse should find
    # the LARGEST matching run first at each position, not stop at the smallest.
    seq = ["A", "B", "A", "B", "C", "C"]
    result = collapse_doubled_runs(seq)
    assert result == ["A", "B", "C"]
