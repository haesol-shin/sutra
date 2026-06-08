from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
import re

from nlp_term.chat.controlled_fetch import fetchable_specs
from nlp_term.chat.state_contract import (
    AllowlistStatus,
    AnswerKind,
    EvidenceSufficiencyDecision,
    EvidenceSufficiencyStatus,
    FetchDecision,
    FreshnessStatus,
    RetrievalRequirement,
    SourceStatus,
    TemporalIntent,
)
from nlp_term.collect.source_inventory import SourceSpec
from nlp_term.schemas import Domain, KnowledgeDoc


def evaluate_evidence_sufficiency(
    *,
    answer_kind: AnswerKind,
    docs: list[KnowledgeDoc],
    retrieved_scores: list[float],
    source_statuses: list[SourceStatus],
    candidate_specs: Iterable[SourceSpec],
    route_domain: Domain,
    min_top_score: float = 0.20,
    question_time: datetime | None = None,
    temporal_intent: TemporalIntent | None = None,
) -> EvidenceSufficiencyDecision:
    candidates = [spec for spec in candidate_specs if spec.active and spec.domain == route_domain]
    supported_candidates = fetchable_specs(candidates, route_domain=route_domain)

    if answer_kind == AnswerKind.UNSUPPORTED:
        return EvidenceSufficiencyDecision(
            status=EvidenceSufficiencyStatus.INSUFFICIENT,
            fetch_decision=FetchDecision.FETCH_BLOCKED_NO_REGISTRY,
            freshness_status=FreshnessStatus.NOT_REQUIRED,
            reasons=["unsupported_or_cross_domain_question"],
        )

    if not docs:
        if supported_candidates:
            return EvidenceSufficiencyDecision(
                status=EvidenceSufficiencyStatus.NEEDS_FETCH,
                fetch_decision=FetchDecision.FETCH_REQUIRED_BUT_NOT_IMPLEMENTED,
                freshness_status=FreshnessStatus.UNKNOWN,
                reasons=["no_retrieved_docs", "controlled_fetch_candidate_exists"],
            )
        return EvidenceSufficiencyDecision(
            status=EvidenceSufficiencyStatus.INSUFFICIENT,
            fetch_decision=FetchDecision.FETCH_BLOCKED_NO_REGISTRY,
            freshness_status=FreshnessStatus.UNKNOWN,
            reasons=["no_retrieved_docs", "no_fetchable_registry_candidate"],
        )

    if answer_kind == AnswerKind.SOURCE_NAVIGATION and _has_safe_navigation_source(source_statuses, route_domain=route_domain):
        return EvidenceSufficiencyDecision(
            status=EvidenceSufficiencyStatus.SUFFICIENT,
            fetch_decision=FetchDecision.SKIPPED_RAG_SUFFICIENT,
            freshness_status=_source_navigation_freshness(source_statuses),
            reasons=["official_source_url_is_enough_for_navigation"],
        )

    if answer_kind == AnswerKind.CURRENT_FACT:
        blocking_status = _current_fact_blocking_status(source_statuses)
        if blocking_status is not None:
            return EvidenceSufficiencyDecision(
                status=EvidenceSufficiencyStatus.INSUFFICIENT,
                fetch_decision=blocking_status[0],
                freshness_status=blocking_status[1],
                reasons=blocking_status[2],
            )
        if not _has_structured_current_fact(docs):
            return EvidenceSufficiencyDecision(
                status=EvidenceSufficiencyStatus.INSUFFICIENT,
                fetch_decision=FetchDecision.FETCH_REQUIRED_BUT_NOT_IMPLEMENTED,
                freshness_status=FreshnessStatus.UNKNOWN,
                reasons=["current_fact_requires_structured_fields"],
            )

    top_score = max(retrieved_scores or [0.0])
    if top_score < min_top_score:
        if supported_candidates:
            return EvidenceSufficiencyDecision(
                status=EvidenceSufficiencyStatus.NEEDS_FETCH,
                fetch_decision=FetchDecision.FETCH_REQUIRED_BUT_NOT_IMPLEMENTED,
                freshness_status=FreshnessStatus.UNKNOWN,
                reasons=["top_score_below_threshold", "controlled_fetch_candidate_exists"],
            )
        return EvidenceSufficiencyDecision(
            status=EvidenceSufficiencyStatus.INSUFFICIENT,
            fetch_decision=FetchDecision.FETCH_BLOCKED_NO_REGISTRY,
            freshness_status=FreshnessStatus.UNKNOWN,
            reasons=["top_score_below_threshold", "no_fetchable_registry_candidate"],
        )

    if temporal_intent and RetrievalRequirement.DATE_FILTERED_EVIDENCE_NEEDED in temporal_intent.retrieval_requirements:
        if not _docs_match_temporal_target(docs, temporal_intent=temporal_intent):
            return EvidenceSufficiencyDecision(
                status=EvidenceSufficiencyStatus.INSUFFICIENT,
                fetch_decision=FetchDecision.FETCH_REQUIRED_BUT_NOT_IMPLEMENTED,
                freshness_status=FreshnessStatus.UNKNOWN,
                reasons=["date_filtered_evidence_missing_or_mismatched"],
            )

    return EvidenceSufficiencyDecision(
        status=EvidenceSufficiencyStatus.SUFFICIENT,
        fetch_decision=FetchDecision.SKIPPED_RAG_SUFFICIENT,
        freshness_status=_static_freshness(answer_kind, source_statuses),
        reasons=["retrieved_evidence_passed_threshold"],
    )


