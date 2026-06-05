from __future__ import annotations

from pathlib import Path

import joblib

from nlp_term.paths import ensure_parent, model_dir
from nlp_term.schemas import ClassificationInput, ClassificationOutput
from nlp_term.validators import read_json, write_json


KEYWORD_LABELS: list[tuple[int, tuple[str, ...]]] = [
    (0, ("졸업", "학점", "전공", "교양", "수료", "요건")),
    (1, ("공지", "장학", "모집", "안내문", "게시", "학사정보")),
    (2, ("학사일정", "수강신청", "수강 신청", "수강정정", "개강", "종강", "휴학", "복학")),
    (3, ("식단", "학식", "메뉴", "학생식당", "점심", "저녁", "아침")),
    (4, ("셔틀", "통학", "버스", "정류장", "시간표", "운행")),
]


def predict_label(question: str) -> int:
    compact = question.replace(" ", "")
    for label, keywords in KEYWORD_LABELS:
        if any(keyword.replace(" ", "") in compact for keyword in keywords):
            return label
    return 1


def predict_rows(rows: list[ClassificationInput]) -> list[ClassificationOutput]:
    model_path = model_dir() / "classifier.joblib"
    if model_path.exists():
        model = joblib.load(model_path)
        questions = [row.question for row in rows]
        labels = model.predict(questions).tolist()
        return [ClassificationOutput(question=row.question, label=int(label)) for row, label in zip(rows, labels)]
    return [ClassificationOutput(question=row.question, label=predict_label(row.question)) for row in rows]


def predict_file(input_path: Path, output_path: Path) -> None:
    payload = read_json(input_path)
    rows = [ClassificationInput.model_validate(row) for row in payload]
    outputs = predict_rows(rows)
    ensure_parent(output_path)
    write_json(output_path, outputs)
