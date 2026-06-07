from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_data_expansion_priority_report_has_baselines_and_gates() -> None:
    report = (ROOT / "docs" / "next_data_expansion_priorities.md").read_text(encoding="utf-8")

    required_phrases = [
        "Priority 1",
        "졸업",
        "PDF",
        "HWP",
        "acceptance gate",
        "baseline",
        "Task 1",
        "Task 2",
        "macro F1",
        "naturalness heuristic pass rate",
        "hit@3",
        "generalization",
    ]
    for phrase in required_phrases:
        assert phrase in report


def test_goal_23_summary_evidence_lists_all_steps() -> None:
    summary = (ROOT / "docs" / "evidence" / "goal-2.3-summary-2026-06-07.json").read_text(
        encoding="utf-8"
    )

    for step_id in [
        "omc-ignore",
        "task1-gold-error-analysis",
        "task1-improvement-candidates",
        "task2-gold-answer-eval",
        "task2-backend-comparison",
        "retrieval-bottleneck-diagnosis",
        "next-data-expansion-priorities",
    ]:
        assert step_id in summary
