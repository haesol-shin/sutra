from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from nlp_term.chat.answer_validation import validate_task2_answer
from nlp_term.chat.evidence_pack import build_evidence_pack
from nlp_term.chat.prompts import build_task2_prompt
from nlp_term.chat.router import route_question
from nlp_term.chat.source_status import build_source_status
from nlp_term.chat.state_contract import (
    AnswerKind,
    AnswerValidationStatus,
    EvidenceLookupStatus,
    EvidenceSufficiencyStatus,
    EvidenceSufficiencyDecision,
    FetchDecision,
    FreshnessStatus,
    GenerationStatus,
    HarnessResult,
    HarnessTrace,
    OutputStatus,
    PackStatus,
    RetrievalCandidateTrace,
    SourceStatus,
    TemporalType,
)
from nlp_term.chat.temporal_intent import resolve_temporal_intent
from nlp_term.collect.source_inventory import Stage
from nlp_term.paths import model_dir
from nlp_term.retrieve.knowledge import load_knowledge_with_metadata
from nlp_term.retrieve.rank import rank_docs
from nlp_term.schemas import ChatOutput, Domain, KnowledgeDoc


DEFAULT_MODEL_PATH = model_dir() / "qwen3.5-9b-instruct-q4_k_m.gguf"


def answer_with_harness(
    question: str,
    *,
    mode: Literal["chat", "realtime"] = "chat",
    backend: Literal["auto", "llama", "deterministic"] = "auto",
    knowledge_path: Path | None = None,
    model_path: Path = DEFAULT_MODEL_PATH,
    generator: Callable[[str], str] | None = None,
    live_fetch_enabled: bool = False,
    min_top_score: float = 0.20,
    question_time: datetime | None = None,
    allowed_stages: set[Stage] = {"stage0"},
) -> HarnessResult:
    del live_fetch_enabled, allowed_stages
    route = route_question(question)
    route_domain = route.domain  # type: ignore[assignment]
    resolved_question_time = question_time or datetime.now(timezone.utc)
    temporal_intent = resolve_temporal_intent(
        question,
        route_domain=route_domain,
        reference_time=resolved_question_time,
    )
    answer_kind = AnswerKind.STATIC_FACT
    evidence_pack_size = _evidence_pack_size(temporal_intent)

    knowledge = load_knowledge_with_metadata(knowledge_path)
    decision_top_k = max(12, evidence_pack_size * 3)
    diagnostic_top_k = max(24, evidence_pack_size * 4)
    decision_retrieved = rank_docs(question, knowledge.docs, top_k=decision_top_k)
    diagnostic_retrieved = rank_docs(question, knowledge.docs, top_k=diagnostic_top_k)
    docs_by_id = {doc.doc_id: doc for doc in knowledge.docs}
    prefilter_candidates = _candidate_trace_rows(diagnostic_retrieved, docs_by_id)
    candidate_pairs = [
        (docs_by_id[row.doc_id], row.score)
        for row in decision_retrieved
        if row.doc_id in docs_by_id
    ]
    retrieved_pairs = _prefer_route_pairs(candidate_pairs, route_label=route.label, min_score=min_top_score)
    retrieved_pairs = _order_retrieved_pairs(retrieved_pairs, temporal_type=temporal_intent.temporal_type)
    retrieved_pairs = _prioritize_retrieved_pairs(
        retrieved_pairs,
        question=question,
        route_label=route.label,
        temporal_intent=temporal_intent,
    )
    retrieved_pairs = _deduplicate_retrieved_pairs(retrieved_pairs)[:evidence_pack_size]
    retrieved_docs = [doc for doc, _score in retrieved_pairs]
    retrieved_scores = [score for _doc, score in retrieved_pairs]
    postfilter_candidates = _selected_candidate_trace_rows(retrieved_pairs)
    source_statuses = [build_source_status(doc) for doc in retrieved_docs]

    sufficiency = _minimal_evidence_decision(retrieved_docs)

    if not retrieved_docs:
        answer = _fail_closed_answer(sufficiency.reasons)
        trace = _build_trace(
            question=question,
            mode=mode,
            route_label=route.label,
            route_domain=route_domain,
            answer_kind=answer_kind,
            temporal_intent=temporal_intent,
            knowledge_path=knowledge.path,
            model_path=model_path,
            retrieved_docs=retrieved_docs,
            retrieved_scores=retrieved_scores,
            prefilter_candidates=prefilter_candidates,
            postfilter_candidates=postfilter_candidates,
            source_statuses=source_statuses,
            sufficiency=sufficiency,
            pack_status=PackStatus.BLOCKED_EMPTY,
            generation_status=GenerationStatus.SKIPPED_BLOCKED,
            answer_validation_status=AnswerValidationStatus.BLOCKED,
            output_status=OutputStatus.FAIL_CLOSED,
            generation_backend=None,
            min_top_score=min_top_score,
            failure_reason=";".join(sufficiency.reasons),
        )
        return HarnessResult(output=ChatOutput(user=question, model=answer), output_status=OutputStatus.FAIL_CLOSED, trace=trace)

    pack = build_evidence_pack(
        question=question,
        label=route.label,
        domain=route_domain,
        docs=retrieved_docs,
        max_items=evidence_pack_size,
        max_fact_chars=500,
        temporal_context=_render_temporal_context(temporal_intent),
    )
    if not pack.items:
        answer = _fail_closed_answer(["empty_evidence_pack"])
        trace = _build_trace(
            question=question,
            mode=mode,
            route_label=route.label,
            route_domain=route_domain,
            answer_kind=answer_kind,
            temporal_intent=temporal_intent,
            knowledge_path=knowledge.path,
            model_path=model_path,
            retrieved_docs=retrieved_docs,
            retrieved_scores=retrieved_scores,
            prefilter_candidates=prefilter_candidates,
            postfilter_candidates=postfilter_candidates,
            source_statuses=source_statuses,
            sufficiency=sufficiency,
            pack_status=PackStatus.BLOCKED_EMPTY,
            generation_status=GenerationStatus.SKIPPED_BLOCKED,
            answer_validation_status=AnswerValidationStatus.BLOCKED,
            output_status=OutputStatus.FAIL_CLOSED,
            generation_backend=None,
            min_top_score=min_top_score,
            failure_reason="empty_evidence_pack",
        )
        return HarnessResult(output=ChatOutput(user=question, model=answer), output_status=OutputStatus.FAIL_CLOSED, trace=trace)

    prompt = build_task2_prompt(pack)
    generated, generation_backend = _generate_answer(
        prompt,
        route=route,
        backend=backend,
        generator=generator,
        docs=retrieved_docs,
        knowledge_path=knowledge.path,
        model_path=model_path,
    )
    validation = validate_task2_answer(generated, evidence_texts=[pack.to_prompt_text()])
    if not validation.passed:
        answer = _fail_closed_answer(validation.failures)
        trace = _build_trace(
            question=question,
            mode=mode,
            route_label=route.label,
            route_domain=route_domain,
            answer_kind=answer_kind,
            temporal_intent=temporal_intent,
            knowledge_path=knowledge.path,
            model_path=model_path,
            retrieved_docs=retrieved_docs,
            retrieved_scores=retrieved_scores,
            prefilter_candidates=prefilter_candidates,
            postfilter_candidates=postfilter_candidates,
            source_statuses=source_statuses,
            sufficiency=sufficiency,
            pack_status=PackStatus.BUILT,
            generation_status=GenerationStatus.GENERATED,
            answer_validation_status=AnswerValidationStatus.FAILED_UNSUPPORTED_CLAIM,
            output_status=OutputStatus.FAIL_CLOSED,
            generation_backend=generation_backend,
            min_top_score=min_top_score,
            failure_reason=";".join(validation.failures),
        )
        return HarnessResult(output=ChatOutput(user=question, model=answer), output_status=OutputStatus.FAIL_CLOSED, trace=trace)

    trace = _build_trace(
        question=question,
        mode=mode,
        route_label=route.label,
        route_domain=route_domain,
        answer_kind=answer_kind,
        temporal_intent=temporal_intent,
        knowledge_path=knowledge.path,
        model_path=model_path,
        retrieved_docs=retrieved_docs,
        retrieved_scores=retrieved_scores,
        prefilter_candidates=prefilter_candidates,
        postfilter_candidates=postfilter_candidates,
        source_statuses=source_statuses,
        sufficiency=sufficiency,
        pack_status=PackStatus.BUILT,
        generation_status=GenerationStatus.GENERATED,
        answer_validation_status=AnswerValidationStatus.PASSED,
        output_status=OutputStatus.ANSWERED,
        generation_backend=generation_backend,
        min_top_score=min_top_score,
    )
    return HarnessResult(output=ChatOutput(user=question, model=generated), output_status=OutputStatus.ANSWERED, trace=trace)


