from __future__ import annotations

import json
from pathlib import Path

from nlp_term.retrieve.diagnose import diagnose_retrieval_bottlenecks


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_retrieval_bottleneck_report_splits_coverage_gap_from_ranking(tmp_path: Path) -> None:
    facts_path = tmp_path / "task2_fact_gold.json"
    knowledge_path = tmp_path / "knowledge_seed.json"
    output_path = tmp_path / "retrieval_bottleneck_diagnosis.json"
    _write_json(
        facts_path,
        [
            {
                "fact_id": "grad_credit",
                "label": 0,
                "source_doc_id": "grad_doc_1",
                "source_url": "https://plus.cnu.ac.kr/grad",
                "claim": "졸업 기준은 전공과 교양 학점 이수 기준을 확인해야 한다.",
                "evidence_quote": "전공과 교양 학점 이수 기준",
                "answerable_scope": "static",
            },
            {
                "fact_id": "missing_notice",
                "label": 1,
                "source_doc_id": "notice_doc_missing",
                "source_url": "https://plus.cnu.ac.kr/notice",
                "claim": "폐강 공지는 학사 공지에서 확인해야 한다.",
                "evidence_quote": "폐강 공지 확인",
                "answerable_scope": "static",
            },
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
                "source_id": "grad",
                "metadata": {},
            }
        ],
    )

    report = diagnose_retrieval_bottlenecks(
        facts_path=facts_path,
        knowledge_path=knowledge_path,
        output_path=output_path,
    )

    assert report["evaluation_scope"] == "task2_fact_retrieval_bottleneck"
    assert report["dataset_origin"] == "task2_gold"
    assert report["claim_level"] == "sanity"
    assert report["fact_count"] == 2
    assert report["source_coverage_gap_count"] == 1
    assert report["ranking_failure_count"] == 0
    assert report["hit_at_1"] == 0.5
    assert report["hit_at_3"] == 0.5
    assert report["missing_source_doc_ids"] == ["notice_doc_missing"]
    assert report["rows"][0]["bottleneck_type"] == "none"
    assert report["rows"][1]["bottleneck_type"] == "source_coverage_gap"
