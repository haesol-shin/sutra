from __future__ import annotations

import joblib
import pytest

from nlp_term.classify import predict
from nlp_term.schemas import ClassificationInput


class FixedModel:
    def __init__(self, labels: list[int]) -> None:
        self.labels = labels

    def predict(self, questions: list[str]) -> list[int]:
        assert questions
        return self.labels[: len(questions)]


def test_predict_rows_requires_classifier_model(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("NLP_TERM_MODEL_DIR", str(tmp_path))

    with pytest.raises(RuntimeError, match="classifier\\.joblib.*필수"):
        predict.predict_rows([ClassificationInput(question="오늘 학식 메뉴 알려줘")])


def test_predict_rows_uses_joblib_model_only(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("NLP_TERM_MODEL_DIR", str(tmp_path))
    joblib.dump(FixedModel([4, 0]), tmp_path / "classifier.joblib")

    outputs = predict.predict_rows(
        [
            ClassificationInput(question="졸업요건 변경 안내 공지가 공지사항에 올라왔는지 찾아줘"),
            ClassificationInput(question="오늘 학식 메뉴 알려줘"),
        ]
    )

    assert [row.label for row in outputs] == [4, 0]
    assert predict.predict_label("셔틀 시간표 알려줘") == 4


def test_keyword_fallback_api_is_removed() -> None:
    assert not hasattr(predict, "KEYWORD_LABELS")
