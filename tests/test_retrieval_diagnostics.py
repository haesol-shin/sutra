from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from nlp_term.retrieve.evaluate import evaluate_retrieval
from nlp_term.validators import validate_retrieval_metrics


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_retrieval_diagnostics_include_per_label_and_alignment(tmp_path: Path) -> None:
    knowledge = [
        {
            "doc_id": "graduation_curriculum_pdf_chunk_1",
            "label": 0,
            "domain": "graduation",
            "title": "졸업 교육과정",
            "body": "졸업 교육과정 전공 교양 학점 이수 기준 확인 문장입니다.",
            "source_url": "https://plus.cnu.ac.kr",
            "source_id": "graduation_curriculum_pdf",
            "metadata": {
                "source_id": "graduation_curriculum_pdf",
                "source_stage": "stage0",
                "source_parser_type": "pdf",
            },
        },
        {
            "doc_id": "notice_chunk_1",
            "label": 1,
            "domain": "notices",
            "title": "학사 공지",
            "body": "학사 공지 수강신청 휴학 복학 신청 안내 문장입니다.",
            "source_url": "https://plus.cnu.ac.kr",
            "source_id": "notice",
            "metadata": {
                "source_id": "notice",
                "source_stage": "stage0",
                "source_parser_type": "html",
            },
        },
    ]
    qa = [
        {
            "user": "졸업 교육과정 학점 기준 알려줘",
            "model": "근거는 '졸업 교육과정 전공 교양 학점 이수 기준 확인 문장입니다'입니다.",
            "source_doc_id": "graduation_curriculum_pdf_chunk_1",
            "source_url": "https://plus.cnu.ac.kr",
            "label": 0,
            "validated": True,
        }
    ]
    knowledge_path = tmp_path / "knowledge.json"
    qa_path = tmp_path / "qa.json"
    metrics_path = tmp_path / "retrieval_metrics.json"
    _write_json(knowledge_path, knowledge)
    _write_json(qa_path, qa)

    metrics = evaluate_retrieval(knowledge_path, qa_path)
    _write_json(metrics_path, metrics)

    assert metrics["per_label_top3_source_hit_rate"]["0"] == 1.0
    assert metrics["graduation_curriculum_pdf_hit_rate"] == 1.0
    assert metrics["retrieved_evidence_alignment_rate"] == 1.0
    validate_retrieval_metrics(
        metrics_path,
        knowledge_path=knowledge_path,
        qa_path=qa_path,
        require_metadata_aware=True,
        require_diagnostics=True,
        min_graduation_top3_source_hit_rate=1.0,
        min_retrieved_evidence_alignment_rate=1.0,
    )


def test_retrieval_validator_rejects_per_label_threshold(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    qa_path = tmp_path / "qa.json"
    metrics_path = tmp_path / "retrieval_metrics.json"
    _write_json(knowledge_path, [])
    _write_json(qa_path, [])
    _write_json(
        metrics_path,
        {
            "knowledge_checksum": "",
            "qa_checksum": "",
            "retrieval_strategy": "lexical_metadata_label_hint",
            "metadata_fields": ["source_id", "source_stage", "source_parser_type"],
            "top1_label_accuracy": 1.0,
            "top3_source_hit_rate": 1.0,
            "per_label_failure_counts": {str(label): 0 for label in range(5)},
            "row_count": 0,
            "per_label_top1_label_accuracy": {str(label): 1.0 for label in range(5)},
            "per_label_top3_source_hit_rate": {"0": 0.0, "1": 1.0, "2": 1.0, "3": 1.0, "4": 1.0},
        },
    )

    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    payload["knowledge_checksum"] = sha256(knowledge_path.read_bytes()).hexdigest()
    payload["qa_checksum"] = sha256(qa_path.read_bytes()).hexdigest()
    metrics_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="per_label_top3_source_hit_rate label 0 below threshold"):
        validate_retrieval_metrics(
            metrics_path,
            knowledge_path=knowledge_path,
            qa_path=qa_path,
            min_per_label_top3_source_hit_rate=0.5,
        )
