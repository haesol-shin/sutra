from __future__ import annotations

from pathlib import Path

import joblib

from nlp_term.paths import ensure_parent, model_dir
from nlp_term.schemas import ClassificationInput, ClassificationOutput
from nlp_term.validators import read_json, write_json


def predict_rows(rows: list[ClassificationInput]) -> list[ClassificationOutput]:
    model_path = model_dir() / "classifier.joblib"
    if not model_path.exists():
        raise RuntimeError(
            f"분류 모델 파일 {model_path} 은 필수입니다. "
            "채점 전에 model/classifier.joblib 파일을 함께 제출해 주세요."
        )
    model = joblib.load(model_path)
    questions = [row.question for row in rows]
    predictions = model.predict(questions)
    labels = predictions.tolist() if hasattr(predictions, "tolist") else list(predictions)
    return [ClassificationOutput(question=row.question, label=int(label)) for row, label in zip(rows, labels)]


def predict_label(question: str) -> int:
    """Compatibility wrapper for legacy callers; still uses the joblib model only."""
    return predict_rows([ClassificationInput(question=question)])[0].label


def predict_file(input_path: Path, output_path: Path) -> None:
    payload = read_json(input_path)
    rows = [ClassificationInput.model_validate(row) for row in payload]
    outputs = predict_rows(rows)
    ensure_parent(output_path)
    write_json(output_path, outputs)
