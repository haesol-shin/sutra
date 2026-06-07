from __future__ import annotations

import json
from pathlib import Path

from nlp_term.chat.evaluate_gold import evaluate_task2_gold_answers
from nlp_term.validators import validate_metric_claim


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_task2_answer_eval_artifact_links_answers_to_gold_facts(tmp_path: Path) -> None:
    gold_path = tmp_path / "task2_answer_eval_gold.json"
    facts_path = tmp_path / "task2_fact_gold.json"
    knowledge_path = tmp_path / "knowledge_seed.json"
    output_path = tmp_path / "task2_answer_eval.json"
    _write_json(
        facts_path,
        [
            {
                "fact_id": "grad_credit",
                "label": 0,
                "source_doc_id": "grad_doc_1",
                "source_url": "https://plus.cnu.ac.kr/grad",
                "claim": "졸업 기준은 전공과 교양 학점 이수 기준을 확인해야 한다.",
                "evidence_quote": "전공과 교양 학점 이수 기준을 확인해야 한다.",
                "answerable_scope": "static",
            }
        ],
    )
    _write_json(
        gold_path,
        [
            {
                "user": "졸업 전공 학점 기준 알려줘",
                "expected_fact_ids": ["grad_credit"],
                "must_not_claim": ["확인되지 않은 최신 정보"],
                "naturalness_score": None,
                "factuality_score": None,
            }
        ],
    )
    _write_json(
        knowledge_path,
        [
            {
                "doc_id": "grad_doc_1",
                "label": 0,
                "domain": "graduation",
                "title": "졸업요건 안내",
                "body": "졸업 기준은 전공과 교양 학점 이수 기준을 확인해야 한다.",
                "source_url": "https://plus.cnu.ac.kr/grad",
                "source_id": "graduation",
                "metadata": {},
            }
        ],
    )

    metrics = evaluate_task2_gold_answers(
        gold_path=gold_path,
        facts_path=facts_path,
        knowledge_path=knowledge_path,
        output_path=output_path,
        backend="deterministic",
    )

    assert metrics["evaluation_scope"] == "task2_answer_gold_eval"
    assert metrics["evaluation_set_type"] == "task2_gold"
    assert metrics["dataset_origin"] == "task2_gold"
    assert metrics["claim_level"] == "qualitative_check"
    assert metrics["row_count"] == 1
    assert metrics["backend_used"] == "deterministic"
    assert metrics["fallback_used"] is False
    assert metrics["fact_recall"] == 1.0
    assert metrics["must_not_claim_violation_count"] == 0
    assert metrics["source_hint_rate"] == 1.0
    assert metrics["naturalness_heuristic_pass_rate"] == 1.0
    assert metrics["rows"][0]["matched_fact_ids"] == ["grad_credit"]
    assert metrics["rows"][0]["retrieved_doc_ids"] == ["grad_doc_1"]
    validate_metric_claim(
        output_path,
        input_path=gold_path,
        require_dataset_origin="task2_gold",
        require_claim_level="qualitative_check",
    )
