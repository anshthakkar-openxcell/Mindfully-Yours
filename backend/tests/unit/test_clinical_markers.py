"""
Tests the Clinical Markers table stays exactly what was extracted verbatim from
Clinical_Markers_Reference_Table (1).pdf -- see documnets/understanding/08_SAFETY_INTERLOCK_AND_TRIAGE.md
§2. This is a content-integrity test: if someone edits app.safety.clinical_markers.CLINICAL_MARKERS
in a way that drops a category, this test catches it.
"""

from app.safety.clinical_markers import CLINICAL_MARKERS, render_for_prompt

_EXPECTED_MARKERS = [
    "Speech",
    "Safety",
    "Functional Impact",
    "Reality Testing",
    "Emotional State",
    "Thought Organisation",
    "Thought Content",
    "Sensory Experiences",
    "Behavioural Changes",
    "Engagement with AI",
]


def test_all_ten_clinical_marker_categories_present_in_order():
    assert [m["marker"] for m in CLINICAL_MARKERS] == _EXPECTED_MARKERS


def test_every_marker_has_both_examples_and_style_tag():
    for marker in CLINICAL_MARKERS:
        assert marker["lower_concern_example"]
        assert marker["higher_concern_example"]
        assert marker["example_style"] in ("quote", "description")


def test_render_for_prompt_includes_every_marker_name():
    rendered = render_for_prompt()
    for name in _EXPECTED_MARKERS:
        assert name in rendered
