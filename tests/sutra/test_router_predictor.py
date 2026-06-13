from __future__ import annotations

from pathlib import Path

import numpy as np

from sutra.service import (
    RouterClassifierArtifact,
    _load_router_artifact,
    _router_predict_label_from_artifact,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_ROUTER_ARTIFACT = _REPO_ROOT / "examples" / "cnu-campus" / "model" / "router_classifier.npz"


def _toy_artifact() -> RouterClassifierArtifact:
    terms = np.asarray([" 가 ", " ab", " !!", " b"], dtype="<U3")
    coef = np.zeros((5, len(terms)), dtype=np.float64)
    coef[2, 0] = 10.0
    coef[1, 1] = 10.0
    coef[3, 2] = 10.0
    coef[4, 3] = 10.0
    intercept = np.asarray([1.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)
    classes = np.asarray([0, 1, 2, 3, 4], dtype=np.int64)
    return RouterClassifierArtifact(
        schema_version=1,
        source_classifier_sha256="toy",
        terms=terms,
        idf=np.ones(len(terms), dtype=np.float64),
        coef=coef,
        intercept=intercept,
        classes=classes,
        vocabulary={str(term): index for index, term in enumerate(terms.tolist())},
    )


def test_char_wb_collapses_multiple_spaces_like_single_spaces() -> None:
    artifact = _toy_artifact()

    assert _router_predict_label_from_artifact("A   B", artifact) == 4
    assert _router_predict_label_from_artifact("a b", artifact) == 4


def test_char_wb_keeps_short_word_ngram_for_one_char_korean_token() -> None:
    artifact = _toy_artifact()

    assert _router_predict_label_from_artifact("가", artifact) == 2


def test_char_wb_lowercases_mixed_latin_case() -> None:
    artifact = _toy_artifact()

    assert _router_predict_label_from_artifact("Ab", artifact) == 1


def test_char_wb_handles_punctuation_only_token() -> None:
    artifact = _toy_artifact()

    assert _router_predict_label_from_artifact("!!", artifact) == 3


def test_unseen_vocabulary_token_contributes_nothing_and_uses_intercept() -> None:
    artifact = _toy_artifact()

    assert _router_predict_label_from_artifact("쀍쀍쀍", artifact) == 0


def test_empty_and_whitespace_only_input_use_intercept_without_dividing_by_zero() -> None:
    artifact = _toy_artifact()

    assert _router_predict_label_from_artifact("", artifact) == 0
    assert _router_predict_label_from_artifact(" \t\n  ", artifact) == 0


def test_frozen_router_artifact_loads_without_pickle() -> None:
    with np.load(_ROUTER_ARTIFACT, allow_pickle=False) as data:
        assert data["schema_version"].item() == 1
        assert data["terms"].dtype.kind == "U"
        assert data["terms"].shape == (5986,)
        assert data["idf"].dtype == np.float64
        assert data["coef"].dtype == np.float64
        assert data["intercept"].dtype == np.float64
        assert data["classes"].dtype == np.int64


def test_real_questions_match_expected_router_labels() -> None:
    artifact = _load_router_artifact(_ROUTER_ARTIFACT)

    cases = {
        "오늘 1학생회관 점심": 3,
        "졸업요건": 0,
        "셔틀 시간표": 4,
        "학사일정": 2,
        "최근 공지": 1,
    }
    for question, expected_label in cases.items():
        assert _router_predict_label_from_artifact(question, artifact) == expected_label
