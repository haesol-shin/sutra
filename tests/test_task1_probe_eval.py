from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("joblib") is None,
    reason="requires optional joblib dependency",
)


class FixedModel:
    def predict(self, questions: list[str]) -> list[int]:
        return [0 for _ in questions]


def test_probe_eval_rejects_training_question_overlap() -> None:
    pytest.importorskip("joblib")
    from nlp_term.classify.evaluate_probe import assert_no_eval_leakage
    from nlp_term.schemas import ClassificationExample, Task1HumanGoldExample

    train_rows = [
        ClassificationExample(question="복수전공하면 졸업학점 어떻게 돼?", label=0, validated=True)
    ]
    eval_rows = [
        Task1HumanGoldExample(
            question="복수전공하면 졸업학점 어떻게 돼?",
            label=0,
            difficulty="natural",
            annotator="orchestrator",
            validated=True,
        )
    ]

    with pytest.raises(ValueError, match="evaluation leakage"):
        assert_no_eval_leakage(train_rows, [eval_rows])


def test_probe_eval_reports_wrong_rows(tmp_path) -> None:
    joblib = pytest.importorskip("joblib")
    from nlp_term.classify.evaluate_probe import evaluate_model_on_rows
    from nlp_term.schemas import Task1HumanGoldExample

    model_path = tmp_path / "classifier.joblib"
    joblib.dump(FixedModel(), model_path)
    rows = [
        Task1HumanGoldExample(
            question="졸업학점 알려줘",
            label=0,
            difficulty="natural",
            annotator="test",
            validated=True,
        ),
        Task1HumanGoldExample(
            question="오늘 학식 메뉴",
            label=3,
            difficulty="natural",
            annotator="test",
            validated=True,
        ),
    ]

    result = evaluate_model_on_rows(model_path, "mini", rows)

    assert result.row_count == 2
    assert result.wrong == [{"question": "오늘 학식 메뉴", "gold": 3, "pred": 0}]
