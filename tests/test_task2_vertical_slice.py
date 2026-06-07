from __future__ import annotations

import json
from pathlib import Path

from nlp_term.chat.vertical_slice import run_task2_vertical_slice
from nlp_term.validators import validate_metric_claim


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_task2_vertical_slice_builds_source_clean_prompt_and_validates_answer(tmp_path: Path) -> None:
    gold_path = tmp_path / "task2_answer_eval_gold.json"
    facts_path = tmp_path / "task2_fact_gold.json"
    knowledge_path = tmp_path / "knowledge_seed.json"
    output_path = tmp_path / "task2_vertical_slice.json"
    _write_json(
        facts_path,
        [
            {
                "fact_id": "calendar_1",
                "label": 2,
                "source_doc_id": "calendar_doc_1",
                "source_url": "https://plus.cnu.ac.kr/calendar",
                "claim": "학사일정은 공식 학사일정 페이지 기준으로 확인한다.",
                "evidence_quote": "공식 학사일정 페이지 기준",
                "answerable_scope": "static",
            }
        ],
    )
    _write_json(
        gold_path,
        [
            {
                "user": "개강 일정은 어디서 확인해?",
                "expected_fact_ids": ["calendar_1"],
                "must_not_claim": ["확인되지 않은 최신 정보"],
            }
        ],
    )
    _write_json(
        knowledge_path,
        [
            {
                "doc_id": "calendar_doc_1",
                "label": 2,
                "domain": "academic_calendar",
                "title": "chunk_1",
                "body": "학사일정은 공식 학사일정 페이지 기준으로 확인한다.",
                "source_url": "https://plus.cnu.ac.kr/calendar",
                "source_id": "academic_calendar",
                "metadata": {"source_name": "충남대학교 학사일정"},
            }
        ],
    )

    def fake_generator(prompt: str) -> str:
        assert "calendar_doc_1" not in prompt
        assert "chunk_1" not in prompt
        assert "충남대학교 학사일정" in prompt
        return "개강 일정은 충남대학교 학사일정 페이지 기준으로 확인하면 됩니다."

    metrics = run_task2_vertical_slice(
        gold_path=gold_path,
        facts_path=facts_path,
        knowledge_path=knowledge_path,
        output_path=output_path,
        generator=fake_generator,
    )

    assert metrics["evaluation_scope"] == "task2_vertical_slice"
    assert metrics["evaluation_set_type"] == "task2_gold"
    assert metrics["dataset_origin"] == "task2_gold"
    assert metrics["claim_level"] == "qualitative_check"
    assert metrics["fallback_used"] is False
    assert metrics["row_count"] == 1
    assert metrics["success_count"] == 1
    assert metrics["validation_pass_rate"] == 1.0
    assert metrics["rows"][0]["retrieved_doc_ids"] == ["calendar_doc_1"]
    assert metrics["rows"][0]["validation"]["passed"] is True
    validate_metric_claim(
        output_path,
        input_path=gold_path,
        require_dataset_origin="task2_gold",
        require_claim_level="qualitative_check",
    )


