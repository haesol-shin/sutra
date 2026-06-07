from __future__ import annotations

import json
from pathlib import Path

from nlp_term.chat.compare_backends import compare_task2_backends


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_backend_comparison_does_not_mask_unavailable_llama(tmp_path: Path) -> None:
    gold_path = tmp_path / "task2_answer_eval_gold.json"
    facts_path = tmp_path / "task2_fact_gold.json"
    knowledge_path = tmp_path / "knowledge_seed.json"
    output_path = tmp_path / "task2_backend_comparison.json"
    missing_model_path = tmp_path / "missing.gguf"
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
                "must_not_claim": [],
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

    comparison = compare_task2_backends(
        gold_path=gold_path,
        facts_path=facts_path,
        knowledge_path=knowledge_path,
        output_path=output_path,
        model_path=missing_model_path,
        llama_limit=1,
    )

    assert comparison["evaluation_scope"] == "task2_backend_comparison"
    assert comparison["dataset_origin"] == "task2_gold"
    assert comparison["claim_level"] == "qualitative_check"
    assert comparison["backend_count"] == 2
    deterministic, llama = comparison["backend_runs"]
    assert deterministic["backend_requested"] == "deterministic"
    assert deterministic["status"] == "ran"
    assert deterministic["row_count"] == 1
    assert deterministic["fallback_used"] is False
    assert llama["backend_requested"] == "llama"
    assert llama["status"] == "unavailable"
    assert llama["row_count"] == 0
    assert llama["fallback_used"] is False
    assert llama["backend_used"] is None
    assert comparison["llama_quality_claim_allowed"] is False
