from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from nlp_term.schemas import ChatOutput, Domain


class _StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class AnswerKind(_StrEnum):
    SOURCE_NAVIGATION = "source_navigation"
    STATIC_FACT = "static_fact"
    CURRENT_FACT = "current_fact"
    PROCEDURAL = "procedural"
    UNSUPPORTED = "unsupported"


class IntentStatus(_StrEnum):
    OK = "ok"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


class EvidenceLookupStatus(_StrEnum):
    DOCS_FOUND = "docs_found"
    NO_DOCS = "no_docs"


class EvidenceSufficiencyStatus(_StrEnum):
    SUFFICIENT = "sufficient"
    NEEDS_FETCH = "needs_fetch"
    INSUFFICIENT = "insufficient"
    CONFLICT = "conflict"


class FetchDecision(_StrEnum):
    SKIPPED_RAG_SUFFICIENT = "skipped_rag_sufficient"
    FETCH_ALLOWED = "fetch_allowed"
    FETCH_BLOCKED_NO_REGISTRY = "fetch_blocked_no_registry"
    FETCH_BLOCKED_UNOFFICIAL = "fetch_blocked_unofficial"
    FETCH_BLOCKED_UNSUPPORTED_PARSER = "fetch_blocked_unsupported_parser"
    FETCH_REQUIRED_BUT_NOT_IMPLEMENTED = "fetch_required_but_not_implemented"


class FreshnessStatus(_StrEnum):
    NOT_REQUIRED = "not_required"
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"
    UNVERIFIED_SOURCE = "unverified_source"


class TemporalType(_StrEnum):
    NONE = "none"
    DATE_LOOKUP = "date_lookup"
    CURRENT_SNAPSHOT = "current_snapshot"
    FUTURE_SCHEDULE = "future_schedule"
    LATEST_ITEM = "latest_item"
    CHANGED_SINCE = "changed_since"
    ONGOING_STATUS = "ongoing_status"
    PERIOD_SUMMARY = "period_summary"


