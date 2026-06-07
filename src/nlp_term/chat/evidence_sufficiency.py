from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from nlp_term.chat.controlled_fetch import fetchable_specs
from nlp_term.chat.state_contract import (
    AllowlistStatus,
    AnswerKind,
    EvidenceSufficiencyDecision,
    EvidenceSufficiencyStatus,
    FetchDecision,
    FreshnessStatus,
    SourceStatus,
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

    if answer_kind == AnswerKind.CURRENT_FACT and not _has_structured_current_fact(docs):
        return EvidenceSufficiencyDecision(
            status=EvidenceSufficiencyStatus.INSUFFICIENT,
            fetch_decision=FetchDecision.FETCH_REQUIRED_BUT_NOT_IMPLEMENTED,
            freshness_status=FreshnessStatus.UNKNOWN,
            reasons=["current_fact_requires_structured_fields"],
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


def _static_freshness(answer_kind: AnswerKind, source_statuses: list[SourceStatus]) -> FreshnessStatus:
    if answer_kind in {AnswerKind.STATIC_FACT, AnswerKind.PROCEDURAL}:
        return FreshnessStatus.NOT_REQUIRED
    if any(status.official_chain_ok for status in source_statuses):
        return FreshnessStatus.FRESH
    return FreshnessStatus.UNKNOWN