def _minimal_evidence_decision(docs: list[KnowledgeDoc]) -> EvidenceSufficiencyDecision:
    if not docs:
        return EvidenceSufficiencyDecision(
            status=EvidenceSufficiencyStatus.INSUFFICIENT,
            fetch_decision=FetchDecision.FETCH_BLOCKED_NO_REGISTRY,
            freshness_status=FreshnessStatus.UNKNOWN,
            reasons=["no_retrieved_docs"],
        )
    return EvidenceSufficiencyDecision(
        status=EvidenceSufficiencyStatus.SUFFICIENT,
        fetch_decision=FetchDecision.SKIPPED_RAG_SUFFICIENT,
        freshness_status=FreshnessStatus.UNKNOWN,
        reasons=["retrieved_evidence_available"],
    )


def _candidate_trace_rows(rows, docs_by_id: dict[str, KnowledgeDoc]) -> list[RetrievalCandidateTrace]:
    trace_rows: list[RetrievalCandidateTrace] = []
    for row in rows:
        doc = docs_by_id.get(row.doc_id)
        if doc is None:
            continue
        trace_rows.append(
            RetrievalCandidateTrace(
                doc_id=doc.doc_id,
                score=row.score,
                label=doc.label,
                domain=doc.domain,
                source_id=doc.source_id,
                chunking_strategy=_optional_metadata_text(doc, "chunking_strategy"),
                boundary_type=_optional_metadata_text(doc, "boundary_type"),
                chunk_confidence=_optional_metadata_text(doc, "chunk_confidence"),
            )
        )
    return trace_rows


