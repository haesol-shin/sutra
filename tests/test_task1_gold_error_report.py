from __future__ import annotations

import json
from pathlib import Path

import joblib

from nlp_term.classify.analyze_gold_errors import analyze_gold_errors_file
from nlp_term.validators import validate_metric_claim


class FixedModel:
    def __init__(self, labels: list[int]) -> None:
        self.labels = labels

    def predict(self, questions: list[str]) -> list[int]:
        return self.labels[: len(questions)]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_task1_gold_error_report_covers_every_misclassification(tmp_path: Path, monkeypatch) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    joblib.dump(FixedModel([0, 1, 1]), model_dir / "classifier.joblib")
    monkeypatch.setenv("NLP_TERM_MODEL_DIR", str(model_dir))
    input_path = tmp_path / "task1_human_gold.json"
    output_path = tmp_path / "task1_gold_error_report.json"
    _write_json(
        input_path,
        [
            {
                "question": "졸업 조건은 어디서 확인해?",
                "label": 0,
                "source_doc_id": None,
                "difficulty": "natural",
                "ambiguous_reason": None,
                "annotator": "human",
                "validated": True,
            },
            {
                "question": "장학 공지는 어디 올라와?",
                "label": 1,
                "source_doc_id": None,
                "difficulty": "natural",
                "ambiguous_reason": None,
                "annotator": "human",
                "validated": True,
            },
            {
                "question": "이번 학기 일정 알려줘",
                "label": 2,
                "source_doc_id": None,
                "difficulty": "boundary",
                "ambiguous_reason": "일정이라는 말만 있어 공지와 헷갈릴 수 있음",
                "annotator": "human",
                "validated": True,
            },
        ],
    )

    report = analyze_gold_errors_file(input_path, output_path)

    assert report["evaluation_scope"] == "task1_human_gold_error_report"
    assert report["dataset_origin"] == "human_gold"
    assert report["claim_level"] == "heldout_eval"
    assert report["row_count"] == 3
    assert report["error_count"] == 1
    assert report["confusion_matrix"]["2"]["1"] == 1
    assert report["per_difficulty_failure_counts"] == {"boundary": 1}
    assert report["false_negative_counts"]["2"] == 1
    assert report["false_positive_counts"]["1"] == 1
    assert report["errors"] == [
        {
            "question": "이번 학기 일정 알려줘",
            "expected_label": 2,
            "predicted_label": 1,
            "difficulty": "boundary",
            "ambiguous_reason": "일정이라는 말만 있어 공지와 헷갈릴 수 있음",
            "error_type": "2->1",
        }
    ]
    validate_metric_claim(
        output_path,
        input_path=input_path,
        require_dataset_origin="human_gold",
        require_claim_level="heldout_eval",
    )
