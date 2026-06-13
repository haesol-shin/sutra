from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import joblib

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sutra.service import (  # noqa: E402
    _load_router_artifact,
    _router_decision_scores_from_artifact,
    _router_predict_label_from_artifact,
)

MODEL_PATH = REPO_ROOT / "model" / "classifier.joblib"
ARTIFACT_PATH = REPO_ROOT / "examples" / "cnu-campus" / "model" / "router_classifier.npz"
EVIDENCE_PATH = REPO_ROOT / "docs" / "evidence" / "router-sklearn-numpy-parity-2026-06-13.json"

CORPORA: tuple[tuple[Path, str | None], ...] = (
    (REPO_ROOT / "data" / "gold" / "task1_human_gold.json", "label"),
    (REPO_ROOT / "data" / "cls_train_augmented.json", "label"),
    (REPO_ROOT / "data" / "gold" / "task1_probe_v2.json", "label"),
    (REPO_ROOT / "data" / "gold" / "task2_public_probe_eval.json", "expected_label"),
    (REPO_ROOT / "data" / "gold" / "task2_probe39_eval.json", "expected_label"),
)

ADVERSARIAL_QUESTIONS: tuple[tuple[str, str], ...] = (
    ("multiple_spaces", "오늘    1학생회관     점심"),
    ("tabs_newlines", "셔틀\t시간표\n알려줘"),
    ("one_char_korean", "밥"),
    ("mixed_latin_case", "CNU Shuttle BUS"),
    ("punctuation_only", "?!?! ..."),
    ("unseen_vocab", "zzzz_unseen_vocab_token_987654321"),
    ("empty", ""),
    ("whitespace_only", " \t\n  "),
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_corpus_rows(path: Path, label_field: str | None) -> list[dict[str, Any]]:
    payload = _read_json(path)
    if not isinstance(payload, list):
        raise TypeError(f"expected list payload: {path}")

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise TypeError(f"expected object row in {path} at index {index}")
        question = item.get("question")
        if not isinstance(question, str):
            raise KeyError(f"missing string question in {path} at index {index}")
        row: dict[str, Any] = {
            "source": path.relative_to(REPO_ROOT).as_posix(),
            "id_or_index": item.get("id", index),
            "question": question,
        }
        if label_field is not None:
            row["expected_label"] = item.get(label_field)
        rows.append(row)
    return rows


def _top2_margin(scores: Any) -> float:
    ordered = sorted((float(score) for score in scores), reverse=True)
    if len(ordered) < 2:
        return 0.0
    return ordered[0] - ordered[1]


def build_report() -> dict[str, Any]:
    source_bytes = MODEL_PATH.read_bytes()
    model_sha256 = hashlib.sha256(source_bytes).hexdigest()
    sklearn_model = joblib.load(MODEL_PATH)
    artifact = _load_router_artifact(ARTIFACT_PATH)

    corpus_summary: list[dict[str, Any]] = []
    inputs: list[dict[str, Any]] = []
    for path, label_field in CORPORA:
        rows = _load_corpus_rows(path, label_field)
        corpus_summary.append({"path": path.relative_to(REPO_ROOT).as_posix(), "row_count": len(rows)})
        inputs.extend(rows)

    adversarial_rows = [
        {"source": "adversarial", "id_or_index": row_id, "question": question}
        for row_id, question in ADVERSARIAL_QUESTIONS
    ]
    corpus_summary.append({"path": "adversarial", "row_count": len(adversarial_rows)})
    inputs.extend(adversarial_rows)

    rows: list[dict[str, Any]] = []
    mismatch_count = 0
    for item in inputs:
        question = item["question"]
        sklearn_label = int(sklearn_model.predict([question])[0])
        numpy_label = _router_predict_label_from_artifact(question, artifact)
        match = sklearn_label == numpy_label
        if not match:
            mismatch_count += 1
        scores = _router_decision_scores_from_artifact(question, artifact)
        result = {
            "source": item["source"],
            "id_or_index": item["id_or_index"],
            "question": question,
            "sklearn_label": sklearn_label,
            "numpy_label": numpy_label,
            "match": match,
            "top2_margin": _top2_margin(scores),
        }
        if "expected_label" in item:
            result["expected_label"] = item["expected_label"]
        rows.append(result)

    total_count = len(rows)
    match_rate = (total_count - mismatch_count) / total_count if total_count else 0.0
    return {
        "model_path": MODEL_PATH.relative_to(REPO_ROOT).as_posix(),
        "model_sha256": model_sha256,
        "artifact_path": ARTIFACT_PATH.relative_to(REPO_ROOT).as_posix(),
        "artifact_source_classifier_sha256": artifact.source_classifier_sha256,
        "corpus": corpus_summary,
        "rows": rows,
        "mismatch_count": mismatch_count,
        "total_count": total_count,
        "match_rate": match_rate,
        "pass": mismatch_count == 0,
    }


def main() -> None:
    report = build_report()
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "pass={pass_value} match_rate={match_rate:.12f} mismatch_count={mismatch_count} total_count={total_count} evidence={evidence}".format(
            pass_value=str(report["pass"]).lower(),
            match_rate=report["match_rate"],
            mismatch_count=report["mismatch_count"],
            total_count=report["total_count"],
            evidence=EVIDENCE_PATH.relative_to(REPO_ROOT).as_posix(),
        )
    )
    if not report["pass"]:
        mismatches = [row for row in report["rows"] if not row["match"]]
        print(json.dumps(mismatches, ensure_ascii=False, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
