from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from nlp_term.chat.state_contract import (
    RetrievalRequirement,
    TemporalConfidence,
    TemporalIntent,
    TemporalType,
)
from nlp_term.chat.temporal_intent import resolve_temporal_intent


REFERENCE_TIME = datetime(2026, 6, 8, tzinfo=ZoneInfo("Asia/Seoul"))


def test_temporal_intent_contract_stores_iso_week_resolution() -> None:
    intent = TemporalIntent(
        reference_time=datetime(2026, 6, 8, tzinfo=ZoneInfo("Asia/Seoul")),
        timezone="Asia/Seoul",
        week_policy="iso_monday_to_sunday",
        original_expression="다음주 화요일",
        temporal_type=TemporalType.FUTURE_SCHEDULE,
        explicitness="relative",
        target_start=date(2026, 6, 16),
        target_end=date(2026, 6, 16),
        granularity="day",
        resolution_policy="next_iso_week_weekday",
        freshness_required=True,
        version_match_required=False,
        retrieval_requirements=[
            RetrievalRequirement.DATE_FILTERED_EVIDENCE_NEEDED,
            RetrievalRequirement.STRUCTURED_SOURCE_PREFERRED,
        ],
        confidence=TemporalConfidence.HIGH,
        confidence_reasons=["relative_weekday_expression_resolved", "single_day_target"],
    )

    assert intent.week_policy == "iso_monday_to_sunday"
    assert intent.target_start.isoformat() == "2026-06-16"
    assert intent.retrieval_requirements == [
        RetrievalRequirement.DATE_FILTERED_EVIDENCE_NEEDED,
        RetrievalRequirement.STRUCTURED_SOURCE_PREFERRED,
    ]


def test_next_week_tuesday_uses_iso_week_policy() -> None:
    intent = resolve_temporal_intent(
        "다음주 화요일 2학생회관 메뉴가 어떻게 되나요?",
        route_domain="dining",
        reference_time=REFERENCE_TIME,
    )

    assert intent.temporal_type == TemporalType.FUTURE_SCHEDULE
    assert intent.target_start == date(2026, 6, 16)
    assert intent.target_end == date(2026, 6, 16)
    assert intent.confidence == TemporalConfidence.HIGH
    assert RetrievalRequirement.DATE_FILTERED_EVIDENCE_NEEDED in intent.retrieval_requirements
    assert RetrievalRequirement.STRUCTURED_SOURCE_PREFERRED in intent.retrieval_requirements


def test_changed_since_defaults_to_recent_30_day_window() -> None:
    intent = resolve_temporal_intent(
        "최근에 바뀐 학사일정 있어요?",
        route_domain="academic_calendar",
        reference_time=REFERENCE_TIME,
    )

    assert intent.temporal_type == TemporalType.CHANGED_SINCE
    assert intent.target_start == date(2026, 5, 9)
    assert intent.target_end == date(2026, 6, 8)
    assert intent.confidence == TemporalConfidence.MEDIUM
    assert RetrievalRequirement.CHANGE_WINDOW_NEEDED in intent.retrieval_requirements


def test_graduation_credit_question_has_no_temporal_requirement() -> None:
    intent = resolve_temporal_intent(
        "졸업까지 몇 학점 들어야 하나요?",
        route_domain="graduation",
        reference_time=REFERENCE_TIME,
    )

    assert intent.temporal_type == TemporalType.NONE
    assert intent.freshness_required is False
    assert intent.target_start is None
    assert intent.retrieval_requirements == [RetrievalRequirement.RAG_OK]