def test_task2_vertical_slice_records_generation_failure_without_fallback(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.json"
    facts_path = tmp_path / "facts.json"
    knowledge_path = tmp_path / "knowledge.json"
    output_path = tmp_path / "out.json"
    _write_json(
        facts_path,
        [
            {
                "fact_id": "notice_1",
                "label": 1,
                "source_doc_id": "notice_doc_1",
                "source_url": "https://plus.cnu.ac.kr/notice",
                "claim": "공지사항은 공식 공지 게시판 기준으로 확인한다.",
                "evidence_quote": "공식 공지 게시판",
                "answerable_scope": "fresh",
            }
        ],
    )
    _write_json(gold_path, [{"user": "공지 어디서 봐?", "expected_fact_ids": ["notice_1"]}])
    _write_json(
        knowledge_path,
        [
            {
                "doc_id": "notice_doc_1",
                "label": 1,
                "domain": "notices",
                "title": "학사 공지",
                "body": "공지사항은 공식 공지 게시판 기준으로 확인한다.",
                "source_url": "https://plus.cnu.ac.kr/notice",
                "source_id": "notice",
                "metadata": {},
            }
        ],
    )

    def failing_generator(prompt: str) -> str:
        raise RuntimeError("llama-server down")

    metrics = run_task2_vertical_slice(
        gold_path=gold_path,
        facts_path=facts_path,
        knowledge_path=knowledge_path,
        output_path=output_path,
        generator=failing_generator,
    )

    assert metrics["fallback_used"] is False
    assert metrics["success_count"] == 0
    assert metrics["generation_failure_count"] == 1
    assert metrics["rows"][0]["status"] == "generation_failed"
    assert metrics["rows"][0]["answer"] == ""
    assert metrics["rows"][0]["generation_error"] == "llama-server down"


def test_task2_vertical_slice_uses_classifier_as_hint_not_hard_filter(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.json"
    facts_path = tmp_path / "facts.json"
    knowledge_path = tmp_path / "knowledge.json"
    output_path = tmp_path / "out.json"
    _write_json(
        facts_path,
        [
            {
                "fact_id": "notice_1",
                "label": 1,
                "source_doc_id": "notice_doc_1",
                "source_url": "https://plus.cnu.ac.kr/notice",
                "claim": "수강신청 공지는 학사 공지 게시판 기준으로 확인한다.",
                "evidence_quote": "학사 공지 게시판",
                "answerable_scope": "fresh",
            }
        ],
    )
    _write_json(gold_path, [{"user": "수강신청 공지 어디서 봐?", "expected_fact_ids": ["notice_1"]}])
    _write_json(
        knowledge_path,
        [
            {
                "doc_id": "notice_doc_1",
                "label": 1,
                "domain": "notices",
                "title": "수강신청 학사 공지",
                "body": "수강신청 공지는 학사 공지 게시판 기준으로 확인한다.",
                "source_url": "https://plus.cnu.ac.kr/notice",
                "source_id": "notice",
                "metadata": {"source_name": "충남대학교 학사 공지"},
            }
        ],
    )

    metrics = run_task2_vertical_slice(
        gold_path=gold_path,
        facts_path=facts_path,
        knowledge_path=knowledge_path,
        output_path=output_path,
        generator=lambda prompt: "수강신청 공지는 충남대학교 학사 공지에서 확인하면 됩니다.",
        route_label_override_for_test=2,
    )

    assert metrics["rows"][0]["route_label"] == 2
    assert metrics["rows"][0]["route_used_as"] == "soft_hint"
    assert metrics["rows"][0]["retrieved_doc_ids"] == ["notice_doc_1"]
    assert metrics["rows"][0]["retrieved_label_mismatch_count"] == 1


def test_task2_vertical_slice_validates_answer_against_evidence_pack(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.json"
    facts_path = tmp_path / "facts.json"
    knowledge_path = tmp_path / "knowledge.json"
    output_path = tmp_path / "out.json"
    _write_json(
        facts_path,
        [
            {
                "fact_id": "grad_1",
                "label": 0,
                "source_doc_id": "grad_doc_1",
                "source_url": "https://biochemistry.cnu.ac.kr/grad",
                "claim": "생화학과 졸업요건은 학과 공식 자료를 확인한다.",
                "evidence_quote": "학과 공식 자료",
                "answerable_scope": "static",
            }
        ],
    )
    _write_json(gold_path, [{"user": "생화학과 졸업요건 어디서 봐?", "expected_fact_ids": ["grad_1"]}])
    _write_json(
        knowledge_path,
        [
            {
                "doc_id": "grad_doc_1",
                "label": 0,
                "domain": "graduation",
                "title": "생화학과 졸업요건",
                "body": "생화학과 졸업요건은 학과 공식 자료를 확인한다.",
                "source_url": "https://biochemistry.cnu.ac.kr/grad",
                "source_id": "graduation",
                "metadata": {"source_name": "생화학과 졸업요건"},
            }
        ],
    )

    metrics = run_task2_vertical_slice(
        gold_path=gold_path,
        facts_path=facts_path,
        knowledge_path=knowledge_path,
        output_path=output_path,
        generator=lambda prompt: "학생지원센터에서 130점 기준을 확인하면 됩니다.",
    )

    validation = metrics["rows"][0]["validation"]
    assert validation["passed"] is True
    assert validation["failures"] == []
    assert "unsupported_institution_claim" in validation["warnings"]
    assert "unsupported_numeric_claim" in validation["warnings"]
