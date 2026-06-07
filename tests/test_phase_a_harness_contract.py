from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from nlp_term.chat.evidence_sufficiency import evaluate_evidence_sufficiency
from nlp_term.chat.orchestrator import answer_with_harness
from nlp_term.chat.source_status import build_source_status
from nlp_term.chat.state_contract import (
    AnswerKind,
    EvidenceSufficiencyStatus,
    FetchDecision,
    FreshnessStatus,
    OutputStatus,
)
from nlp_term.collect.source_inventory import STAGE0_SOURCES
from nlp_term.schemas import KnowledgeDoc


def _doc(
    *,
    doc_id: str = "doc_1",
    label: int = 4,
    domain: str = "shuttle",
    body: str = "셔틀버스 시간표는 충남대학교 공식 셔틀 안내 페이지에서 확인한다.",
    source_url: str = "https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html",
    source_id: str = "shuttle_bus",
    metadata: dict[str, object] | None = None,
) -> KnowledgeDoc:
    return KnowledgeDoc(
        doc_id=doc_id,
        label=label,
        domain=domain,  # type: ignore[arg-type]
        title="공식 안내",
        body=body,
        source_url=source_url,
        source_id=source_id,
        metadata=metadata or {},
    )


def test_source_status_normalizes_registry_metadata_and_allowlist() -> None:
    doc = _doc(
        domain="graduation",
        label=0,
        source_id="graduation_biochemistry_requirements",
        source_url="https://biochemistry.cnu.ac.kr/biochemistry/info/requirements.do",
        metadata={
            "source_department": "생화학과",
            "source_curriculum_year": "2025",
            "raw_fetched_at": "2026-06-01T00:00:00+00:00",
        },
    )

    status = build_source_status(doc, specs=STAGE0_SOURCES)

    assert status.registry_present is True
    assert status.active is True
    assert status.official_chain_ok is True
    assert status.parser_type == "html"
    assert status.allowlist_status == "allowed"
    assert status.metadata_department == "생화학과"
    assert status.metadata_curriculum_year == "2025"
    assert status.raw_fetched_at == "2026-06-01T00:00:00+00:00"


def test_source_navigation_is_sufficient_with_safe_official_url() -> None:
    doc = _doc()
    status = build_source_status(doc, specs=STAGE0_SOURCES)

    decision = evaluate_evidence_sufficiency(
        answer_kind=AnswerKind.SOURCE_NAVIGATION,
        docs=[doc],
        retrieved_scores=[0.05],
        source_statuses=[status],
        candidate_specs=STAGE0_SOURCES,
        route_domain="shuttle",
        min_top_score=0.20,
        question_time=datetime(2026, 6, 7, tzinfo=timezone.utc),
    )

    assert decision.status == EvidenceSufficiencyStatus.SUFFICIENT
    assert decision.fetch_decision == FetchDecision.SKIPPED_RAG_SUFFICIENT
    assert decision.freshness_status == FreshnessStatus.FRESH


def test_current_dining_fact_fails_closed_when_source_is_unverified_and_unstructured() -> None:
    doc = _doc(
        label=3,
        domain="dining",
        source_id="cnu_mobile_food",
        source_url="https://mobileadmin.cnu.ac.kr/food/index.jsp",
        body="식단은 모바일 식단 페이지에서 확인한다.",
        metadata={"raw_fetched_at": "2026-06-07T00:00:00+00:00"},
    )
    status = build_source_status(doc, specs=STAGE0_SOURCES)

    decision = evaluate_evidence_sufficiency(
        answer_kind=AnswerKind.CURRENT_FACT,
        docs=[doc],
        retrieved_scores=[0.9],
        source_statuses=[status],
        candidate_specs=STAGE0_SOURCES,
        route_domain="dining",
        min_top_score=0.20,
        question_time=datetime(2026, 6, 7, tzinfo=timezone.utc),
    )

    assert decision.status == EvidenceSufficiencyStatus.INSUFFICIENT
    assert decision.fetch_decision == FetchDecision.FETCH_BLOCKED_UNOFFICIAL
    assert decision.freshness_status == FreshnessStatus.UNVERIFIED_SOURCE


def test_harness_generates_from_sufficient_evidence_with_injected_writer(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        "["
        "{"
        '"doc_id":"shuttle_doc",'
        '"label":4,'
        '"domain":"shuttle",'
        '"title":"셔틀 안내",'
        '"body":"셔틀버스 시간표는 충남대학교 공식 셔틀 안내 페이지에서 확인한다.",'
        '"source_url":"https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html",'
        '"source_id":"shuttle_bus",'
        '"metadata":{"source_name":"충남대학교 셔틀 안내"}'
        "}"
        "]",
        encoding="utf-8",
    )

    result = answer_with_harness(
        "셔틀 시간표 어디서 봐?",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "셔틀 시간표는 충남대학교 공식 셔틀 안내 페이지에서 확인하면 됩니다.",
    )

    assert result.output_status == OutputStatus.ANSWERED
    assert "공식 셔틀 안내" in result.output.model
    assert result.trace.answer_kind == AnswerKind.SOURCE_NAVIGATION
    assert result.trace.evidence_sufficiency_status == EvidenceSufficiencyStatus.SUFFICIENT
    assert result.trace.generation_backend == "injected"


