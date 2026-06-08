from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import nlp_term.chat.orchestrator as orchestrator_module
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
from nlp_term.schemas import KnowledgeDoc, RetrievedDoc


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


def test_harness_blocks_dining_evidence_for_wrong_target_date(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        "["
        "{"
        '"doc_id":"dining_doc",'
        '"label":3,'
        '"domain":"dining",'
        '"title":"식단",'
        '"body":"2026년 6월 9일 2학생회관 점심 메뉴는 백반입니다.",'
        '"source_url":"https://mobileadmin.cnu.ac.kr/food/index.jsp",'
        '"source_id":"cnu_mobile_food",'
        '"metadata":{"menu_date":"2026-06-09","location":"2학생회관","raw_fetched_at":"2026-06-08T00:00:00+09:00"}'
        "}"
        "]",
        encoding="utf-8",
    )

    result = answer_with_harness(
        "다음주 화요일 2학생회관 메뉴가 어떻게 되나요?",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "2026년 6월 9일 2학생회관 점심은 백반입니다.",
        question_time=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )

    assert result.output_status == OutputStatus.FAIL_CLOSED
    assert result.trace.target_start == "2026-06-16"
    assert result.trace.evidence_sufficiency_status == EvidenceSufficiencyStatus.INSUFFICIENT
    assert "백반" not in result.output.model


def test_harness_accepts_shuttle_interval_overlap_for_next_week_status(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        "["
        "{"
        '"doc_id":"shuttle_doc",'
        '"label":4,'
        '"domain":"shuttle",'
        '"title":"2026학년도 셔틀버스 교내 순환",'
        '"body":"2026학년도 셔틀버스 교내 순환은 2026-03-03부터 2026-06-21까지 학기 중 평일 주간에 정상 운행합니다.",'
        '"date":"2026-03-03",'
        '"source_url":"https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html",'
        '"source_id":"shuttle_bus",'
        '"metadata":{'
        '"generation_method":"structured_row",'
        '"structured_fields":["route_key","valid_start","valid_end"],'
        '"valid_start":"2026-03-03",'
        '"valid_end":"2026-06-21",'
        '"date_span":"2026-03-03/2026-06-21",'
        '"verification_official_chain_ok":true'
        "}"
        "}"
        "]",
        encoding="utf-8",
    )

    result = answer_with_harness(
        "다음주에 셔틀버스는 정상 운행하나요?",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "다음주 평일에는 학기 중 평일 주간 기준으로 셔틀버스가 운행합니다.",
        question_time=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )

    assert result.output_status == OutputStatus.ANSWERED
    assert result.trace.temporal_type == "ongoing_status"
    assert result.trace.target_start == "2026-06-15"
    assert result.trace.target_end == "2026-06-21"
    assert result.trace.evidence_sufficiency_status == EvidenceSufficiencyStatus.SUFFICIENT