def _prefer_route_pairs(
    retrieved_pairs: list[tuple[KnowledgeDoc, float]],
    *,
    route_label: int,
    min_score: float,
) -> list[tuple[KnowledgeDoc, float]]:
    eligible = [(doc, score) for doc, score in retrieved_pairs if score >= min_score]
    if eligible:
        return sorted(eligible, key=lambda pair: (pair[0].label == route_label, pair[1]), reverse=True)
    return [(doc, score) for doc, score in retrieved_pairs if doc.label == route_label]


def _selected_candidate_trace_rows(retrieved_pairs: list[tuple[KnowledgeDoc, float]]) -> list[RetrievalCandidateTrace]:
    return [
        RetrievalCandidateTrace(
            doc_id=doc.doc_id,
            score=score,
            label=doc.label,
            domain=doc.domain,
            source_id=doc.source_id,
            chunking_strategy=_optional_metadata_text(doc, "chunking_strategy"),
            boundary_type=_optional_metadata_text(doc, "boundary_type"),
            chunk_confidence=_optional_metadata_text(doc, "chunk_confidence"),
        )
        for doc, score in retrieved_pairs
    ]


def _order_retrieved_pairs(
    retrieved_pairs: list[tuple[KnowledgeDoc, float]],
    *,
    temporal_type: TemporalType,
) -> list[tuple[KnowledgeDoc, float]]:
    if temporal_type != TemporalType.LATEST_ITEM:
        return retrieved_pairs
    return sorted(retrieved_pairs, key=lambda pair: (_posted_date_key(pair[0]), pair[1]), reverse=True)


def _posted_date_key(doc: KnowledgeDoc) -> str:
    posted_date = doc.metadata.get("posted_date")
    if isinstance(posted_date, str):
        return posted_date
    return doc.date or ""


def _prioritize_retrieved_pairs(
    retrieved_pairs: list[tuple[KnowledgeDoc, float]],
    *,
    question: str,
    route_label: int,
    temporal_intent,
) -> list[tuple[KnowledgeDoc, float]]:
    compact_question = question.replace(" ", "")
    return sorted(
        retrieved_pairs,
        key=lambda pair: (
            pair[0].label == route_label,
            _temporal_match_score(pair[0], temporal_intent=temporal_intent),
            _structured_score(pair[0]),
            _alias_match_score(pair[0], compact_question),
            pair[1],
        ),
        reverse=True,
    )


def _deduplicate_retrieved_pairs(retrieved_pairs: list[tuple[KnowledgeDoc, float]]) -> list[tuple[KnowledgeDoc, float]]:
    selected: list[tuple[KnowledgeDoc, float]] = []
    seen_fact_keys: set[str] = set()
    seen_scope_keys: set[str] = set()
    for doc, score in retrieved_pairs:
        fact_key = _fact_key(doc)
        if fact_key:
            if fact_key in seen_fact_keys:
                continue
            seen_fact_keys.add(fact_key)
        scope_key = _scope_key(doc)
        if scope_key:
            if scope_key in seen_scope_keys:
                continue
            seen_scope_keys.add(scope_key)
        selected.append((doc, score))
    return selected


