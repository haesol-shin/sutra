"""Lean test collection filtering.

Lean-environment exclusions cover examples tests that depend on git-ignored
raw data not present in worker worktrees or CI. They apply only when
SUTRA_LEAN_TESTS=1, which worker worktrees and CI set per the AGENTS.md
worktree/CI policy. The main working tree runs the full suite.
"""

import os

LEAN_TESTS = os.environ.get("SUTRA_LEAN_TESTS") == "1"

# Lean-only exclusions: examples parser tests that depend on git-ignored raw
# data (data/raw/*) absent in worker worktrees and CI.
SKIP_COLLECT_LEAN_ONLY = {
    "test_calendar_parser",
    "test_dining_parser",
    "test_shuttle_parser",
}


def pytest_ignore_collect(collection_path, config):
    if LEAN_TESTS and collection_path.stem in SKIP_COLLECT_LEAN_ONLY:
        return True
    return None
