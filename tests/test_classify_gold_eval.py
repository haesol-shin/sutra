from __future__ import annotations

import json
from pathlib import Path

import joblib

from nlp_term.classify.evaluate_gold import evaluate_gold_file
from nlp_term.validators import validate_metric_claim


class FixedModel:
    def __init__(self, labels: list[int]) -> None:
        self.labels = labels

    def predict(self, questions: list[str]) -> list[int]:
        return self.labels[: len(questions)]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_evaluate_gold_file_writes_heldout_metric(tmp_path: Path, monkeypatch) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    joblib.dump(FixedModel([0, 1, 2, 3, 4]), model_dir / "classifier.joblib")
    monkeypatch.setenv("NLP_TERM_MODEL_DIR", str(model_dir))
    input_path = tmp_path / "task1_human_gold.json"
    output_path = tmp_path / "gold_classifier_metrics.json"
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
                "question": "학사 공지는 어디 올라와?",
                "label": 1,
                "source_doc_id": None,
                "difficulty": "natural",
                "ambiguous_reason": None,
                "annotator": "human",
                "validated": True,
            },
            {
                "question": "개강일이랑 종강일 알려줘",
                "label": 2,
                "source_doc_id": None,
                "difficulty": "natural",
                "ambiguous_reason": None,
                "annotator": "human",
                "validated": True,
            },
            {
                "question": "학생식당 점심 메뉴 뭐야?",
                "label": 3,
                "source_doc_id": None,
                "difficulty": "natural",
                "ambiguous_reason": None,
                "annotator": "human",
                "validated": True,
            },
            {
                "question": "통학 버스 시간 알려줘",
                "label": 4,
                "source_doc_id": None,
                "difficulty": "natural",
                "ambiguous_reason": None,
                "annotator": "human",
                "validated": True,
            },
        ],
    )

    metrics = evaluate_gold_file(input_path, output_path)

    assert metrics["evaluation_set_type"] == "human_gold"
    assert metrics["dataset_origin"] == "human_gold"
    assert metrics["claim_level"] == "heldout_eval"
    assert metrics["row_count"] == 5
    assert metrics["macro_f1"] == 1.0
    validate_metric_claim(
        output_path,
        input_path=input_path,
        require_dataset_origin="human_gold",
        require_claim_level="heldout_eval",
    )