def _fact_key(doc: KnowledgeDoc) -> str | None:
    metadata = doc.metadata
    row_type = metadata.get("row_type")
    if row_type == "academic_calendar_event":
        return _join_key(
            "calendar_event",
            metadata.get("start_date"),
            metadata.get("end_date"),
            metadata.get("event_name"),
        )
    if row_type == "dining_menu":
        return _join_key(
            "dining_menu",
            metadata.get("menu_date"),
            metadata.get("cafeteria"),
            metadata.get("meal_type"),
            metadata.get("user_type"),
        )
    return None


def _scope_key(doc: KnowledgeDoc) -> str | None:
    metadata = doc.metadata
    row_type = metadata.get("row_type")
    if row_type == "academic_calendar_monthly":
        return _join_key("calendar_month", metadata.get("academic_year"), metadata.get("month"))
    if row_type == "academic_calendar_semester":
        return _join_key("calendar_semester", metadata.get("academic_year"), metadata.get("semester"))
    if row_type == "dining_weekly_menu":
        return _join_key("dining_week", metadata.get("week_start"), metadata.get("week_end"), metadata.get("cafeteria"))
    return None


def _join_key(*values: object) -> str | None:
    parts = [str(value).strip() for value in values if value is not None and str(value).strip()]
    if len(parts) != len(values):
        return None
    return ":".join(parts)


def _temporal_match_score(doc: KnowledgeDoc, *, temporal_intent) -> int:
    if temporal_intent.target_start is None:
        return 0
    target_end = temporal_intent.target_end or temporal_intent.target_start
    if _doc_interval_overlaps(doc, target_start=temporal_intent.target_start, target_end=target_end):
        return 2
    target = temporal_intent.target_start.isoformat()
    date_keys = ("menu_date", "operation_date", "valid_at", "effective_date", "posted_date", "start_date", "end_date")
    values = [doc.date or "", *(str(doc.metadata.get(key, "")) for key in date_keys), doc.body]
    return int(any(target in value for value in values if value))


def _structured_score(doc: KnowledgeDoc) -> int:
    return int(doc.metadata.get("generation_method") == "structured_row" or "structured" in doc.metadata)


def _alias_match_score(doc: KnowledgeDoc, compact_question: str) -> int:
    aliases = doc.metadata.get("search_aliases")
    if not isinstance(aliases, list):
        return 0
    return sum(int(str(alias).replace(" ", "") in compact_question) for alias in aliases)


def _doc_interval_overlaps(doc: KnowledgeDoc, *, target_start: date, target_end: date) -> bool:
    spans = []
    date_span = doc.metadata.get("date_span")
    if isinstance(date_span, str):
        spans.extend(_parse_date_span(date_span))
    start = _parse_iso_date(doc.metadata.get("start_date") or doc.metadata.get("valid_start"))
    end = _parse_iso_date(doc.metadata.get("end_date") or doc.metadata.get("valid_end"))
    if start and end:
        spans.append((start, end))
    return any(left <= target_end and target_start <= right for left, right in spans)


def _parse_date_span(value: str) -> list[tuple[date, date]]:
    parts = [part for part in value.replace("/", " ").split() if part]
    dates = [_parse_iso_date(part) for part in parts]
    parsed = [item for item in dates if item is not None]
    if len(parsed) >= 2:
        return [(parsed[0], parsed[1])]
    if len(parsed) == 1:
        return [(parsed[0], parsed[0])]
    return []


def _parse_iso_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _optional_metadata_text(doc: KnowledgeDoc, key: str) -> str | None:
    value = doc.metadata.get(key)
    return str(value) if value is not None else None


def _evidence_pack_size(temporal_intent) -> int:
    if temporal_intent.temporal_type in {"period_summary", "changed_since"}:
        return 8
    if temporal_intent.freshness_required or temporal_intent.temporal_type != "none":
        return 5
    return 3


def _generate_answer(
    prompt: str,
    *,
    route,
    backend: Literal["auto", "llama", "deterministic"],
    generator: Callable[[str], str] | None,
    docs: list[KnowledgeDoc],
    knowledge_path: Path | None,
    model_path: Path,
) -> tuple[str, str]:
    if generator is not None:
        return generator(prompt), "injected"
    if backend == "llama":
        from nlp_term.chat.llama_backend import generate_llama_answer

        return generate_llama_answer(route, knowledge_path=knowledge_path, model_path=model_path), "llama"
    return _deterministic_answer(docs), "deterministic"


