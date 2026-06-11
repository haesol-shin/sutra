"""Legacy test collection filtering.

Two exclusion tiers:
- Import-blocked modules are excluded only when their required optional
  dependency is actually missing in the current environment.
- Lean-environment exclusions (legacy nlp_term suites, raw-data-dependent
  examples tests) apply only when SUTRA_LEAN_TESTS=1, which worker
  worktrees set per the AGENTS.md worktree policy. The main working tree
  runs the full suite.
"""

import importlib.util
import os

LEAN_TESTS = os.environ.get("SUTRA_LEAN_TESTS") == "1"

# Modules that fail to import when optional deps are missing.
SKIP_COLLECT_REQUIRES = {
    "test_graduation_requirement_adapter": "olefile",
    "test_prepare_from_sources": "olefile",
    "test_backend_evidence_separation": "sklearn",
    "test_chat_composer": "sklearn",
    "test_chat_provenance": "sklearn",
    "test_classify_gold_eval": "sklearn",
    "test_harness_safety_experiment": "sklearn",
    "test_phase_a_harness_contract": "sklearn",
    "test_probe39_experiment": "sklearn",
    "test_public_probe_experiment": "sklearn",
    "test_qwen_public_probe_baseline": "sklearn",
    "test_task1_augmentation": "joblib",
    "test_task1_gold_error_report": "sklearn",
    "test_task1_probe_eval": "joblib",
    "test_task1_router_policy": "sklearn",
    "test_task2_answer_eval_artifact": "sklearn",
    "test_task2_vertical_slice": "sklearn",
}

# Lean-only exclusions: legacy adapter suites and examples tests that
# depend on git-ignored raw data not present in worker worktrees.
SKIP_COLLECT_LEAN_ONLY = {
    "test_calendar_adapter",
    "test_dining_adapter",
    "test_notice_adapter",
    "test_shuttle_adapter",
    "test_source_audit",
    "test_calendar_parser",
    "test_dining_parser",
    "test_shuttle_parser",
}


def _missing(package: str) -> bool:
    return importlib.util.find_spec(package) is None


def pytest_ignore_collect(collection_path, config):
    module_name = collection_path.stem
    required = SKIP_COLLECT_REQUIRES.get(module_name)
    if required is not None and _missing(required):
        return True
    if LEAN_TESTS and module_name in SKIP_COLLECT_LEAN_ONLY:
        return True
    return None
