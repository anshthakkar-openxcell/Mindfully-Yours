#!/usr/bin/env python3
"""
Convenience wrapper: ingest the REAL client knowledge base from documnets/knowledgebase/ into a
local dev database. This is a thin call into app.ingestion.cli -- see that module for the actual
logic.

NOTE on data handling: this is different from a pytest test environment. The clinical KB content
in documnets/knowledgebase/ is the product's actual knowledge base (client-provided source of
truth), not real end-user conversation data / PII -- ingesting it into a local dev DB is the
ingestion pipeline's normal job, not a violation of
documnets/understanding/12_SECURITY_COMPLIANCE_DPDP.md §8 (that rule is about real USER data and
real conversation transcripts never appearing in test/dev environments, and about never pasting
this content into an unrelated third-party tool). Automated tests (tests/) still use only the
synthetic fixtures in tests/fixtures/synthetic_kb/, never this real content.

Usage:
    python scripts/seed_kb.py
"""

import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
KB_DIR = REPO_ROOT.parent / "documnets" / "knowledgebase"


def main() -> None:
    label = f"dev-{date.today().isoformat()}"
    cmd = [
        sys.executable,
        "-m",
        "app.ingestion.cli",
        "ingest",
        "--kb-dir",
        str(KB_DIR),
        "--label",
        label,
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


if __name__ == "__main__":
    main()