def _deterministic_answer(docs: list[KnowledgeDoc]) -> str:
    if not docs:
        return "공식 근거가 충분하지 않아 확답하기 어렵습니다. 충남대학교 공식 페이지를 확인해 주세요."
    doc = docs[0]
    return f"{doc.body.strip()} 자세한 내용은 {doc.source_url}에서 확인해 주세요."


def _fail_closed_answer(reasons: list[str]) -> str:
    return "공식 근거가 충분하지 않아 확답하기 어렵습니다. 충남대학교 공식 출처를 기준으로 다시 확인해 주세요."


def _render_temporal_context(temporal_intent) -> str | None:
    if temporal_intent.temporal_type == "none":
        return None
    lines = [f"- 현재 기준일: {temporal_intent.reference_time.date().isoformat()}"]
    if temporal_intent.original_expression:
        lines.append(f"- 질문의 시간 표현: {temporal_intent.original_expression}")
    if temporal_intent.target_start and temporal_intent.target_end:
        if temporal_intent.target_start == temporal_intent.target_end:
            lines.append(f"- 해석된 날짜: {temporal_intent.target_start.isoformat()}")
        else:
            lines.append(f"- 해석된 기간: {temporal_intent.target_start.isoformat()} ~ {temporal_intent.target_end.isoformat()}")
    if temporal_intent.candidate_dates:
        dates = ", ".join(item.isoformat() for item in temporal_intent.candidate_dates)
        lines.append(f"- 후보 날짜: {dates}")
    if temporal_intent.candidate_periods:
        lines.append(f"- 후보 기간: {', '.join(temporal_intent.candidate_periods)}")
    if temporal_intent.candidate_resolution_policy:
        lines.append(f"- 날짜 해석 정책: {temporal_intent.candidate_resolution_policy}")
    lines.append("- 후보 날짜 또는 기간과 맞는 근거를 우선 사용하고, 맞지 않는 근거로는 날짜, 메뉴, 운행 여부를 단정하지 않는다.")
    return "\n".join(lines)


def _build_trace(
    *,
    question: str,
    mode: Literal["chat", "realtime"],
    route_label: int,
    route_domain: Domain,
    answer_kind: AnswerKind,
    temporal_intent,
    knowledge_path: Path | None,
    model_path: Path,
    retrieved_docs: list[KnowledgeDoc],
    retrieved_scores: list[float],
    prefilter_candidates: list[RetrievalCandidateTrace],
    postfilter_candidates: list[RetrievalCandidateTrace],
    source_statuses: list[SourceStatus],
    sufficiency,
    pack_status: PackStatus,
    generation_status: GenerationStatus,
    answer_validation_status: AnswerValidationStatus,
    output_status: OutputStatus,
    generation_backend: str | None,
    min_top_score: float,
    failure_reason: str | None = None,
) -> HarnessTrace:
    return HarnessTrace(
        question=question,
        mode=mode,
        route_label=route_label,
        route_domain=route_domain,
        answer_kind=answer_kind,
        evidence_lookup_status=EvidenceLookupStatus.DOCS_FOUND if retrieved_docs else EvidenceLookupStatus.NO_DOCS,
        evidence_sufficiency_status=sufficiency.status,
        fetch_decision=sufficiency.fetch_decision,
        freshness_status=sufficiency.freshness_status,
        pack_status=pack_status,
        generation_status=generation_status,
        answer_validation_status=answer_validation_status,
        output_status=output_status,
        generation_backend=generation_backend,
        min_top_score=min_top_score,
        temporal_type=temporal_intent.temporal_type,
        temporal_confidence=temporal_intent.confidence,
        temporal_confidence_reasons=temporal_intent.confidence_reasons,
        target_start=temporal_intent.target_start.isoformat() if temporal_intent.target_start else None,
        target_end=temporal_intent.target_end.isoformat() if temporal_intent.target_end else None,
        candidate_dates=[item.isoformat() for item in temporal_intent.candidate_dates],
        candidate_periods=temporal_intent.candidate_periods,
        candidate_resolution_policy=temporal_intent.candidate_resolution_policy,
        retrieval_requirements=temporal_intent.retrieval_requirements,
        retrieved_doc_ids=[doc.doc_id for doc in retrieved_docs],
        retrieved_scores=retrieved_scores,
        prefilter_retrieved_candidates=prefilter_candidates,
        postfilter_retrieved_candidates=postfilter_candidates,
        candidate_source_ids=[status.source_id for status in source_statuses],
        source_statuses=source_statuses,
        failure_reason=failure_reason,
        knowledge_path=str(knowledge_path) if knowledge_path else None,
        model_path=str(model_path),
    )
