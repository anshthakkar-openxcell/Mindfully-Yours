"""
Shared pytest fixtures.

Per documnets/understanding/12_SECURITY_COMPLIANCE_DPDP.md §8: test environments use synthetic/
sample data ONLY -- never real user data or real clinical KB content, ever. Every fixture file
under tests/fixtures/synthetic_kb/ is fabricated for this test suite; it deliberately does not
resemble any real client-provided row.
"""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic_kb"


@pytest.fixture
def synthetic_kb_dir() -> Path:
    return FIXTURES_DIR
