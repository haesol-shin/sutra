from __future__ import annotations

from datetime import date, datetime, timedelta
import re
from zoneinfo import ZoneInfo

from nlp_term.chat.state_contract import (
    RetrievalRequirement,
    TemporalConfidence,
    TemporalIntent,
    TemporalType,
)
from nlp_term.schemas import Domain


KST_TIMEZONE = "Asia/Seoul"
WEEKDAY_INDEX = {
    "월요일": 0,
    "월": 0,
    "화요일": 1,
    "화": 1,
    "수요일": 2,
    "수": 2,
    "목요일": 3,
    "목": 3,
    "금요일": 4,
    "금": 4,
    "토요일": 5,
    "토": 5,
    "일요일": 6,
    "일": 6,
}


def resolve_temporal_intent(
    question: str,
    *,
    route_domain: Domain,
    reference_time: datetime,
) -> TemporalIntent:
    compact = question.replace(" ", "")
    normalized_reference = _to_kst(reference_time)
    reference_date = normalized_reference.date()

    if _is_changed_since(compact):
        start = reference_date - timedelta(days=30)
        return TemporalIntent(
            reference_time=normalized_reference,
            original_expression=_original_expression(question, default="최근"),
            temporal_type=TemporalType.CHANGED_SINCE,
            explicitness="relative",
            target_start=start,
            target_end=reference_date,
            granularity="day",
            resolution_policy="recent_30_days_default",
            freshness_required=True,
            retrieval_requirements=[
                RetrievalRequirement.DATE_FILTERED_EVIDENCE_NEEDED,
                RetrievalRequirement.CHANGE_WINDOW_NEEDED,
            ],
            confidence=TemporalConfidence.MEDIUM,
            confidence_reasons=["ambiguous_recent_resolved_by_30_day_policy", f"domain_{route_domain}"],
        )

    weekday = _extract_weekday(compact)
    if "다음주" in compact and weekday is not None:
        target = _iso_week_start(reference_date) + timedelta(days=7 + weekday)
        temporal_type = _schedule_type(route_domain, compact, granularity="day")
        return TemporalIntent(
            reference_time=normalized_reference,
            original_expression=_original_expression(question, default="다음주"),
            temporal_type=temporal_type,
            explicitness="relative",
            target_start=target,
            target_end=target,
            granularity="day",
            resolution_policy="next_iso_week_weekday",
            freshness_required=route_domain in {"dining", "shuttle", "notices", "academic_calendar"},
            retrieval_requirements=_requirements_for(route_domain, temporal_type),
            confidence=TemporalConfidence.HIGH,
            confidence_reasons=["relative_weekday_expression_resolved", f"domain_{route_domain}", "single_day_target"],
        )

    if "다음주" in compact:
        start = _iso_week_start(reference_date) + timedelta(days=7)
        end = start + timedelta(days=6)
        temporal_type = _schedule_type(route_domain, compact, granularity="week")
        return TemporalIntent(
            reference_time=normalized_reference,
            original_expression=_original_expression(question, default="다음주"),
            temporal_type=temporal_type,
            explicitness="relative",
            target_start=start,
            target_end=end,
            granularity="week",
            resolution_policy="next_iso_week",
            freshness_required=route_domain in {"dining", "shuttle", "notices", "academic_calendar"},
            retrieval_requirements=_requirements_for(route_domain, temporal_type),
            confidence=TemporalConfidence.HIGH,
            confidence_reasons=["relative_week_expression_resolved", f"domain_{route_domain}", "week_range_target"],
        )

    if any(token in compact for token in ("오늘", "현재", "지금")):
        return TemporalIntent(
            reference_time=normalized_reference,
            original_expression=_original_expression(question, default="오늘"),
            temporal_type=TemporalType.CURRENT_SNAPSHOT,
            explicitness="relative",
            target_start=reference_date,
            target_end=reference_date,
            granularity="day",
            resolution_policy="current_date",
            freshness_required=True,
            retrieval_requirements=_requirements_for(route_domain, TemporalType.CURRENT_SNAPSHOT),
            confidence=TemporalConfidence.HIGH,
            confidence_reasons=["current_expression_resolved", f"domain_{route_domain}"],
        )

    if route_domain == "academic_calendar" and any(token in compact for token in ("이번학기", "종강일", "수강신청")):
        return TemporalIntent(
            reference_time=normalized_reference,
            original_expression=_original_expression(question, default="이번 학기"),
            temporal_type=TemporalType.DATE_LOOKUP,
            explicitness="relative",
            granularity="semester",
            resolution_policy="academic_semester_lookup_required",
            freshness_required=False,
            retrieval_requirements=[RetrievalRequirement.DATE_FILTERED_EVIDENCE_NEEDED],
            confidence=TemporalConfidence.MEDIUM,
            confidence_reasons=["academic_calendar_event_lookup", "semester_requires_calendar_evidence"],
        )

    version_match = route_domain == "graduation" and bool(re.search(r"\d{2,4}학번|\d{4}", compact))
    requirements = [RetrievalRequirement.VERSION_MATCH_NEEDED] if version_match else [RetrievalRequirement.RAG_OK]
    return TemporalIntent(
        reference_time=normalized_reference,
        temporal_type=TemporalType.NONE,
        version_match_required=version_match,
        retrieval_requirements=requirements,
        confidence=TemporalConfidence.HIGH,
        confidence_reasons=["no_temporal_expression_detected"],
    )


def _to_kst(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=ZoneInfo(KST_TIMEZONE))
    return value.astimezone(ZoneInfo(KST_TIMEZONE))


def _iso_week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _extract_weekday(compact: str) -> int | None:
    for text, index in sorted(WEEKDAY_INDEX.items(), key=lambda item: len(item[0]), reverse=True):
        if text in compact:
            return index
    return None


def _is_changed_since(compact: str) -> bool:
    change_cues = ("바뀐", "변동", "변경", "업데이트", "새로")
    range_cues = ("최근", "이후", "부터")
    return any(cue in compact for cue in change_cues) and any(cue in compact for cue in range_cues)


def _schedule_type(route_domain: Domain, compact: str, *, granularity: str) -> TemporalType:
    if route_domain == "shuttle" and any(token in compact for token in ("정상운행", "운행하", "운영하")):
        return TemporalType.ONGOING_STATUS
    if granularity == "day":
        return TemporalType.FUTURE_SCHEDULE
    return TemporalType.PERIOD_SUMMARY


def _requirements_for(route_domain: Domain, temporal_type: TemporalType) -> list[RetrievalRequirement]:
    requirements = [RetrievalRequirement.DATE_FILTERED_EVIDENCE_NEEDED]
    if route_domain in {"dining", "shuttle"} or temporal_type in {
        TemporalType.CURRENT_SNAPSHOT,
        TemporalType.FUTURE_SCHEDULE,
    }:
        requirements.append(RetrievalRequirement.STRUCTURED_SOURCE_PREFERRED)
    if temporal_type == TemporalType.LATEST_ITEM:
        requirements.append(RetrievalRequirement.LATEST_LIST_NEEDED)
    return requirements


def _original_expression(question: str, *, default: str) -> str:
    for token in ("다음주 화요일", "다음주", "이번 학기", "오늘", "최근"):
        if token in question:
            return token
    return default
