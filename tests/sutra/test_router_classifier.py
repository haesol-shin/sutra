"""Regression pin for the sklearn-free numpy router predictor.

This test imports ONLY the numpy predictor + the committed label fixture; it
never imports joblib/sklearn and never reads the frozen model/classifier.joblib.
The expected labels were generated from the parity-proven artifact (see
docs/evidence/router-sklearn-numpy-parity-2026-06-13.json, 100% sklearn-vs-numpy
label match) so any future drift in the predictor or artifact fails here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sutra.service import _load_router_artifact, _router_predict_label_from_artifact

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACT = _REPO_ROOT / "examples" / "cnu-campus" / "model" / "router_classifier.npz"
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "router_expected_labels.json"


def _fixture() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_router_fixture_matches_committed_artifact_sha256() -> None:
    data = _fixture()
    sha = hashlib.sha256(_ARTIFACT.read_bytes()).hexdigest()
    assert data["artifact_sha256"] == sha
    assert data["row_count"] == len(data["rows"]) == 53


def test_router_predictor_reproduces_expected_labels() -> None:
    data = _fixture()
    artifact = _load_router_artifact(_ARTIFACT)
    mismatches = [
        (row["id"], row["question"], row["expected_label"], label)
        for row in data["rows"]
        if (label := _router_predict_label_from_artifact(row["question"], artifact))
        != row["expected_label"]
    ]
    assert mismatches == []