class TemporalConfidence(_StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RetrievalRequirement(_StrEnum):
    RAG_OK = "rag_ok"
    DATE_FILTERED_EVIDENCE_NEEDED = "date_filtered_evidence_needed"
    LATEST_LIST_NEEDED = "latest_list_needed"
    STRUCTURED_SOURCE_PREFERRED = "structured_source_preferred"
    VERSION_MATCH_NEEDED = "version_match_needed"
    CHANGE_WINDOW_NEEDED = "change_window_needed"


class ParseStatus(_StrEnum):
    NOT_APPLICABLE = "not_applicable"
    PASSED = "passed"
    FAILED_MOJIBAKE = "failed_mojibake"
    FAILED_REQUIRED_FIELDS = "failed_required_fields"
    UNSUPPORTED = "unsupported"


class PackStatus(_StrEnum):
    BUILT = "built"
    BLOCKED_EMPTY = "blocked_empty"
    BLOCKED_CONFLICT = "blocked_conflict"
    BLOCKED_FETCH_REQUIRED = "blocked_fetch_required"
    BLOCKED_UNSUPPORTED = "blocked_unsupported"


class GenerationStatus(_StrEnum):
    GENERATED = "generated"
    GENERATION_FAILED = "generation_failed"
    FALLBACK_GENERATED = "fallback_generated"
    SKIPPED_BLOCKED = "skipped_blocked"


class AnswerValidationStatus(_StrEnum):
    PASSED = "passed"
    FAILED_UNSUPPORTED_CLAIM = "failed_unsupported_claim"
    FAILED_MISSING_REQUIRED_SOURCE = "failed_missing_required_source"
    FAILED_NUMERIC_OR_DATE_CONFLICT = "failed_numeric_or_date_conflict"
    FAILED_TOO_NOISY = "failed_too_noisy"
    GENERATION_FAILED = "generation_failed"
    BLOCKED = "blocked"


class OutputStatus(_StrEnum):
    ANSWERED = "answered"
    FAIL_CLOSED = "fail_closed"
    UNSUPPORTED = "unsupported"


class AllowlistStatus(_StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class SourceStatus(BaseModel):
    source_id: str
    source_url: str
    registry_present: bool = False
    active: bool = False
    official_chain_ok: bool = False
    parser_type: str | None = None
    freshness_policy: str = "snapshot"
    raw_fetched_at: str | None = None
    allowlist_status: AllowlistStatus = AllowlistStatus.UNKNOWN
    metadata_department: str | None = None
    metadata_curriculum_year: str | None = None
    metadata_domain: Domain | None = None


class RetrievalCandidateTrace(BaseModel):
    doc_id: str
    score: float
    label: int = Field(ge=0, le=4)
    domain: Domain
    source_id: str
    chunking_strategy: str | None = None
    boundary_type: str | None = None
    chunk_confidence: str | None = None


class IntentState(BaseModel):
    question: str
    route_label: int = Field(ge=0, le=4)
    route_domain: Domain
    answer_kind: AnswerKind
    status: IntentStatus = IntentStatus.OK
    department: str | None = None
    curriculum_year: str | None = None
    date: str | None = None
    meal: str | None = None
    location: str | None = None
    route_or_stop: str | None = None
    freshness_cue: str | None = None
    current_requested: bool = False
    question_time: datetime | None = None
    unsupported_reason: str | None = None


class TemporalIntent(BaseModel):
    reference_time: datetime
    timezone: str = "Asia/Seoul"
    week_policy: Literal["iso_monday_to_sunday"] = "iso_monday_to_sunday"
    original_expression: str | None = None
    temporal_type: TemporalType = TemporalType.NONE
    explicitness: Literal["none", "absolute", "relative", "mixed_conflict"] = "none"
    target_start: date | None = None
    target_end: date | None = None
    candidate_dates: list[date] = Field(default_factory=list)
    candidate_periods: list[str] = Field(default_factory=list)
    candidate_resolution_policy: str | None = None
    granularity: Literal["none", "day", "week", "month", "semester", "year"] = "none"
    resolution_policy: str | None = None
    freshness_required: bool = False
    version_match_required: bool = False
    retrieval_requirements: list[RetrievalRequirement] = Field(default_factory=lambda: [RetrievalRequirement.RAG_OK])
    confidence: TemporalConfidence = TemporalConfidence.HIGH
    confidence_reasons: list[str] = Field(default_factory=list)


class EvidenceSufficiencyDecision(BaseModel):
    status: EvidenceSufficiencyStatus
    fetch_decision: FetchDecision
    freshness_status: FreshnessStatus
    reasons: list[str] = Field(default_factory=list)
    conflict_check: Literal["not_applicable", "passed", "conflict"] = "not_applicable"


class HarnessTrace(BaseModel):
    question: str
    mode: Literal["chat", "realtime"]
    route_label: int = Field(ge=0, le=4)
    route_domain: Domain
    answer_kind: AnswerKind
    evidence_lookup_status: EvidenceLookupStatus
    evidence_sufficiency_status: EvidenceSufficiencyStatus
    fetch_decision: FetchDecision
    freshness_status: FreshnessStatus
    parse_status: ParseStatus = ParseStatus.NOT_APPLICABLE
    pack_status: PackStatus
    generation_status: GenerationStatus
    answer_validation_status: AnswerValidationStatus
    output_status: OutputStatus
    generation_backend: str | None = None
    fallback_used: bool = False
    min_top_score: float = 0.20
    temporal_type: TemporalType = TemporalType.NONE
    temporal_confidence: TemporalConfidence = TemporalConfidence.HIGH
    temporal_confidence_reasons: list[str] = Field(default_factory=list)
    target_start: str | None = None
    target_end: str | None = None
    candidate_dates: list[str] = Field(default_factory=list)
    candidate_periods: list[str] = Field(default_factory=list)
    candidate_resolution_policy: str | None = None
    retrieval_requirements: list[RetrievalRequirement] = Field(default_factory=list)
    retrieved_doc_ids: list[str] = Field(default_factory=list)
    retrieved_scores: list[float] = Field(default_factory=list)
    prefilter_retrieved_candidates: list[RetrievalCandidateTrace] = Field(default_factory=list)
    postfilter_retrieved_candidates: list[RetrievalCandidateTrace] = Field(default_factory=list)
    candidate_source_ids: list[str] = Field(default_factory=list)
    source_statuses: list[SourceStatus] = Field(default_factory=list)
    failure_reason: str | None = None
    knowledge_path: str | None = None
    model_path: str | None = None


class HarnessResult(BaseModel):
    output: ChatOutput
    output_status: OutputStatus
    trace: HarnessTrace
    provenance_path: Path | None = None