def test_harness_prefers_newest_notice_row_for_latest_item_question(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        json.dumps(
            [
                {
                    "doc_id": "old_notice_doc",
                    "label": 1,
                    "domain": "notices",
                    "title": "공지사항 안내",
                    "body": "공지사항 안내입니다. 게시일은 2026-05-01입니다.",
                    "date": "2026-05-01",
                    "source_url": "https://plus.cnu.ac.kr/old",
                    "source_id": "academic_notice_board",
                    "metadata": {
                        "generation_method": "structured_row",
                        "row_type": "notice_board_item",
                        "posted_date": "2026-05-01",
                        "structured_fields": ["posted_date", "title", "detail_url"],
                        "verification_official_chain_ok": True,
                    },
                },
                {
                    "doc_id": "new_notice_doc",
                    "label": 1,
                    "domain": "notices",
                    "title": "공지사항 안내",
                    "body": "가장 최근에 올라온 공지사항입니다. 게시일은 2026-06-05입니다.",
                    "date": "2026-06-05",
                    "source_url": "https://plus.cnu.ac.kr/new",
                    "source_id": "academic_notice_board",
                    "metadata": {
                        "generation_method": "structured_row",
                        "row_type": "notice_board_item",
                        "posted_date": "2026-06-05",
                        "structured_fields": ["posted_date", "title", "detail_url"],
                        "verification_official_chain_ok": True,
                    },
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    captured: dict[str, str] = {}

    def writer(prompt: str) -> str:
        captured["prompt"] = prompt
        return "가장 최근에 올라온 공지사항은 2026년 6월 5일에 게시되었습니다."

    result = answer_with_harness(
        "가장 최근에 올라온 공지사항은 언제 게시되었나요?",
        knowledge_path=knowledge_path,
        generator=writer,
        question_time=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )

    assert result.output_status == OutputStatus.ANSWERED
    assert result.trace.temporal_type == "latest_item"
    assert result.trace.retrieved_doc_ids[0] == "new_notice_doc"
    assert captured["prompt"].find("2026-06-05") < captured["prompt"].find("2026-05-01")


def test_harness_prompt_contains_user_safe_temporal_context(tmp_path: Path) -> None:
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
    captured: dict[str, str] = {}

    def writer(prompt: str) -> str:
        captured["prompt"] = prompt
        return "다음주 화요일인 2026년 6월 16일 기준으로 2학생회관 식단은 공식 식단 페이지에서 확인하면 됩니다."

    result = answer_with_harness(
        "다음주 화요일 2학생회관 메뉴가 어떻게 되나요?",
        knowledge_path=knowledge_path,
        generator=writer,
        question_time=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )

    assert result.output_status == OutputStatus.ANSWERED
    assert "2026-06-16" in captured["prompt"]
    assert "TemporalIntent" not in captured["prompt"]
    assert "confidence" not in captured["prompt"]


def test_temporal_questions_can_send_more_than_three_evidence_items(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    docs = [
        {
            "doc_id": f"calendar_doc_{index}",
            "label": 2,
            "domain": "academic_calendar",
            "title": f"학사일정 {index}",
            "body": f"이번 학기 학사일정 참고 자료 {index}. 2026년 6월 19일 종강일 관련 자료입니다.",
            "source_url": "https://plus.cnu.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&site_dvs_cd=kr",
            "source_id": "academic_calendar",
            "metadata": {"date_span": "2026-06-19", "source_name": f"학사일정 {index}"},
        }
        for index in range(5)
    ]
    knowledge_path.write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
    captured: dict[str, str] = {}

    def writer(prompt: str) -> str:
        captured["prompt"] = prompt
        return "이번 학기 종강일은 2026년 6월 19일입니다."

    answer_with_harness(
        "이번 학기 종강일이 언제인가요?",
        knowledge_path=knowledge_path,
        generator=writer,
        question_time=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )

    assert captured["prompt"].count("핵심 사실:") >= 5


def test_harness_trace_records_prefilter_and_postfilter_retrieval_candidates(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        json.dumps(
            [
                {
                    "doc_id": "notice_doc",
                    "label": 1,
                    "domain": "notices",
                    "title": "공지",
                    "body": "토익 장학금 성적 기준은 공지사항에서 확인한다.",
                    "source_url": "https://plus.cnu.ac.kr/notice",
                    "source_id": "notices_main",
                    "metadata": {
                        "source_name": "공지사항",
                        "chunking_strategy": "recursive_prose",
                        "boundary_type": "prose_sentence",
                        "chunk_confidence": "medium",
                    },
                },
                {
                    "doc_id": "grad_doc",
                    "label": 0,
                    "domain": "graduation",
                    "title": "졸업요건",
                    "body": "토익 졸업인증 기준은 학과별로 다르다.",
                    "source_url": "https://biochemistry.cnu.ac.kr/biochemistry/info/requirements.do",
                    "source_id": "graduation_biochemistry_requirements",
                    "metadata": {
                        "source_department": "생화학과",
                        "chunking_strategy": "fallback_window",
                        "boundary_type": "fallback_window",
                        "chunk_confidence": "low",
                    },
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = answer_with_harness(
        "토익 장학금을 받으려면 성적이 몇 점 이상이어야 하나요?",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "토익 장학금 성적 기준은 공지사항에서 확인해야 합니다.",
    )

    prefilter_ids = [candidate.doc_id for candidate in result.trace.prefilter_retrieved_candidates]
    postfilter_ids = [candidate.doc_id for candidate in result.trace.postfilter_retrieved_candidates]

    assert "notice_doc" in prefilter_ids
    assert "grad_doc" in prefilter_ids
    assert postfilter_ids == result.trace.retrieved_doc_ids
    assert "grad_doc" not in postfilter_ids
    assert result.trace.prefilter_retrieved_candidates[0].score >= 0
    assert {candidate.chunk_confidence for candidate in result.trace.prefilter_retrieved_candidates} >= {"medium", "low"}


def test_diagnostic_retrieval_pool_does_not_expand_evidence_selection(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    high_scoring_wrong_route_docs = [
        {
            "doc_id": f"calendar_doc_{index}",
            "label": 2,
            "domain": "academic_calendar",
            "title": "토익 장학금 성적 기준",
            "body": "토익 장학금 성적 기준 관련 일정 안내입니다.",
            "source_url": "https://plus.cnu.ac.kr/_prog/academic_calendar/",
            "source_id": "academic_calendar",
            "metadata": {"chunk_confidence": "medium"},
        }
        for index in range(6)
    ]
    knowledge_path.write_text(
        json.dumps(
            [
                *high_scoring_wrong_route_docs,
                {
                    "doc_id": "late_notice_doc",
                    "label": 1,
                    "domain": "notices",
                    "title": "공지",
                    "body": "장학 공지사항은 공식 공지 게시판에서 확인한다.",
                    "source_url": "https://plus.cnu.ac.kr/notice",
                    "source_id": "notices_main",
                    "metadata": {"chunk_confidence": "low"},
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = answer_with_harness(
        "토익 장학금을 받으려면 성적 기준이 어떻게 되나요?",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "토익 장학금 성적 기준은 공지사항에서 확인해야 합니다.",
    )

    prefilter_ids = [candidate.doc_id for candidate in result.trace.prefilter_retrieved_candidates]
    postfilter_ids = [candidate.doc_id for candidate in result.trace.postfilter_retrieved_candidates]

    assert "late_notice_doc" in prefilter_ids
    assert "late_notice_doc" not in postfilter_ids
    assert result.trace.retrieved_doc_ids == []
    assert result.output_status == OutputStatus.FAIL_CLOSED


def test_harness_uses_original_top_k_for_decision_and_larger_pool_for_diagnostics(tmp_path: Path, monkeypatch) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        json.dumps(
            [
                {
                    "doc_id": "notice_doc",
                    "label": 1,
                    "domain": "notices",
                    "title": "공지",
                    "body": "장학금 공지는 공식 공지사항에서 확인한다.",
                    "source_url": "https://plus.cnu.ac.kr/notice",
                    "source_id": "notices_main",
                    "metadata": {},
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    top_k_calls: list[int] = []

    def fake_rank_docs(question, docs, *, top_k: int):
        top_k_calls.append(top_k)
        return [
            RetrievedDoc(
                doc_id="notice_doc",
                score=0.9,
                title="공지",
                source_url="https://plus.cnu.ac.kr/notice",
                label=1,
            )
        ]

    monkeypatch.setattr(orchestrator_module, "rank_docs", fake_rank_docs)

    answer_with_harness(
        "장학금 공지 어디서 봐요?",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "장학금 공지는 공식 공지사항에서 확인하면 됩니다.",
    )

    assert top_k_calls == [6, 12]


def test_diagnostic_only_candidate_does_not_enter_prompt(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    wrong_route_docs = [
        {
            "doc_id": f"calendar_doc_{index}",
            "label": 2,
            "domain": "academic_calendar",
            "title": "토익 장학금 성적 기준",
            "body": "토익 장학금 성적 기준 관련 일정 안내입니다.",
            "source_url": "https://plus.cnu.ac.kr/_prog/academic_calendar/",
            "source_id": "academic_calendar",
            "metadata": {"chunk_confidence": "medium"},
        }
        for index in range(5)
    ]
    knowledge_path.write_text(
        json.dumps(
            [
                {
                    "doc_id": "selected_notice_doc",
                    "label": 1,
                    "domain": "notices",
                    "title": "토익 장학금 성적 기준",
                    "body": "토익 장학금 성적 기준은 공식 공지사항에서 확인한다.",
                    "source_url": "https://plus.cnu.ac.kr/notice",
                    "source_id": "notices_main",
                    "metadata": {"chunk_confidence": "medium"},
                },
                *wrong_route_docs,
                {
                    "doc_id": "late_notice_doc",
                    "label": 1,
                    "domain": "notices",
                    "title": "공지",
                    "body": "진단 전용 비밀 문장. 이 문장은 prompt에 들어가면 안 된다.",
                    "source_url": "https://plus.cnu.ac.kr/notice/late",
                    "source_id": "notices_main",
                    "metadata": {"chunk_confidence": "low"},
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    captured: dict[str, str] = {}

    def writer(prompt: str) -> str:
        captured["prompt"] = prompt
        return "토익 장학금 성적 기준은 공식 공지사항에서 확인하면 됩니다."

    result = answer_with_harness(
        "토익 장학금을 받으려면 성적 기준이 어떻게 되나요?",
        knowledge_path=knowledge_path,
        generator=writer,
    )

    prefilter_ids = [candidate.doc_id for candidate in result.trace.prefilter_retrieved_candidates]
    postfilter_ids = [candidate.doc_id for candidate in result.trace.postfilter_retrieved_candidates]

    assert result.output_status == OutputStatus.ANSWERED
    assert "late_notice_doc" in prefilter_ids
    assert "late_notice_doc" not in postfilter_ids
    assert "진단 전용 비밀 문장" not in captured["prompt"]