def _has_safe_navigation_source(source_statuses: list[SourceStatus], *, route_domain: Domain) -> bool:
    return any(
        status.registry_present
        and status.active
        and status.official_chain_ok
        and status.allowlist_status == AllowlistStatus.ALLOWED
        and status.metadata_domain == route_domain
        and bool(status.source_url)
        for status in source_statuses
    )


def _source_navigation_freshness(source_statuses: list[SourceStatus]) -> FreshnessStatus:
    if any(status.official_chain_ok for status in source_statuses):
        return FreshnessStatus.FRESH
    return FreshnessStatus.UNKNOWN


def _current_fact_blocking_status(
    source_statuses: list[SourceStatus],
) -> tuple[FetchDecision, FreshnessStatus, list[str]] | None:
    if any(not status.registry_present for status in source_statuses):
        return (
            FetchDecision.FETCH_BLOCKED_NO_REGISTRY,
            FreshnessStatus.UNKNOWN,
            ["current_fact_source_missing_from_registry"],
        )
    if any(not status.official_chain_ok for status in source_statuses):
        return (
            FetchDecision.FETCH_BLOCKED_UNOFFICIAL,
            FreshnessStatus.UNVERIFIED_SOURCE,
            ["current_fact_source_not_official_chain_verified"],
        )
    if any(status.allowlist_status != AllowlistStatus.ALLOWED for status in source_statuses):
        return (
            FetchDecision.FETCH_BLOCKED_UNOFFICIAL,
            FreshnessStatus.UNVERIFIED_SOURCE,
            ["current_fact_source_not_allowlisted"],
        )
    return None


def _has_structured_current_fact(docs: list[KnowledgeDoc]) -> bool:
    required_any = ("structured_fields", "valid_at", "effective_date", "menu_date", "operation_date")
    return any(any(key in doc.metadata for key in required_any) for doc in docs)


def _docs_match_temporal_target(docs: list[KnowledgeDoc], *, temporal_intent: TemporalIntent) -> bool:
    if temporal_intent.target_start is None:
        return True
    target = temporal_intent.target_start.isoformat()
    target_end = temporal_intent.target_end or temporal_intent.target_start
    date_keys = ("menu_date", "operation_date", "valid_at", "effective_date", "posted_date")
    for doc in docs:
        values = [doc.date or "", *(str(doc.metadata.get(key, "")) for key in date_keys), doc.body]
        if any(target in value for value in values if value):
            return True
        if _doc_interval_overlaps_target(doc, target_start=temporal_intent.target_start, target_end=target_end):
            return True
    return False


def _doc_interval_overlaps_target(doc: KnowledgeDoc, *, target_start: date, target_end: date) -> bool:
    intervals: list[tuple[date, date]] = []
    valid_start = _parse_iso_date(doc.metadata.get("valid_start"))
    valid_end = _parse_iso_date(doc.metadata.get("valid_end"))
    if valid_start and valid_end:
        intervals.append((valid_start, valid_end))
    date_span = doc.metadata.get("date_span")
    if isinstance(date_span, str):
        intervals.extend(_parse_date_span(date_span))
    return any(_overlaps(start, end, target_start, target_end) for start, end in intervals)


def _parse_date_span(value: str) -> list[tuple[date, date]]:
    matches = [_parse_iso_date(item) for item in re.findall(r"\d{4}-\d{2}-\d{2}", value)]
    dates = [item for item in matches if item is not None]
    if len(dates) >= 2:
        return [(dates[0], dates[1])]
    if len(dates) == 1:
        return [(dates[0], dates[0])]
    return []


def _parse_iso_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _overlaps(left_start: date, left_end: date, right_start: date, right_end: date) -> bool:
    return left_start <= right_end and right_start <= left_end


def _static_freshness(answer_kind: AnswerKind, source_statuses: list[SourceStatus]) -> FreshnessStatus:
    if answer_kind in {AnswerKind.STATIC_FACT, AnswerKind.PROCEDURAL}:
        return FreshnessStatus.NOT_REQUIRED
    if any(status.official_chain_ok for status in source_statuses):
        return FreshnessStatus.FRESH
    return FreshnessStatus.UNKNOWN
