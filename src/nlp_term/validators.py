from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import inspect
import json
from pathlib import Path
import re
import unicodedata
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from nlp_term.schemas import (
    ChatInput,
    ChatOutput,
    ClassificationInput,
    ClassificationOutput,
    ClassificationExample,
    KnowledgeDoc,
    LabelAudit,
    ModelCandidate,
    QAExample,
    RealtimeOutput,
    RawSource,
    SourceVerification,
)


ModelT = TypeVar("ModelT", bound=BaseModel)
BANNED_OUTPUT_TERMS = ("dry-run", "dry_run", "stub", "parser 미구현", "제출 구현에서는")
UNSUPPORTED_REALTIME_CLAIMS = (
    "검증된 공식 source",
    "저장된 공식 source",
    "공식 source snapshot",
    "최신 정보는",
    "실시간 조회가",
)
QUESTION_NORMALIZE_RE = re.compile(r"\s+")
QA_BOILERPLATE_TERMS = (
    "본문 바로가기",
    "사이드메뉴",
    "주요메뉴",
    "통합검색",
    "사이트맵",
    "CNU홍보",
    "CNU 홍보브로슈어",
    "사이버투어",
    "THE STRONG CNU",
    "미래 사회를 선도할",
    "홍보동영상",
    "홍보브로슈어",
    "캠퍼스투어",
    "대학/대학원",
    "열기 버튼",
    "닫기버튼",
    "All Rights Reserved",
    "Login",
    "ENG",
    "SNS",
    "URL복사",
    "facebook",
    "카카오톡",
    "Naver",
    "print",
    "학사서비스소개",
    "교직원커뮤니티",
    "백마게시판",
    "금주의식단",
    "온라인FAQ",
    "학생증발급안내",
    "학생생활관안내",
    "주차안내",
    "교내현수막관리",
    "기타 서비스안내",
    "교내복지안내",
    "편의시설안내",
    "시설이용안내",
    "입법예고",
    "주간업무추진계획",
    "행정정보",
    "입찰공고",
    "대학정보공시",
    "청렴행정",
    "회의실예약",
)
GENERIC_QA_PHRASES = (
    "자료를 우선 확인해야 합니다.",
    "공식 source에서 확인한 해당 주제의 안내 범위와 근거",
)
QA_LABEL_KEYWORDS: dict[int, tuple[str, ...]] = {
    0: ("졸업", "교양", "전공", "학점", "교육과정", "이수"),
    1: ("공지", "학사정보", "게시", "백마광장", "학사지원과", "작성일", "조회수", "수강신청", "휴학", "복학"),
    2: ("학사일정", "일정", "학기"),
    3: ("식단", "메뉴", "학생회관", "조식", "중식", "석식"),
    4: ("셔틀", "버스", "통학", "시간표", "운행"),
}
QA_EVIDENCE_RE = re.compile(r"'([^']+)'")


