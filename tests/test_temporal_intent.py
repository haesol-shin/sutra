from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from nlp_term.chat.state_contract import (
    RetrievalRequirement,
    TemporalConfidence,
    TemporalIntent,
    TemporalType,
)


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
