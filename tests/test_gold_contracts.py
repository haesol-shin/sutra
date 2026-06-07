from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from nlp_term.validators import validate_gold_data, validate_metric_claim


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _task1_gold_rows() -> list[dict[str, object]]:
    rows = []
    for label in range(5):
        for index in range(10):
            rows.append(
                {
                    "question": f"학생이 직접 쓴 label {label} 평가 질문 {index}",
                    "label": label,
                    "source_doc_id": None,
                    "difficulty": "natural",
                    "ambiguous_reason": None,
                    "annotator": "human",
                    "validated": True,
                }
            )
    return rows


def _task2_fact_gold_rows() -> list[dict[str, object]]:
    rows = []
    for label in range(5):
        for index in range(5):
            rows.append(
                {
                    "fact_id": f"fact_{label}_{index}",
                    "label": label,
                    "source_doc_id": f"doc_{label}_{index}",
                    "source_url": "https://plus.cnu.ac.kr",
                    "claim": f"label {label} 검증 사실 {index}",
                    "evidence_quote": f"label {label} 공식 근거 문장 {index}",
                    "answerable_scope": "static",
                }
            )
    return rows


def _task2_answer_gold_rows() -> list[dict[str, object]]:
    rows = []
    for index in range(25):
        label = index % 5
        rows.append(
            {
                "user": f"학생이 묻는 task2 자연 질문 {index}",
                "expected_fact_ids": [f"fact_{label}_0"],
                "must_not_claim": ["확인되지 않은 최신 정보"],
                "naturalness_score": None,
                "factuality_score": None,
            }
        )
    return rows


def _write_gold_dir(gold_dir: Path) -> None:
    _write_json(gold_dir / "task1_human_gold.json", _task1_gold_rows())
    _write_json(gold_dir / "task2_fact_gold.json", _task2_fact_gold_rows())
    _write_json(gold_dir / "task2_answer_eval_gold.json", _task2_answer_gold_rows())


def test_gold_data_contract_accepts_small_human_style_set(tmp_path: Path) -> None:
    _write_gold_dir(tmp_path)

    validate_gold_data(
        tmp_path,
        min_task1_rows=50,
        min_task1_per_label=10,
        min_task2_facts_per_label=5,
        min_task2_answer_rows=25,
    )


def test_gold_data_contract_rejects_chunk_leakage(tmp_path: Path) -> None:
    _write_gold_dir(tmp_path)
    rows = _task1_gold_rows()
    rows[0]["question"] = "chunk_3에 있는 졸업요건 알려줘"
    _write_json(tmp_path / "task1_human_gold.json", rows)

    with pytest.raises(ValueError, match="leakage"):
        validate_gold_data(tmp_path)


def test_metric_claim_requires_checksum_and_heldout_origin(tmp_path: Path) -> None:
    input_path = tmp_path / "task1_human_gold.json"
    _write_json(input_path, _task1_gold_rows())
    metrics_path = tmp_path / "gold_classifier_metrics.json"
    _write_json(
        metrics_path,
        {
            "evaluation_set_type": "human_gold",
            "dataset_origin": "human_gold",
            "claim_level": "heldout_eval",
            "input_path": str(input_path),
            "input_checksum": sha256(input_path.read_bytes()).hexdigest(),
            "macro_f1": 0.8,
        },
    )

    validate_metric_claim(
        metrics_path,
        input_path=input_path,
        require_dataset_origin="human_gold",
        require_claim_level="heldout_eval",
    )


def test_metric_claim_rejects_seed_as_heldout_eval(tmp_path: Path) -> None:
    input_path = tmp_path / "cls_train_seed.json"
    _write_json(input_path, _task1_gold_rows())
    metrics_path = tmp_path / "seed_classifier_metrics.json"
    _write_json(
        metrics_path,
        {
            "evaluation_set_type": "seed",
            "dataset_origin": "seed",
            "claim_level": "heldout_eval",
            "input_path": str(input_path),
            "input_checksum": sha256(input_path.read_bytes()).hexdigest(),
            "macro_f1": 1.0,
        },
    )

    with pytest.raises(ValueError, match="seed metrics cannot claim heldout evaluation"):
        validate_metric_claim(metrics_path, input_path=input_path)
