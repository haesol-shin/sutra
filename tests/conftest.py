"""Lean test collection filtering.

Lean-environment exclusions cover examples tests that depend on git-ignored
raw data not present in worker worktrees or CI. They apply only when
SUTRA_LEAN_TESTS=1, which worker worktrees and CI set per the AGENTS.md
worktree/CI policy. The main working tree runs the full suite.
"""

import os
from pathlib import Path

LEAN_TESTS = os.environ.get("SUTRA_LEAN_TESTS") == "1"

# Lean-only exclusions: examples parser tests that depend on git-ignored raw
# data (data/raw/*) absent in worker worktrees and CI.
SKIP_COLLECT_LEAN_ONLY = {
    "test_calendar_parser",
    "test_dining_parser",
    "test_shuttle_parser",
}

# Lean-only exclusion by exact path: the graduation builder test reads
# git-ignored raw graduation OCR data and writes generated index/report files,
# so it is not hermetic. Making it hermetic (tmp_path + fake extraction) is a
# documented follow-up; until then it runs only in the full local suite.
_GRADUATION_BUILDER = (
    Path(__file__).parent / "examples" / "cnu_campus" / "test_graduation_builder.py"
).resolve()


def pytest_ignore_collect(collection_path, config):
    if not LEAN_TESTS:
        return None
    if collection_path.stem in SKIP_COLLECT_LEAN_ONLY:
        return True
    if Path(collection_path).resolve() == _GRADUATION_BUILDER:
        return True
    return None
