from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import sutra.service as service

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACT = _REPO_ROOT / "examples" / "cnu-campus" / "model" / "router_classifier.npz"
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "router_expected_labels.json"


def _write_router_artifact(path: Path, **overrides: object) -> None:
    payload = {
        "schema_version": np.array(1),
        "source_classifier_sha256": np.array("test-sha"),
        "terms": np.array(["aa", "bb", "cc"], dtype="<U2"),
        "idf": np.array([1.0, 1.5, 2.0], dtype=np.float64),
        "coef": np.array(
            [
                [0.1, 0.2, 0.3],
                [0.2, 0.3, 0.4],
                [0.3, 0.4, 0.5],
                [0.4, 0.5, 0.6],
                [0.5, 0.6, 0.7],
            ],
            dtype=np.float64,
        ),
        "intercept": np.array([0.0, 0.1, 0.2, 0.3, 0.4], dtype=np.float64),
        "classes": np.array([0, 1, 2, 3, 4], dtype=np.int64),
    }
    payload.update(overrides)
    np.savez(path, **payload)


def _assert_load_raises(path: Path) -> Exception:
    service._load_router_artifact.cache_clear()
    try:
        service._load_router_artifact(path)
    except Exception as exc:
        assert isinstance(exc, (ValueError, KeyError, TypeError, OSError))
        return exc
    raise AssertionError(f"_load_router_artifact unexpectedly accepted {path}")


def test_corrupt_router_artifacts_raise_instead_of_silently_loading() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        bad_schema = tmp_path / "bad_schema.npz"
        _write_router_artifact(bad_schema, schema_version=np.array(2))
        assert "schema_version" in str(_assert_load_raises(bad_schema))

        bad_coef = tmp_path / "bad_coef.npz"
        _write_router_artifact(bad_coef, coef=np.zeros((5, 2), dtype=np.float64))
        assert "coef" in str(_assert_load_raises(bad_coef))

        bad_intercept = tmp_path / "bad_intercept.npz"
        _write_router_artifact(bad_intercept, intercept=np.zeros(4, dtype=np.float64))
        assert "intercept" in str(_assert_load_raises(bad_intercept))

        duplicate_terms = tmp_path / "duplicate_terms.npz"
        _write_router_artifact(duplicate_terms, terms=np.array(["aa", "aa", "cc"], dtype="<U2"))
        assert "duplicate" in str(_assert_load_raises(duplicate_terms))

        object_terms = tmp_path / "object_terms.npz"
        _write_router_artifact(object_terms, terms=np.array(["aa", "bb", "cc"], dtype=object))
        _assert_load_raises(object_terms)


def test_missing_router_artifact_returns_none_fallback() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "workspace-without-router-model"
        workspace.mkdir()
        missing_env_artifact = Path(tmp) / "missing" / "router_classifier.npz"
        config = SimpleNamespace(root=workspace)

        service._load_router_artifact.cache_clear()
        with mock.patch.dict(os.environ, {"SUTRA_ROUTER_ARTIFACT_PATH": str(missing_env_artifact)}):
            assert service._predict_router_label("오늘 학식 뭐예요?", config=config) is None


def test_corrupt_or_raising_router_load_returns_none_fallback() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        artifact_path = Path(tmp) / "router_classifier.npz"
        _write_router_artifact(artifact_path)

        with mock.patch.object(service, "_resolve_router_artifact_path", return_value=artifact_path):
            with mock.patch.object(service, "_load_router_artifact", side_effect=ValueError("boom")):
                assert service._predict_router_label("오늘 학식 뭐예요?", config=SimpleNamespace(root=Path(tmp))) is None


def test_real_router_artifact_handles_adversarial_inputs_without_crashing() -> None:
    service._load_router_artifact.cache_clear()
    artifact = service._load_router_artifact(_ARTIFACT)
    adversarial_questions = [
        "",
        "   \t\n  ",
        "학식" * 10_000,
        "😀🚀✨ 충남대학교 學食 공지 셔틀 졸업 календарь",
        "1234567890" * 100,
        "!@#$%^&*()_+-=[]{};':,./<>?" * 100,
    ]

    for question in adversarial_questions:
        label = service._router_predict_label_from_artifact(question, artifact)
        assert isinstance(label, int)
        assert label in {0, 1, 2, 3, 4}


def test_router_fixture_sha256_pin_matches_current_artifact_and_detects_tamper() -> None:
    fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    artifact_bytes = _ARTIFACT.read_bytes()
    current_sha = hashlib.sha256(artifact_bytes).hexdigest()
    tampered_sha = hashlib.sha256(artifact_bytes + b"tamper").hexdigest()

    assert fixture["artifact_sha256"] == current_sha
    assert tampered_sha != fixture["artifact_sha256"]