def test_harness_current_dining_question_fails_closed_without_menu_claim(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        "["
        "{"
        '"doc_id":"dining_doc",'
        '"label":3,'
        '"domain":"dining",'
        '"title":"식단",'
        '"body":"식단은 모바일 식단 페이지에서 확인한다.",'
        '"source_url":"https://mobileadmin.cnu.ac.kr/food/index.jsp",'
        '"source_id":"cnu_mobile_food",'
        '"metadata":{"raw_fetched_at":"2026-06-07T00:00:00+00:00"}'
        "}"
        "]",
        encoding="utf-8",
    )

    result = answer_with_harness(
        "오늘 점심 메뉴 뭐야?",
        mode="realtime",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "오늘 점심은 김치찌개입니다.",
        question_time=datetime(2026, 6, 7, tzinfo=timezone.utc),
    )

    assert result.output_status == OutputStatus.FAIL_CLOSED
    assert "공식 근거가 충분하지 않아 확답하기 어렵습니다" in result.output.model
    assert "김치찌개" not in result.output.model
    assert result.trace.answer_kind == AnswerKind.CURRENT_FACT
    assert result.trace.fetch_decision == FetchDecision.FETCH_BLOCKED_UNOFFICIAL
    assert result.trace.generation_status == "skipped_blocked"


def test_harness_does_not_accept_safe_source_from_wrong_domain(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        "["
        "{"
        '"doc_id":"shuttle_doc",'
        '"label":4,'
        '"domain":"shuttle",'
        '"title":"셔틀 안내",'
        '"body":"셔틀버스 시간표는 충남대학교 공식 셔틀 안내 페이지에서 확인한다.",'
        '"source_url":"https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html",'
        '"source_id":"shuttle_bus",'
        '"metadata":{"source_name":"충남대학교 셔틀 안내"}'
        "}"
        "]",
        encoding="utf-8",
    )

    result = answer_with_harness(
        "식단 페이지 어디서 봐?",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "식단 페이지는 셔틀 안내 페이지에서 확인하면 됩니다.",
    )

    assert result.output_status == OutputStatus.FAIL_CLOSED
    assert result.trace.route_domain == "dining"
    assert result.trace.evidence_lookup_status == "no_docs"


def test_harness_fails_closed_for_cross_domain_source_navigation(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        "["
        "{"
        '"doc_id":"grad_doc",'
        '"label":0,'
        '"domain":"graduation",'
        '"title":"졸업요건",'
        '"body":"졸업요건은 생화학과 공식 졸업요건 페이지에서 확인한다.",'
        '"source_url":"https://biochemistry.cnu.ac.kr/biochemistry/info/requirements.do",'
        '"source_id":"graduation_biochemistry_requirements",'
        '"metadata":{"source_department":"생화학과"}'
        "}"
        "]",
        encoding="utf-8",
    )

    result = answer_with_harness(
        "셔틀 시간표는 졸업요건 페이지에서 확인해도 돼?",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "졸업요건 페이지에서 셔틀 시간표를 확인하면 됩니다.",
    )

    assert result.output_status == OutputStatus.FAIL_CLOSED
    assert result.trace.answer_kind == AnswerKind.UNSUPPORTED
    assert "셔틀 시간표" not in result.output.model


def test_harness_trace_records_next_week_temporal_intent(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        "["
        "{"
        '"doc_id":"dining_doc",'
        '"label":3,'
        '"domain":"dining",'
        '"title":"식단",'
        '"body":"다음주 화요일인 2026년 6월 16일 2학생회관 점심 메뉴는 공식 식단 페이지에서 확인한다.",'
        '"source_url":"https://mobileadmin.cnu.ac.kr/food/index.jsp",'
        '"source_id":"cnu_mobile_food",'
        '"metadata":{"menu_date":"2026-06-16","location":"2학생회관","raw_fetched_at":"2026-06-08T00:00:00+09:00"}'
        "}"
        "]",
        encoding="utf-8",
    )

    result = answer_with_harness(
        "다음주 화요일 2학생회관 메뉴가 어떻게 되나요?",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "다음주 화요일인 2026년 6월 16일 2학생회관 메뉴는 공식 식단 페이지에서 확인하면 됩니다.",
        question_time=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )

    assert result.trace.temporal_type == "future_schedule"
    assert result.trace.temporal_confidence == "high"
    assert result.trace.target_start == "2026-06-16"
    assert result.trace.target_end == "2026-06-16"
    assert "date_filtered_evidence_needed" in result.trace.retrieval_requirements
