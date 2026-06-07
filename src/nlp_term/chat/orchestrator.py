from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from nlp_term.chat.answer_validation import validate_task2_answer
from nlp_term.chat.evidence_pack import build_evidence_pack
from nlp_term.chat.evidence_sufficiency import evaluate_evidence_sufficiency
from nlp_term.chat.prompts import build_task2_prompt
from nlp_term.chat.router import route_question
from nlp_term.chat.source_status import build_source_status
from nlp_term.chat.state_contract import (
    AnswerKind,
    AnswerValidationStatus,
    EvidenceLookupStatus,
    EvidenceSufficiencyStatus,
    GenerationStatus,
    HarnessResult,
    HarnessTrace,
    OutputStatus,
    PackStatus,
    SourceStatus,
)
from nlp_term.chat.temporal_intent import resolve_temporal_intent
from nlp_term.collect.source_inventory import SourceSpec, Stage, iter_specs
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
    route = route_question(question)
    route_domain = route.domain  # type: ignore[assignment]
    resolved_question_time = question_time or datetime.now(timezone.utc)
    temporal_intent = resolve_temporal_intent(
        question,
        route_domain=route_domain,
        reference_time=resolved_question_time,
    )
    answer_kind = _infer_answer_kind(question, route_domain=route_domain, mode=mode)
    evidence_pack_size = _evidence_pack_size(temporal_intent)

    knowledge = load_knowledge_with_metadata(knowledge_path)
    retrieved = rank_docs(question, knowledge.docs, top_k=max(6, evidence_pack_size))
    docs_by_id = {doc.doc_id: doc for doc in knowledge.docs}
    retrieved_pairs = [
        (docs_by_id[row.doc_id], row.score)
        for row in retrieved
        if row.doc_id in docs_by_id and docs_by_id[row.doc_id].label == route.label
    ][:evidence_pack_size]
    retrieved_docs = [doc for doc, _score in retrieved_pairs]
    retrieved_scores = [score for _doc, score in retrieved_pairs]
    source_statuses = [build_source_status(doc) for doc in retrieved_docs]
    candidate_specs = _candidate_specs(allowed_stages)

    sufficiency = evaluate_evidence_sufficiency(
        answer_kind=answer_kind,
        docs=retrieved_docs,
        retrieved_scores=retrieved_scores,
        source_statuses=source_statuses,
        candidate_specs=candidate_specs,
        route_domain=route_domain,
        min_top_score=min_top_score,
        question_time=question_time,
        temporal_intent=temporal_intent,
    )

    if sufficiency.status != EvidenceSufficiencyStatus.SUFFICIENT:
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
            source_statuses=source_statuses,
            sufficiency=sufficiency,
            pack_status=PackStatus.BLOCKED_UNSUPPORTED
            if answer_kind == AnswerKind.UNSUPPORTED
            else PackStatus.BLOCKED_FETCH_REQUIRED,
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


def _infer_answer_kind(
    question: str,
    *,
    route_domain: Domain,
    mode: Literal["chat", "realtime"],
) -> AnswerKind:
    compact = question.replace(" ", "")
    is_source_navigation = any(keyword in compact for keyword in ("어디서", "어디", "링크", "홈페이지", "사이트", "게시판", "페이지"))
    if is_source_navigation and _domain_cue_count(compact) >= 2:
        return AnswerKind.UNSUPPORTED
    if is_source_navigation:
        return AnswerKind.SOURCE_NAVIGATION
    if mode == "realtime" or any(keyword in compact for keyword in ("오늘", "이번주", "최신", "현재", "방금", "마감", "운행중")):
        if route_domain in {"dining", "shuttle", "notices", "academic_calendar"}:
            return AnswerKind.CURRENT_FACT
    if any(keyword in compact for keyword in ("방법", "절차", "신청", "제출")):
        return AnswerKind.PROCEDURAL
    return AnswerKind.STATIC_FACT


def _domain_cue_count(compact_question: str) -> int:
    domain_keywords = {
        "graduation": ("졸업", "학점", "전공", "교양", "수료", "요건"),
        "notices": ("공지", "장학", "모집", "안내문", "게시"),
        "academic_calendar": ("학사일정", "수강신청", "수강정정", "개강", "종강", "휴학", "복학"),
        "dining": ("식단", "학식", "메뉴", "학생식당", "점심", "저녁", "아침"),
        "shuttle": ("셔틀", "통학", "버스", "정류장", "시간표", "운행"),
    }
    return sum(int(any(keyword in compact_question for keyword in keywords)) for keywords in domain_keywords.values())


def _candidate_specs(allowed_stages: set[Stage]) -> list[SourceSpec]:
    specs = []
    for stage in allowed_stages:
        specs.extend(iter_specs(stage=stage, active_only=True))
    return specs


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
    lines.append("- 해석된 날짜 또는 기간과 맞지 않는 근거로는 날짜, 메뉴, 운행 여부를 단정하지 않는다.")
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
        retrieval_requirements=temporal_intent.retrieval_requirements,
        retrieved_doc_ids=[doc.doc_id for doc in retrieved_docs],
        retrieved_scores=retrieved_scores,
        candidate_source_ids=[status.source_id for status in source_statuses],
        source_statuses=source_statuses,
        failure_reason=failure_reason,
        knowledge_path=str(knowledge_path) if knowledge_path else None,
        model_path=str(model_path),
    )