def read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def file_checksum(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, rows: list[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [row.model_dump() for row in rows]
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def validate_rows(path: Path, model_type: type[ModelT], *, required: bool = True) -> list[ModelT]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return []
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    return [model_type.model_validate(row) for row in payload]


def validate_inputs(data_dir: Path, *, require_realtime: bool = False) -> None:
    validate_rows(data_dir / "test_cls.json", ClassificationInput, required=True)
    validate_rows(data_dir / "test_chat.json", ChatInput, required=True)
    validate_rows(data_dir / "test_realtime.json", ChatInput, required=require_realtime)


def validate_outputs(outputs_dir: Path, *, require_realtime: bool = False) -> None:
    validate_rows(outputs_dir / "cls_output.json", ClassificationOutput, required=True)
    validate_rows(outputs_dir / "chat_output.json", ChatOutput, required=True)
    validate_rows(outputs_dir / "realtime_output.json", RealtimeOutput, required=require_realtime)


def validate_seed_data(data_dir: Path) -> None:
    docs = validate_rows(data_dir / "knowledge_seed.json", KnowledgeDoc, required=True)
    examples = validate_rows(data_dir / "cls_train_seed.json", ClassificationExample, required=True)
    audits = validate_rows(data_dir / "label_audit_seed.json", LabelAudit, required=True)
    qa_rows = validate_rows(data_dir / "qa_seed.json", QAExample, required=True)
    docs_by_id = {doc.doc_id: doc for doc in docs}
    if {doc.label for doc in docs} != {0, 1, 2, 3, 4}:
        raise ValueError("knowledge_seed.json must cover labels 0-4")
    for doc in docs:
        _validate_knowledge_body_text(doc)
    if any(not row.validated for row in examples):
        raise ValueError("cls_train_seed.json contains unvalidated examples")
    if any(row.decision != "accept" for row in audits):
        raise ValueError("label_audit_seed.json contains non-accepted audit rows")
    if any(not row.validated for row in qa_rows):
        raise ValueError("qa_seed.json contains unvalidated rows")
    for row in qa_rows:
        _validate_qa_answer_text(row, docs_by_id=docs_by_id)


def validate_source_probe(path: Path, *, require_raw_files: bool = False) -> None:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError(f"{path} rows must be objects")
        raw = RawSource.model_validate(row.get("raw"))
        SourceVerification.model_validate(row.get("verification"))
        raw_path = Path(raw.raw_path)
        if require_raw_files:
            if not raw_path.exists():
                raise FileNotFoundError(raw.raw_path)
            if raw.status_code is None or not 200 <= raw.status_code < 300:
                raise ValueError(f"{raw.source_id} has non-2xx status: {raw.status_code}")
            checksum = sha256(raw_path.read_bytes()).hexdigest()
            if checksum != raw.checksum:
                raise ValueError(f"{raw.source_id} checksum does not match raw file")


def validate_knowledge_provenance(
    data_dir: Path,
    source_probe_path: Path,
    *,
    require_official_chain: bool = False,
) -> None:
    probe_payload = read_json(source_probe_path)
    if not isinstance(probe_payload, list):
        raise ValueError(f"{source_probe_path} must contain a JSON list")
    source_map: dict[str, tuple[RawSource, SourceVerification]] = {}
    for row in probe_payload:
        raw = RawSource.model_validate(row.get("raw"))
        verification = SourceVerification.model_validate(row.get("verification"))
        source_map[raw.source_id] = (raw, verification)
    docs = validate_rows(data_dir / "knowledge_seed.json", KnowledgeDoc, required=True)
    for doc in docs:
        if doc.source_id not in source_map:
            raise ValueError(f"{doc.doc_id} references missing source_id {doc.source_id}")
        raw, verification = source_map[doc.source_id]
        if raw.status_code is not None and not 200 <= raw.status_code < 300:
            raise ValueError(f"{doc.doc_id} source has non-2xx status: {raw.status_code}")
        if require_official_chain and not verification.official_chain_ok:
            raise ValueError(f"{doc.doc_id} source is not official-chain verified")


def validate_model_shortlist(path: Path) -> None:
    rows = validate_rows(path, ModelCandidate, required=True)
    if not any(row.status == "primary" for row in rows):
        raise ValueError("model shortlist needs one primary candidate")
    if any(row.max_params_b > 9 and row.status in {"primary", "candidate"} for row in rows):
        raise ValueError("primary/candidate models must stay at or below 9B parameters")


def validate_final_readiness(outputs_dir: Path) -> None:
    for filename in ("chat_output.json", "realtime_output.json"):
        path = outputs_dir / filename
        text = path.read_text(encoding="utf-8").lower()
        for term in BANNED_OUTPUT_TERMS:
            if term.lower() in text:
                raise ValueError(f"{path} contains final-readiness banned term: {term}")
    realtime_path = outputs_dir / "realtime_output.json"
    if realtime_path.exists():
        validate_realtime_provenance(realtime_path)


def validate_realtime_provenance(output_path: Path, source_probe_path: Path | None = None) -> None:
    rows = validate_rows(output_path, RealtimeOutput, required=True)
    if source_probe_path is None:
        any_official_chain = False
    else:
        payload = read_json(source_probe_path)
        if not isinstance(payload, list):
            raise ValueError(f"{source_probe_path} must contain a JSON list")
        any_official_chain = any(
            SourceVerification.model_validate(row.get("verification")).official_chain_ok for row in payload
        )
    if any_official_chain:
        return
    for row in rows:
        for term in UNSUPPORTED_REALTIME_CLAIMS:
            if term.casefold() in row.model.casefold():
                raise ValueError(f"realtime-provenance: unsupported realtime/source claim {term}: {row.user}")


def validate_knowledge_quality(
    path: Path,
    *,
    source_probe_path: Path | None = None,
    min_docs_per_label: int | None = None,
    min_body_chars: int | None = None,
    min_source_parse_ratio: float | None = None,
) -> None:
    docs = validate_rows(path, KnowledgeDoc, required=True)
    if source_probe_path:
        payload = read_json(source_probe_path)
        if not isinstance(payload, list):
            raise ValueError(f"{source_probe_path} must contain a JSON list")
        source_ids = {RawSource.model_validate(row.get("raw")).source_id for row in payload}
        for doc in docs:
            if doc.source_id not in source_ids:
                raise ValueError(f"knowledge-quality: {doc.doc_id} references missing source {doc.source_id}")
    if min_docs_per_label is not None:
        counts = Counter(doc.label for doc in docs)
        for label in range(5):
            if counts[label] < min_docs_per_label:
                raise ValueError(
                    f"knowledge-quality: label {label} has {counts[label]} docs, "
                    f"expected at least {min_docs_per_label}"
                )
    if min_body_chars is not None:
        for doc in docs:
            if len(doc.body.strip()) < min_body_chars:
                raise ValueError(f"knowledge-quality: {doc.doc_id} body is shorter than {min_body_chars} chars")
    for doc in docs:
        _validate_knowledge_body_text(doc)
    if min_source_parse_ratio is not None:
        parsed = sum(1 for doc in docs if doc.metadata.get("generation_method") == "source_parse")
        ratio = parsed / max(len(docs), 1)
        if ratio < min_source_parse_ratio:
            raise ValueError(
                f"knowledge-quality: source_parse ratio {ratio:.3f} is below {min_source_parse_ratio:.3f}"
            )


def _is_ambiguous_example(row: ClassificationExample) -> bool:
    sample_type = str(row.metadata.get("sample_type", "")).lower()
    return (
        row.generation_method == "augmented"
        or bool(row.metadata.get("is_ambiguous"))
        or sample_type in {"ambiguous", "adversarial"}
    )


def validate_dataset_quality(
    data_dir: Path,
    *,
    min_cls_rows: int | None = None,
    min_cls_per_label: int | None = None,
    min_ambiguous_per_label: int | None = None,
    min_qa_rows: int | None = None,
    min_qa_per_label: int | None = None,
    no_dry_run: bool = False,
    require_validated: bool = False,
    require_qa_source: bool = False,
) -> None:
    docs = validate_rows(data_dir / "knowledge_seed.json", KnowledgeDoc, required=True)
    cls_rows = validate_rows(data_dir / "cls_train_seed.json", ClassificationExample, required=True)
    audits = validate_rows(data_dir / "label_audit_seed.json", LabelAudit, required=True)
    qa_rows = validate_rows(data_dir / "qa_seed.json", QAExample, required=True)
    docs_by_id = {doc.doc_id: doc for doc in docs}
    for doc in docs:
        _validate_knowledge_body_text(doc)
    _validate_question_label_consistency(cls_rows)
    _validate_audit_consistency(cls_rows, audits)
    if min_cls_rows is not None and len(cls_rows) < min_cls_rows:
        raise ValueError(f"dataset-quality: cls rows {len(cls_rows)} below {min_cls_rows}")
    if min_cls_per_label is not None:
        counts = Counter(row.label for row in cls_rows)
        for label in range(5):
            if counts[label] < min_cls_per_label:
                raise ValueError(f"dataset-quality: cls label {label} has {counts[label]} rows")
    if min_ambiguous_per_label is not None:
        counts = Counter(row.label for row in cls_rows if _is_ambiguous_example(row))
        for label in range(5):
            if counts[label] < min_ambiguous_per_label:
                raise ValueError(f"dataset-quality: ambiguous label {label} has {counts[label]} rows")
    if min_qa_rows is not None and len(qa_rows) < min_qa_rows:
        raise ValueError(f"dataset-quality: qa rows {len(qa_rows)} below {min_qa_rows}")
    if min_qa_per_label is not None:
        counts = Counter(row.label for row in qa_rows)
        for label in range(5):
            if counts[label] < min_qa_per_label:
                raise ValueError(f"dataset-quality: qa label {label} has {counts[label]} rows")
    if no_dry_run and any(row.generation_method == "dry_run" for row in cls_rows):
        raise ValueError("dataset-quality: classification data contains dry_run rows")
    if require_validated:
        if any(not row.validated for row in cls_rows):
            raise ValueError("dataset-quality: classification data contains unvalidated rows")
        if any(not row.validated for row in qa_rows):
            raise ValueError("dataset-quality: QA data contains unvalidated rows")
    if require_qa_source:
        for row in qa_rows:
            has_source_text = "http" in row.model.lower() or "출처" in row.model
            if not row.source_url or not has_source_text:
                raise ValueError(f"dataset-quality: QA row lacks source evidence: {row.user}")
            _validate_qa_answer_text(row, docs_by_id=docs_by_id)


def _normalize_question(text: str) -> str:
    return QUESTION_NORMALIZE_RE.sub(" ", text.strip().lower())


def _validate_qa_answer_text(row: QAExample, *, docs_by_id: dict[str, KnowledgeDoc] | None = None) -> None:
    lowered = row.model.lower()
    for term in BANNED_OUTPUT_TERMS:
        if term.lower() in lowered:
            raise ValueError(f"dataset-quality: QA answer contains banned term {term}: {row.user}")
    for term in QA_BOILERPLATE_TERMS:
        if term.casefold() in row.model.casefold():
            raise ValueError(f"dataset-quality: QA answer contains boilerplate term {term}: {row.user}")
    for phrase in GENERIC_QA_PHRASES:
        if phrase in row.model:
            raise ValueError(f"dataset-quality: QA answer is too generic: {row.user}")
    if _mojibake_score(row.model) >= 3:
        raise ValueError(f"dataset-quality: QA answer appears garbled: {row.user}")
    if _contains_private_use(row.model):
        raise ValueError(f"dataset-quality: QA answer contains private-use glyphs: {row.user}")
    _validate_qa_evidence_span(row, docs_by_id=docs_by_id)


def _validate_knowledge_body_text(doc: KnowledgeDoc) -> None:
    for term in QA_BOILERPLATE_TERMS:
        if term.casefold() in doc.body.casefold():
            raise ValueError(f"knowledge-quality: {doc.doc_id} contains page chrome term {term}")
    if _mojibake_score(doc.body) >= 3:
        raise ValueError(f"knowledge-quality: {doc.doc_id} appears garbled")
    if _contains_private_use(doc.body):
        raise ValueError(f"knowledge-quality: {doc.doc_id} contains private-use glyphs")
    if not _has_label_specific_source_signal(doc.body, doc.label):
        raise ValueError(f"knowledge-quality: {doc.doc_id} lacks source-specific content signal")


def _has_label_specific_source_signal(text: str, label: int) -> bool:
    if label == 1:
        return bool(re.search(r"20\d{2}-\d{2}-\d{2}", text)) and any(
            term in text for term in ("공지", "학사지원과", "작성일", "조회수")
        )
    if label == 2:
        return bool(re.search(r"\d{2}\.\d{2}", text)) and any(
            term in text for term in ("개강", "수강신청", "휴학", "복학", "등록", "계절학기", "성적")
        )
    if label == 3:
        return any(term in text for term in ("조식", "중식", "석식", "메뉴운영내역", "원산지"))
    if label == 4:
        return any(term in text for term in ("운영기준", "운행", "시간표", "평일", "주말", "공휴일", "월평역"))
    return True


def _validate_qa_evidence_span(row: QAExample, *, docs_by_id: dict[str, KnowledgeDoc] | None) -> None:
    excerpts = QA_EVIDENCE_RE.findall(row.model)
    if not excerpts:
        raise ValueError(f"dataset-quality: QA row lacks quoted evidence: {row.user}")
    excerpt = excerpts[0].strip()
    if len(excerpt) < 40:
        raise ValueError(f"dataset-quality: QA quoted evidence is too short: {row.user}")
    if sum(1 for char in excerpt if "가" <= char <= "힣") < 20:
        raise ValueError(f"dataset-quality: QA quoted evidence has low Korean density: {row.user}")
    if not any(keyword in excerpt for keyword in QA_LABEL_KEYWORDS[row.label]):
        raise ValueError(f"dataset-quality: QA quoted evidence lacks label keyword: {row.user}")
    if docs_by_id is None:
        return
    doc = docs_by_id.get(row.source_doc_id)
    if doc is None:
        raise ValueError(f"dataset-quality: QA row references missing source doc: {row.user}")
    if row.source_url != doc.source_url:
        raise ValueError(f"dataset-quality: QA row source URL mismatches source doc: {row.user}")
    token_hits = sum(1 for token in excerpt.split() if len(token) > 1 and token in doc.body)
    if token_hits < 6:
        raise ValueError(f"dataset-quality: QA evidence is not grounded in source body: {row.user}")


def _mojibake_score(text: str) -> int:
    suspicious = "泲湮ȯմϴбտαøũĴ�"
    return sum(text.count(char) for char in suspicious)


def _contains_private_use(text: str) -> bool:
    return any(unicodedata.category(char) == "Co" for char in text)


def _validate_question_label_consistency(rows: list[ClassificationExample]) -> None:
    labels_by_question: dict[str, int] = {}
    for row in rows:
        normalized = _normalize_question(row.question)
        existing = labels_by_question.get(normalized)
        if existing is not None and existing != row.label:
            raise ValueError(
                f"dataset-quality: conflicting labels for question {row.question!r}: {existing} vs {row.label}"
            )
        labels_by_question[normalized] = row.label


def _validate_audit_consistency(rows: list[ClassificationExample], audits: list[LabelAudit]) -> None:
    audit_by_key = {
        (_normalize_question(row.question), row.source_doc_id): row
        for row in audits
    }
    for example in rows:
        key = (_normalize_question(example.question), example.source_doc_id or "")
        audit = audit_by_key.get(key)
        if audit is None:
            raise ValueError(f"dataset-quality: missing audit for question {example.question!r}")
        if audit.final_label != example.label:
            raise ValueError(f"dataset-quality: audit/example label mismatch for {example.question!r}")
        if audit.decision != "accept" and example.validated:
            raise ValueError(f"dataset-quality: validated example has non-accepted audit for {example.question!r}")


def _metric_value(metrics: dict[str, object], names: tuple[str, ...]) -> float:
    for name in names:
        value = metrics.get(name)
        if isinstance(value, int | float):
            return float(value)
    raise ValueError(f"metrics missing one of: {', '.join(names)}")


def validate_classifier_metrics(
    path: Path,
    *,
    input_path: Path | None = None,
    require_source_disjoint: bool = False,
    min_macro_f1: float | None = None,
    min_weighted_f1: float | None = None,
    min_class_f1: float | None = None,
) -> None:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a metrics object")
    if input_path:
        if payload.get("input_checksum") != file_checksum(input_path):
            raise ValueError("classifier-metrics: input_checksum does not match input file")
    if require_source_disjoint:
        if not payload.get("split_strategy"):
            raise ValueError("classifier-metrics: split_strategy is required")
        label_distribution = payload.get("label_distribution")
        if not isinstance(label_distribution, dict) or not label_distribution:
            raise ValueError("classifier-metrics: label_distribution is required")
        if payload.get("evaluation_scope") != "source_disjoint":
            raise ValueError("classifier-metrics: evaluation_scope is not source_disjoint")
        if payload.get("source_overlap_count") != 0:
            raise ValueError("classifier-metrics: source_overlap_count is not 0")
        train_sources = set(payload.get("train_source_ids", []))
        eval_sources = set(payload.get("eval_source_ids", []))
        train_hashes = set(payload.get("train_source_hashes", []))
        eval_hashes = set(payload.get("eval_source_hashes", []))
        has_source_ids = bool(train_sources and eval_sources)
        has_source_hashes = bool(train_hashes and eval_hashes)
        if not has_source_ids and not has_source_hashes:
            raise ValueError("classifier-metrics: train/eval source ids or hashes are required")
        if train_sources & eval_sources:
            raise ValueError("classifier-metrics: train/eval source ids overlap")
        if train_hashes & eval_hashes:
            raise ValueError("classifier-metrics: train/eval source hashes overlap")
    if min_macro_f1 is not None and _metric_value(payload, ("macro_f1",)) < min_macro_f1:
        raise ValueError("classifier-metrics: macro_f1 below threshold")
    if min_weighted_f1 is not None and _metric_value(payload, ("weighted_f1",)) < min_weighted_f1:
        raise ValueError("classifier-metrics: weighted_f1 below threshold")
    if min_class_f1 is not None:
        report = payload.get("report")
        if not isinstance(report, dict):
            raise ValueError("classifier-metrics: report object is required")
        for label in range(5):
            label_report = report.get(str(label))
            if not isinstance(label_report, dict):
                raise ValueError(f"classifier-metrics: missing report for class {label}")
            f1 = label_report.get("f1-score")
            if not isinstance(f1, int | float) or float(f1) < min_class_f1:
                raise ValueError(f"classifier-metrics: class {label} f1 below threshold")


def validate_retrieval_metrics(
    path: Path,
    *,
    knowledge_path: Path | None = None,
    qa_path: Path | None = None,
    min_top1_label_accuracy: float | None = None,
    min_top3_source_hit_rate: float | None = None,
) -> None:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a metrics object")
    if knowledge_path is None or qa_path is None:
        raise ValueError("retrieval-metrics: --knowledge and --qa are required")
    if payload.get("knowledge_checksum") != file_checksum(knowledge_path):
        raise ValueError("retrieval-metrics: knowledge_checksum does not match knowledge file")
    if payload.get("qa_checksum") != file_checksum(qa_path):
        raise ValueError("retrieval-metrics: qa_checksum does not match QA file")
    if min_top1_label_accuracy is not None:
        value = _metric_value(payload, ("top1_label_accuracy", "top_1_label_accuracy"))
        if value < min_top1_label_accuracy:
            raise ValueError("retrieval-metrics: top1 label accuracy below threshold")
    if min_top3_source_hit_rate is not None:
        value = _metric_value(payload, ("top3_source_hit_rate", "top_3_source_hit_rate"))
        if value < min_top3_source_hit_rate:
            raise ValueError("retrieval-metrics: top3 source hit rate below threshold")
    failure_counts = payload.get("per_label_failure_counts")
    if not isinstance(failure_counts, dict):
        raise ValueError("retrieval-metrics: per_label_failure_counts is required")
    expected_labels = {str(label) for label in range(5)}
    if set(failure_counts) != expected_labels:
        raise ValueError("retrieval-metrics: per_label_failure_counts must cover labels 0-4")
    for label, count in failure_counts.items():
        if not isinstance(count, int) or count < 0:
            raise ValueError(f"retrieval-metrics: failure count for label {label} must be a non-negative integer")
    row_count = payload.get("row_count")
    if isinstance(row_count, int) and sum(failure_counts.values()) > row_count:
        raise ValueError("retrieval-metrics: failure counts exceed row_count")


def validate_chat_quality(
    output_path: Path,
    *,
    input_path: Path | None = None,
    min_answer_chars: int | None = None,
    require_source_hint: bool = False,
) -> None:
    rows = validate_rows(output_path, ChatOutput, required=True)
    if input_path:
        inputs = validate_rows(input_path, ChatInput, required=True)
        if len(rows) != len(inputs):
            raise ValueError(f"chat-quality: output rows {len(rows)} do not match input rows {len(inputs)}")
    for row in rows:
        answer = row.model.strip()
        if min_answer_chars is not None and len(answer) < min_answer_chars:
            raise ValueError(f"chat-quality: answer shorter than {min_answer_chars} chars for {row.user}")
        if require_source_hint and not ("http" in answer.lower() or "출처" in answer or "source" in answer.lower()):
            raise ValueError(f"chat-quality: answer lacks source hint for {row.user}")


def validate_runtime_knowledge_consistency(knowledge_path: Path) -> None:
    from nlp_term.chat import batch, composer
    from nlp_term.retrieve.knowledge import load_knowledge_with_metadata
    from nlp_term.ui import app

    file_docs = validate_rows(knowledge_path, KnowledgeDoc, required=True)
    runtime_load = load_knowledge_with_metadata(knowledge_path)
    runtime_docs = runtime_load.docs
    if runtime_load.fallback_used:
        raise ValueError("runtime-knowledge-consistency: fallback knowledge was used")
    file_ids = [doc.doc_id for doc in file_docs]
    runtime_ids = [doc.doc_id for doc in runtime_docs]
    if file_ids != runtime_ids:
        raise ValueError("runtime-knowledge-consistency: runtime loader differs from knowledge file")
    file_count = len(file_docs)
    if len(runtime_docs) != file_count:
        raise ValueError("runtime-knowledge-consistency: runtime doc count differs from knowledge file")
    compose_signature = inspect.signature(composer.compose_answer)
    batch_signature = inspect.signature(batch.run_chat_file)
    answer_signature = inspect.signature(app.answer)
    if "knowledge_path" not in compose_signature.parameters:
        raise ValueError("runtime-knowledge-consistency: composer does not accept knowledge_path")
    if "knowledge_path" not in batch_signature.parameters:
        raise ValueError("runtime-knowledge-consistency: batch runner does not accept knowledge_path")
    if "knowledge_path" not in answer_signature.parameters:
        raise ValueError("runtime-knowledge-consistency: UI answer does not accept knowledge_path")


def validate_all(data_dir: Path, outputs_dir: Path, *, require_outputs: bool, require_realtime: bool) -> None:
    validate_inputs(data_dir, require_realtime=require_realtime)
    if require_outputs:
        validate_outputs(outputs_dir, require_realtime=require_realtime)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate NLP term project JSON contracts.")
    parser.add_argument("--check-all", action="store_true", help="Validate known input/output files.")
    parser.add_argument("--inputs-only", action="store_true", help="Only validate required input fixtures.")
    parser.add_argument("--seed-data", action="store_true", help="Validate generated seed datasets.")
    parser.add_argument("--source-probe", type=Path, help="Validate source probe metadata.")
    parser.add_argument("--knowledge-provenance", type=Path, help="Validate knowledge docs against source probe metadata.")
    parser.add_argument("--require-official-chain", action="store_true", help="Require provenance sources to be official-chain verified.")
    parser.add_argument("--model-shortlist", type=Path, help="Validate model shortlist metadata.")
    parser.add_argument("--knowledge-quality", type=Path, help="Validate source-backed knowledge quality gates.")
    parser.add_argument("--dataset-quality", action="store_true", help="Validate generated classification/QA quality gates.")
    parser.add_argument("--classifier-metrics", type=Path, help="Validate classifier metric gates.")
    parser.add_argument("--retrieval-metrics", type=Path, help="Validate retrieval metric gates.")
    parser.add_argument("--chat-quality", type=Path, help="Validate chat output quality gates.")
    parser.add_argument("--realtime-provenance", type=Path, help="Validate realtime output against source provenance.")
    parser.add_argument("--runtime-knowledge-consistency", action="store_true", help="Validate runtime knowledge loader consistency.")
    parser.add_argument("--final-readiness", action="store_true", help="Reject placeholder terms in final-facing outputs.")
    parser.add_argument("--require-raw-files", action="store_true", help="Require source probe raw files to exist.")
    parser.add_argument("--require-realtime", action="store_true", help="Require realtime input/output files.")
    parser.add_argument("--input", type=Path, help="Input artifact used by a metric or output validator.")
    parser.add_argument("--knowledge", type=Path, help="Knowledge artifact used by runtime or retrieval validators.")
    parser.add_argument("--qa", type=Path, help="QA artifact used by retrieval validators.")
    parser.add_argument("--min-docs-per-label", type=int)
    parser.add_argument("--min-body-chars", type=int)
    parser.add_argument("--min-source-parse-ratio", type=float)
    parser.add_argument("--min-cls-rows", type=int)
    parser.add_argument("--min-cls-per-label", type=int)
    parser.add_argument("--min-ambiguous-per-label", type=int)
    parser.add_argument("--min-qa-rows", type=int)
    parser.add_argument("--min-qa-per-label", type=int)
    parser.add_argument("--no-dry-run", action="store_true")
    parser.add_argument("--require-validated", action="store_true")
    parser.add_argument("--require-qa-source", action="store_true")
    parser.add_argument("--require-source-disjoint", action="store_true")
    parser.add_argument("--min-macro-f1", type=float)
    parser.add_argument("--min-weighted-f1", type=float)
    parser.add_argument("--min-class-f1", type=float)
    parser.add_argument("--min-top1-label-accuracy", type=float)
    parser.add_argument("--min-top3-source-hit-rate", type=float)
    parser.add_argument("--min-answer-chars", type=int)
    parser.add_argument("--require-source-hint", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--outputs-dir", type=Path, default=Path("outputs"))
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if (
        not args.check_all
        and not args.inputs_only
        and not args.seed_data
        and not args.source_probe
        and not args.knowledge_provenance
        and not args.model_shortlist
        and not args.knowledge_quality
        and not args.dataset_quality
        and not args.classifier_metrics
        and not args.retrieval_metrics
        and not args.chat_quality
        and not args.realtime_provenance
        and not args.runtime_knowledge_consistency
        and not args.final_readiness
    ):
        parser.error("at least one validation mode is required")
    try:
        if args.inputs_only:
            validate_inputs(args.data_dir, require_realtime=args.require_realtime)
        if args.check_all:
            validate_all(
                args.data_dir,
                args.outputs_dir,
                require_outputs=True,
                require_realtime=args.require_realtime,
            )
        if args.seed_data:
            validate_seed_data(args.data_dir)
        if args.source_probe:
            validate_source_probe(args.source_probe, require_raw_files=args.require_raw_files)
        if args.knowledge_provenance:
            validate_knowledge_provenance(
                args.data_dir,
                args.knowledge_provenance,
                require_official_chain=args.require_official_chain,
            )
        if args.model_shortlist:
            validate_model_shortlist(args.model_shortlist)
        if args.knowledge_quality:
            validate_knowledge_quality(
                args.knowledge_quality,
                source_probe_path=args.source_probe,
                min_docs_per_label=args.min_docs_per_label,
                min_body_chars=args.min_body_chars,
                min_source_parse_ratio=args.min_source_parse_ratio,
            )
        if args.dataset_quality:
            validate_dataset_quality(
                args.data_dir,
                min_cls_rows=args.min_cls_rows,
                min_cls_per_label=args.min_cls_per_label,
                min_ambiguous_per_label=args.min_ambiguous_per_label,
                min_qa_rows=args.min_qa_rows,
                min_qa_per_label=args.min_qa_per_label,
                no_dry_run=args.no_dry_run,
                require_validated=args.require_validated,
                require_qa_source=args.require_qa_source,
            )
        if args.classifier_metrics:
            validate_classifier_metrics(
                args.classifier_metrics,
                input_path=args.input,
                require_source_disjoint=args.require_source_disjoint,
                min_macro_f1=args.min_macro_f1,
                min_weighted_f1=args.min_weighted_f1,
                min_class_f1=args.min_class_f1,
            )
        if args.retrieval_metrics:
            validate_retrieval_metrics(
                args.retrieval_metrics,
                knowledge_path=args.knowledge,
                qa_path=args.qa,
                min_top1_label_accuracy=args.min_top1_label_accuracy,
                min_top3_source_hit_rate=args.min_top3_source_hit_rate,
            )
        if args.chat_quality:
            validate_chat_quality(
                args.chat_quality,
                input_path=args.input,
                min_answer_chars=args.min_answer_chars,
                require_source_hint=args.require_source_hint,
            )
        if args.realtime_provenance:
            validate_realtime_provenance(args.realtime_provenance, source_probe_path=args.source_probe)
        if args.runtime_knowledge_consistency:
            if args.knowledge is None:
                raise ValueError("--runtime-knowledge-consistency requires --knowledge")
            validate_runtime_knowledge_consistency(args.knowledge)
        if args.final_readiness:
            validate_final_readiness(args.outputs_dir)
    except (FileNotFoundError, ValueError, ValidationError) as exc:
        raise SystemExit(f"validation failed: {exc}") from exc
    print("validation-ok")


if __name__ == "__main__":
    main()
