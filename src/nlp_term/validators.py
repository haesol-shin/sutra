from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import inspect
import json
from pathlib import Path
import re
from urllib.parse import urlparse
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
    Task1HumanGoldExample,
    Task2AnswerEvalGoldExample,
    Task2FactGoldExample,
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
QUESTION_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
GENERIC_TITLE_TOKENS = {
    "chunk",
    "source",
    "공지",
    "안내",
    "자료",
    "학사",
    "충남대학교",
    "cnu",
}
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
GOLD_LEAKAGE_RE = re.compile(
    r"(chunk[_\s-]*\d+|doc[_\s-]*\d+|source\s+\d+|source[_-]\d+)",
    re.IGNORECASE,
)
METRIC_DATASET_ORIGINS = {"seed", "llm_assisted_train", "synthetic", "human_gold", "task2_gold"}
METRIC_CLAIM_LEVELS = {"sanity", "training_selection", "heldout_eval", "qualitative_check"}


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


def validate_source_probe(
    path: Path,
    *,
    require_raw_files: bool = False,
    require_official_chain_evidence: bool = False,
) -> None:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError(f"{path} rows must be objects")
        raw = RawSource.model_validate(row.get("raw"))
        verification = SourceVerification.model_validate(row.get("verification"))
        if require_official_chain_evidence and verification.official_chain_ok:
            if raw.url not in verification.evidence:
                raise ValueError(f"{raw.source_id} official-chain evidence does not include source URL")
            hostname = urlparse(raw.url).hostname or ""
            if not (hostname == "cnu.ac.kr" or hostname.endswith(".cnu.ac.kr")):
                raise ValueError(f"{raw.source_id} official-chain source URL is not under cnu.ac.kr")
        raw_path = Path(raw.raw_path)
        if require_raw_files:
            if not raw_path.exists():
                raise FileNotFoundError(raw.raw_path)
            if raw.status_code is None or not 200 <= raw.status_code < 300:
                raise ValueError(f"{raw.source_id} has non-2xx status: {raw.status_code}")
            checksum = sha256(raw_path.read_bytes()).hexdigest()
            if checksum != raw.checksum:
                raise ValueError(f"{raw.source_id} checksum does not match raw file")


def validate_source_inventory(
    *,
    min_stage1_candidates: int | None = None,
    min_stage2_candidates: int | None = None,
    require_stage_candidate_labels: bool = False,
) -> None:
    from nlp_term.collect.source_inventory import iter_specs

    specs = iter_specs(stage="all", active_only=False)
    rows_by_stage = {
        "stage1": [spec for spec in specs if spec.stage == "stage1" and not spec.active],
        "stage2": [spec for spec in specs if spec.stage == "stage2" and not spec.active],
    }
    thresholds = {"stage1": min_stage1_candidates, "stage2": min_stage2_candidates}
    for stage, threshold in thresholds.items():
        rows = rows_by_stage[stage]
        if threshold is not None and len(rows) < threshold:
            raise ValueError(f"source-inventory: {stage} inactive candidates {len(rows)} below {threshold}")
        if require_stage_candidate_labels:
            labels = {spec.label for spec in rows}
            if labels != {0, 1, 2, 3, 4}:
                raise ValueError(f"source-inventory: {stage} candidate labels {sorted(labels)} do not cover 0-4")
    for spec in specs:
        if not spec.active and spec.official_chain_ok:
            raise ValueError(f"source-inventory: inactive candidate {spec.source_id} must not be official-chain true")


def validate_source_stage_coverage(
    path: Path,
    *,
    stage: str,
    min_stage_sources: int | None = None,
    max_stage_sources: int | None = None,
    require_stage_labels: bool = False,
    require_graduation_departments: int | None = None,
) -> None:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    rows = []
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError(f"{path} rows must be objects")
        raw = RawSource.model_validate(row.get("raw"))
        inventory = row.get("inventory")
        if not isinstance(inventory, dict):
            raise ValueError(f"source-stage: {raw.source_id} lacks inventory metadata")
        if inventory.get("stage") == stage and inventory.get("active", True):
            rows.append((raw, inventory))
    if min_stage_sources is not None and len(rows) < min_stage_sources:
        raise ValueError(f"source-stage: {stage} has {len(rows)} sources below {min_stage_sources}")
    if max_stage_sources is not None and len(rows) > max_stage_sources:
        raise ValueError(f"source-stage: {stage} has {len(rows)} sources above {max_stage_sources}")
    if require_stage_labels:
        labels = {raw.label for raw, _ in rows}
        if labels != {0, 1, 2, 3, 4}:
            raise ValueError(f"source-stage: {stage} labels {sorted(labels)} do not cover 0-4")
    if require_graduation_departments is not None:
        departments = {
            str(inventory.get("department"))
            for raw, inventory in rows
            if raw.label == 0 and inventory.get("department")
        }
        if len(departments) < require_graduation_departments:
            raise ValueError(
                f"source-stage: {stage} graduation departments {len(departments)} below "
                f"{require_graduation_departments}"
            )
        if not any(raw.source_id == "graduation_curriculum_pdf" for raw, _ in rows):
            raise ValueError(f"source-stage: {stage} lacks central graduation curriculum PDF")


def validate_knowledge_provenance(
    data_dir: Path,
    source_probe_path: Path,
    *,
    require_official_chain: bool = False,
    require_raw_provenance: bool = False,
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
        if require_raw_provenance:
            expected = {
                "raw_path": raw.raw_path,
                "raw_checksum": raw.checksum,
                "raw_fetched_at": raw.fetched_at,
                "raw_status_code": raw.status_code,
                "raw_content_type": raw.content_type,
                "verification_official_chain_ok": verification.official_chain_ok,
                "verification_parser_name": verification.parser_name,
                "verification_parser_version": verification.parser_version,
                "verification_verified_at": verification.verified_at,
            }
            for key, value in expected.items():
                if doc.metadata.get(key) != value:
                    raise ValueError(f"{doc.doc_id} metadata {key} does not match source probe")


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
    if source_probe_path is not None:
        payload = read_json(source_probe_path)
        if not isinstance(payload, list):
            raise ValueError(f"{source_probe_path} must contain a JSON list")
        for row in payload:
            SourceVerification.model_validate(row.get("verification"))
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
    min_total_docs: int | None = None,
) -> None:
    docs = validate_rows(path, KnowledgeDoc, required=True)
    if min_total_docs is not None and len(docs) < min_total_docs:
        raise ValueError(f"knowledge-quality: total docs {len(docs)} below {min_total_docs}")
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


def validate_tier1_coverage(
    *,
    data_dir: Path,
    source_probe_path: Path,
    min_index_eligible_sources: int | None = None,
    min_raw_sources: int | None = None,
    min_accepted_docs: int | None = None,
    min_structured_rows: int | None = None,
    min_index_chunk_candidates: int | None = None,
    min_graduation_docs: int | None = None,
    min_graduation_rows: int | None = None,
    min_notice_docs: int | None = None,
    max_notice_docs: int | None = None,
    max_notice_doc_ratio: float | None = None,
    max_notice_duplicate_ratio: float | None = None,
    max_source_concentration: float | None = None,
    min_calendar_rows: int | None = None,
    min_dining_rows: int | None = None,
    min_shuttle_rows: int | None = None,
) -> None:
    probe_payload = read_json(source_probe_path)
    if not isinstance(probe_payload, list):
        raise ValueError(f"{source_probe_path} must contain a JSON list")

    raw_sources = []
    index_eligible_sources = set()
    for row in probe_payload:
        if not isinstance(row, dict):
            raise ValueError(f"{source_probe_path} rows must be objects")
        raw = RawSource.model_validate(row.get("raw"))
        verification = SourceVerification.model_validate(row.get("verification"))
        inventory = row.get("inventory")
        if not isinstance(inventory, dict):
            raise ValueError(f"tier1-coverage: {raw.source_id} lacks inventory metadata")
        raw_sources.append(raw)
        is_active = bool(inventory.get("active", True))
        source_is_allowed = bool(inventory.get("index_eligible", True))
        freshness_policy = str(inventory.get("freshness_policy", ""))
        if is_active and source_is_allowed and (verification.official_chain_ok or freshness_policy == "short_ttl"):
            index_eligible_sources.add(raw.source_id)

    docs = validate_rows(data_dir / "knowledge_seed.json", KnowledgeDoc, required=True)
    accepted_docs = [doc for doc in docs if bool(doc.metadata.get("index_eligible", True))]
    structured_docs = [
        doc for doc in accepted_docs if doc.metadata.get("generation_method") == "structured_row"
    ]
    row_type_counts = Counter(str(doc.metadata.get("row_type", "")) for doc in structured_docs)
    domain_counts = Counter(doc.domain for doc in accepted_docs)
    source_counts = Counter(doc.source_id for doc in accepted_docs)

    _require_min("tier1-coverage: index-eligible sources", len(index_eligible_sources), min_index_eligible_sources)
    _require_min("tier1-coverage: raw sources", len(raw_sources), min_raw_sources)
    _require_min("tier1-coverage: accepted docs", len(accepted_docs), min_accepted_docs)
    _require_min("tier1-coverage: structured rows", len(structured_docs), min_structured_rows)
    _require_min("tier1-coverage: index chunk candidates", len(accepted_docs), min_index_chunk_candidates)
    _require_min("tier1-coverage: graduation docs", domain_counts["graduation"], min_graduation_docs)
    _require_min("tier1-coverage: graduation rows", row_type_counts["graduation_requirement"], min_graduation_rows)
    _require_min("tier1-coverage: notice docs", domain_counts["notices"], min_notice_docs)
    if max_notice_docs is not None and domain_counts["notices"] > max_notice_docs:
        raise ValueError(f"tier1-coverage: notice docs {domain_counts['notices']} above {max_notice_docs}")
    if max_notice_doc_ratio is not None:
        ratio = domain_counts["notices"] / max(len(accepted_docs), 1)
        if ratio > max_notice_doc_ratio:
            raise ValueError(
                f"tier1-coverage: notice doc ratio {ratio:.3f} above {max_notice_doc_ratio:.3f}"
            )
    if max_notice_duplicate_ratio is not None:
        duplicate_ratio = _notice_duplicate_ratio(accepted_docs)
        if duplicate_ratio > max_notice_duplicate_ratio:
            raise ValueError(
                f"tier1-coverage: notice duplicate ratio {duplicate_ratio:.3f} "
                f"above {max_notice_duplicate_ratio:.3f}"
            )
    if max_source_concentration is not None:
        source_concentration = max(source_counts.values(), default=0) / max(len(accepted_docs), 1)
        if source_concentration > max_source_concentration:
            raise ValueError(
                f"tier1-coverage: source concentration {source_concentration:.3f} "
                f"above {max_source_concentration:.3f}"
            )
    _require_min("tier1-coverage: calendar rows", row_type_counts["academic_calendar_event"], min_calendar_rows)
    _require_min("tier1-coverage: dining rows", row_type_counts["dining_menu"], min_dining_rows)
    shuttle_rows = row_type_counts["shuttle_route"] + row_type_counts["shuttle_segment"]
    _require_min("tier1-coverage: shuttle rows", shuttle_rows, min_shuttle_rows)


def _require_min(label: str, actual: int, expected: int | None) -> None:
    if expected is not None and actual < expected:
        raise ValueError(f"{label} {actual} below {expected}")


def _notice_duplicate_ratio(docs: list[KnowledgeDoc]) -> float:
    notice_docs = [doc for doc in docs if doc.domain == "notices"]
    if not notice_docs:
        return 0.0
    keys = []
    for doc in notice_docs:
        metadata = doc.metadata
        keys.append(
            (
                str(metadata.get("detail_url") or doc.source_url),
                str(metadata.get("posted_date") or doc.date or ""),
                doc.title.strip(),
            )
        )
    duplicate_count = len(keys) - len(set(keys))
    return duplicate_count / len(notice_docs)


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


def validate_gold_data(
    gold_dir: Path,
    *,
    min_task1_rows: int | None = None,
    min_task1_per_label: int | None = None,
    min_task2_facts_per_label: int | None = None,
    min_task2_answer_rows: int | None = None,
) -> None:
    task1_rows = validate_rows(gold_dir / "task1_human_gold.json", Task1HumanGoldExample, required=True)
    fact_rows = validate_rows(gold_dir / "task2_fact_gold.json", Task2FactGoldExample, required=True)
    answer_rows = validate_rows(
        gold_dir / "task2_answer_eval_gold.json",
        Task2AnswerEvalGoldExample,
        required=True,
    )
    _validate_task1_gold_rows(task1_rows, min_rows=min_task1_rows, min_per_label=min_task1_per_label)
    _validate_task2_fact_gold_rows(fact_rows, min_per_label=min_task2_facts_per_label)
    _validate_task2_answer_gold_rows(answer_rows, fact_rows, min_rows=min_task2_answer_rows)


def _validate_task1_gold_rows(
    rows: list[Task1HumanGoldExample],
    *,
    min_rows: int | None,
    min_per_label: int | None,
) -> None:
    if min_rows is not None and len(rows) < min_rows:
        raise ValueError("gold-data: task1 human gold row count below threshold")
    seen_questions: set[str] = set()
    counts = Counter(row.label for row in rows)
    for row in rows:
        if not row.validated:
            raise ValueError(f"gold-data: task1 human gold row is unvalidated: {row.question}")
        if row.annotator != "human":
            raise ValueError(f"gold-data: task1 gold row annotator is not human: {row.question}")
        _reject_gold_leakage("task1", row.question)
        normalized = _normalize_question(row.question)
        if normalized in seen_questions:
            raise ValueError(f"gold-data: duplicate task1 gold question: {row.question}")
        seen_questions.add(normalized)
    if min_per_label is not None:
        for label in range(5):
            if counts[label] < min_per_label:
                raise ValueError(f"gold-data: task1 label {label} rows below threshold")


def _validate_task2_fact_gold_rows(
    rows: list[Task2FactGoldExample],
    *,
    min_per_label: int | None,
) -> None:
    counts = Counter(row.label for row in rows)
    fact_ids: set[str] = set()
    for row in rows:
        if row.fact_id in fact_ids:
            raise ValueError(f"gold-data: duplicate task2 fact id: {row.fact_id}")
        fact_ids.add(row.fact_id)
        if not row.source_url.startswith(("http://", "https://")):
            raise ValueError(f"gold-data: task2 fact source URL is invalid: {row.fact_id}")
        if len(row.claim.strip()) < 4:
            raise ValueError(f"gold-data: task2 fact claim is too short: {row.fact_id}")
        if len(row.evidence_quote.strip()) < 8:
            raise ValueError(f"gold-data: task2 evidence quote is too short: {row.fact_id}")
        _reject_gold_leakage("task2 fact claim", row.claim)
        _reject_gold_leakage("task2 fact evidence", row.evidence_quote)
    if min_per_label is not None:
        for label in range(5):
            if counts[label] < min_per_label:
                raise ValueError(f"gold-data: task2 fact label {label} rows below threshold")


def _validate_task2_answer_gold_rows(
    rows: list[Task2AnswerEvalGoldExample],
    fact_rows: list[Task2FactGoldExample],
    *,
    min_rows: int | None,
) -> None:
    if min_rows is not None and len(rows) < min_rows:
        raise ValueError("gold-data: task2 answer eval row count below threshold")
    fact_ids = {row.fact_id for row in fact_rows}
    seen_users: set[str] = set()
    for row in rows:
        _reject_gold_leakage("task2 answer prompt", row.user)
        normalized = _normalize_question(row.user)
        if normalized in seen_users:
            raise ValueError(f"gold-data: duplicate task2 answer prompt: {row.user}")
        seen_users.add(normalized)
        missing = [fact_id for fact_id in row.expected_fact_ids if fact_id not in fact_ids]
        if missing:
            raise ValueError(f"gold-data: task2 answer row references missing facts: {missing}")


def _reject_gold_leakage(scope: str, text: str) -> None:
    if GOLD_LEAKAGE_RE.search(text):
        raise ValueError(f"gold-data: {scope} contains leakage marker")


def validate_metric_claim(
    path: Path,
    *,
    input_path: Path | None = None,
    require_dataset_origin: str | None = None,
    require_claim_level: str | None = None,
) -> None:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a metrics object")
    for field in ("evaluation_set_type", "dataset_origin", "claim_level", "input_path", "input_checksum"):
        if field not in payload:
            raise ValueError(f"metric-claim: {field} is required")
    dataset_origin = payload["dataset_origin"]
    claim_level = payload["claim_level"]
    if dataset_origin not in METRIC_DATASET_ORIGINS:
        raise ValueError("metric-claim: unknown dataset_origin")
    if claim_level not in METRIC_CLAIM_LEVELS:
        raise ValueError("metric-claim: unknown claim_level")
    if input_path is not None and payload.get("input_checksum") != file_checksum(input_path):
        raise ValueError("metric-claim: input_checksum does not match input file")
    if require_dataset_origin is not None and dataset_origin != require_dataset_origin:
        raise ValueError("metric-claim: dataset_origin does not match required origin")
    if require_claim_level is not None and claim_level != require_claim_level:
        raise ValueError("metric-claim: claim_level does not match required level")
    if dataset_origin == "seed" and claim_level == "heldout_eval":
        raise ValueError("metric-claim: seed metrics cannot claim heldout evaluation")
    if claim_level == "heldout_eval" and dataset_origin not in {"human_gold", "task2_gold"}:
        raise ValueError("metric-claim: heldout evaluation requires a gold dataset origin")


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


def _title_tokens(title: str) -> set[str]:
    tokens = set()
    for token in QUESTION_TOKEN_RE.findall(title.casefold()):
        if len(token) < 3 or token in GENERIC_TITLE_TOKENS:
            continue
        tokens.add(token)
    return tokens


def build_task1_hard_gate_report(data_dir: Path) -> dict[str, object]:
    docs = validate_rows(data_dir / "knowledge_seed.json", KnowledgeDoc, required=True)
    rows = validate_rows(data_dir / "cls_train_seed.json", ClassificationExample, required=True)
    docs_by_id = {doc.doc_id: doc for doc in docs}
    normalized_rows: dict[str, list[ClassificationExample]] = defaultdict(list)
    label_source_counts: dict[int, Counter[str]] = defaultdict(Counter)
    missing_source_rows: list[str] = []
    source_label_mismatch_rows: list[dict[str, object]] = []
    title_cue_rows: list[dict[str, object]] = []
    for row in rows:
        normalized_rows[_normalize_question(row.question)].append(row)
        if not row.source_doc_id:
            missing_source_rows.append(row.question)
            continue
        doc = docs_by_id.get(row.source_doc_id)
        if doc is None:
            missing_source_rows.append(row.question)
            continue
        if doc.label != row.label:
            source_label_mismatch_rows.append(
                {
                    "question": row.question,
                    "row_label": row.label,
                    "source_doc_id": row.source_doc_id,
                    "source_doc_label": doc.label,
                }
            )
            continue
        label_source_counts[row.label][row.source_doc_id] += 1
        question = row.question.casefold()
        cue_hits = sorted(token for token in _title_tokens(doc.title) if token in question)
        if cue_hits:
            title_cue_rows.append(
                {
                    "question": row.question,
                    "label": row.label,
                    "source_doc_id": row.source_doc_id,
                    "cue_tokens": cue_hits,
                }
            )
    duplicate_groups = {
        question: group
        for question, group in normalized_rows.items()
        if len(group) > 1
    }
    conflicting_duplicate_groups = {
        question: group
        for question, group in duplicate_groups.items()
        if len({row.label for row in group}) > 1
    }
    cross_source_duplicate_groups = {
        question: group
        for question, group in duplicate_groups.items()
        if len({row.source_doc_id for row in group}) > 1
    }
    source_docs_per_label = {
        str(label): len(label_source_counts.get(label, {}))
        for label in range(5)
    }
    source_concentration_by_label: dict[str, float] = {}
    for label in range(5):
        counts = label_source_counts.get(label, Counter())
        total = sum(counts.values())
        source_concentration_by_label[str(label)] = max(counts.values(), default=0) / max(total, 1)
    return {
        "evaluation_scope": "task1_generated_data_hard_gates",
        "input_path": str(data_dir / "cls_train_seed.json"),
        "input_checksum": file_checksum(data_dir / "cls_train_seed.json"),
        "row_count": len(rows),
        "label_distribution": dict(sorted(Counter(row.label for row in rows).items())),
        "normalized_unique_questions": len(normalized_rows),
        "normalized_duplicate_count": sum(len(group) - 1 for group in duplicate_groups.values()),
        "conflicting_duplicate_count": len(conflicting_duplicate_groups),
        "cross_source_duplicate_count": len(cross_source_duplicate_groups),
        "missing_source_doc_count": len(missing_source_rows),
        "missing_source_doc_examples": missing_source_rows[:10],
        "source_label_mismatch_count": len(source_label_mismatch_rows),
        "source_label_mismatch_examples": source_label_mismatch_rows[:10],
        "source_docs_per_label": source_docs_per_label,
        "source_concentration_by_label": source_concentration_by_label,
        "title_cue_row_count": len(title_cue_rows),
        "title_cue_ratio": len(title_cue_rows) / max(len(rows), 1),
        "title_cue_examples": title_cue_rows[:10],
    }


def validate_task1_hard_gates(
    data_dir: Path,
    *,
    report_output: Path | None = None,
    require_cls_source_docs: bool = False,
    max_normalized_duplicate_count: int | None = None,
    max_conflicting_duplicate_count: int | None = None,
    max_title_cue_ratio: float | None = None,
    min_source_docs_per_label: int | None = None,
    max_source_concentration_ratio: float | None = None,
) -> None:
    report = build_task1_hard_gate_report(data_dir)
    if report_output is not None:
        report_output.parent.mkdir(parents=True, exist_ok=True)
        with report_output.open("w", encoding="utf-8") as file:
            json.dump(report, file, ensure_ascii=False, indent=2)
            file.write("\n")
    if require_cls_source_docs and report["missing_source_doc_count"]:
        raise ValueError("task1-hard-gates: classification rows have missing or unknown source_doc_id")
    if require_cls_source_docs and report["source_label_mismatch_count"]:
        raise ValueError("task1-hard-gates: classification rows have mismatched source labels")
    if (
        max_conflicting_duplicate_count is not None
        and int(report["conflicting_duplicate_count"]) > max_conflicting_duplicate_count
    ):
        raise ValueError("task1-hard-gates: conflicting duplicate count above threshold")
    if (
        max_normalized_duplicate_count is not None
        and int(report["normalized_duplicate_count"]) > max_normalized_duplicate_count
    ):
        raise ValueError("task1-hard-gates: normalized duplicate count above threshold")
    if max_title_cue_ratio is not None and float(report["title_cue_ratio"]) > max_title_cue_ratio:
        raise ValueError("task1-hard-gates: source title cue ratio above threshold")
    if min_source_docs_per_label is not None:
        source_docs = report["source_docs_per_label"]
        if not isinstance(source_docs, dict):
            raise ValueError("task1-hard-gates: source_docs_per_label report is malformed")
        for label in range(5):
            count = source_docs.get(str(label))
            if not isinstance(count, int) or count < min_source_docs_per_label:
                raise ValueError(f"task1-hard-gates: label {label} source docs below threshold")
    if max_source_concentration_ratio is not None:
        concentration = report["source_concentration_by_label"]
        if not isinstance(concentration, dict):
            raise ValueError("task1-hard-gates: source_concentration_by_label report is malformed")
        for label, ratio in concentration.items():
            if not isinstance(ratio, int | float) or float(ratio) > max_source_concentration_ratio:
                raise ValueError(f"task1-hard-gates: label {label} source concentration above threshold")


def validate_retrieval_metrics(
    path: Path,
    *,
    knowledge_path: Path | None = None,
    qa_path: Path | None = None,
    min_top1_label_accuracy: float | None = None,
    min_top3_source_hit_rate: float | None = None,
    min_top3_doc_id_hit_rate: float | None = None,
    min_per_label_top1_label_accuracy: float | None = None,
    min_per_label_top3_source_hit_rate: float | None = None,
    min_per_label_top3_doc_id_hit_rate: float | None = None,
    min_graduation_top3_source_hit_rate: float | None = None,
    min_graduation_top3_doc_id_hit_rate: float | None = None,
    min_graduation_curriculum_pdf_hit_rate: float | None = None,
    min_retrieved_evidence_alignment_rate: float | None = None,
    max_alignment_failures: int | None = None,
    require_metadata_aware: bool = False,
    require_diagnostics: bool = False,
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
    if require_metadata_aware:
        if payload.get("retrieval_strategy") != "lexical_metadata_label_hint":
            raise ValueError("retrieval-metrics: metadata-aware retrieval strategy is required")
        fields = payload.get("metadata_fields")
        if not isinstance(fields, list) or not {"source_id", "source_stage", "source_parser_type"} <= set(fields):
            raise ValueError("retrieval-metrics: required metadata fields are missing")
    if min_top1_label_accuracy is not None:
        value = _metric_value(payload, ("top1_label_accuracy", "top_1_label_accuracy"))
        if value < min_top1_label_accuracy:
            raise ValueError("retrieval-metrics: top1 label accuracy below threshold")
    if min_top3_source_hit_rate is not None:
        value = _metric_value(payload, ("top3_source_hit_rate", "top_3_source_hit_rate"))
        if value < min_top3_source_hit_rate:
            raise ValueError("retrieval-metrics: top3 source hit rate below threshold")
    if require_diagnostics:
        for field in (
            "per_label_row_counts",
            "top3_doc_id_hit_rate",
            "per_label_top1_label_accuracy",
            "per_label_top3_source_hit_rate",
            "per_label_top3_doc_id_hit_rate",
            "graduation_top3_source_hit_rate",
            "graduation_top3_doc_id_hit_rate",
            "graduation_curriculum_pdf_hit_rate",
            "retrieved_evidence_alignment_rate",
            "expected_evidence_alignment_rate",
            "alignment_failures",
        ):
            if field not in payload:
                raise ValueError(f"retrieval-metrics: {field} is required")
    if min_per_label_top1_label_accuracy is not None:
        _validate_per_label_rate(
            payload,
            "per_label_top1_label_accuracy",
            min_per_label_top1_label_accuracy,
        )
    if min_per_label_top3_source_hit_rate is not None:
        _validate_per_label_rate(
            payload,
            "per_label_top3_source_hit_rate",
            min_per_label_top3_source_hit_rate,
        )
    if min_top3_doc_id_hit_rate is not None:
        value = _metric_value(payload, ("top3_doc_id_hit_rate",))
        if value < min_top3_doc_id_hit_rate:
            raise ValueError("retrieval-metrics: top3 doc-id hit rate below threshold")
    if min_per_label_top3_doc_id_hit_rate is not None:
        _validate_per_label_rate(
            payload,
            "per_label_top3_doc_id_hit_rate",
            min_per_label_top3_doc_id_hit_rate,
        )
    if min_graduation_top3_source_hit_rate is not None:
        value = _metric_value(payload, ("graduation_top3_source_hit_rate",))
        if value < min_graduation_top3_source_hit_rate:
            raise ValueError("retrieval-metrics: graduation top3 source hit rate below threshold")
    if min_graduation_top3_doc_id_hit_rate is not None:
        value = _metric_value(payload, ("graduation_top3_doc_id_hit_rate",))
        if value < min_graduation_top3_doc_id_hit_rate:
            raise ValueError("retrieval-metrics: graduation top3 doc-id hit rate below threshold")
    if min_graduation_curriculum_pdf_hit_rate is not None:
        value = _metric_value(payload, ("graduation_curriculum_pdf_hit_rate",))
        if value < min_graduation_curriculum_pdf_hit_rate:
            raise ValueError("retrieval-metrics: graduation curriculum PDF hit rate below threshold")
    if min_retrieved_evidence_alignment_rate is not None:
        value = _metric_value(payload, ("retrieved_evidence_alignment_rate",))
        if value < min_retrieved_evidence_alignment_rate:
            raise ValueError("retrieval-metrics: retrieved evidence alignment rate below threshold")
    if max_alignment_failures is not None:
        failures = payload.get("alignment_failures")
        if not isinstance(failures, list):
            raise ValueError("retrieval-metrics: alignment_failures must be a list")
        if len(failures) > max_alignment_failures:
            raise ValueError("retrieval-metrics: alignment failures above threshold")
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


def _validate_per_label_rate(payload: dict[str, object], field: str, threshold: float) -> None:
    rates = payload.get(field)
    if not isinstance(rates, dict):
        raise ValueError(f"retrieval-metrics: {field} is required")
    for label in range(5):
        value = rates.get(str(label))
        if not isinstance(value, int | float):
            raise ValueError(f"retrieval-metrics: {field} missing label {label}")
        if float(value) < threshold:
            raise ValueError(f"retrieval-metrics: {field} label {label} below threshold")


def validate_chat_quality(
    output_path: Path,
    *,
    input_path: Path | None = None,
    knowledge_path: Path | None = None,
    min_answer_chars: int | None = None,
    require_source_hint: bool = False,
    require_evidence_alignment: bool = False,
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
    if require_evidence_alignment:
        if knowledge_path is None:
            raise ValueError("chat-quality: --knowledge is required for evidence alignment")
        _validate_chat_evidence_alignment(rows, knowledge_path)


def validate_chat_provenance(
    path: Path,
    *,
    input_path: Path | None = None,
    output_path: Path | None = None,
    knowledge_path: Path | None = None,
    require_backend: str | None = None,
    max_fallback_used: int | None = None,
    require_retrieved_docs: bool = False,
    require_model_checksum: bool = False,
) -> None:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a provenance object")
    if payload.get("evaluation_scope") != "task2_chat_batch_provenance":
        raise ValueError("chat-provenance: evaluation_scope is invalid")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("chat-provenance: rows must be a list")
    if input_path is not None:
        inputs = validate_rows(input_path, ChatInput, required=True)
        if payload.get("input_checksum") != file_checksum(input_path):
            raise ValueError("chat-provenance: input_checksum does not match input file")
        if len(rows) != len(inputs):
            raise ValueError("chat-provenance: row count does not match input")
    if output_path is not None:
        outputs = validate_rows(output_path, ChatOutput, required=True)
        if payload.get("output_checksum") != file_checksum(output_path):
            raise ValueError("chat-provenance: output_checksum does not match output file")
        if payload.get("row_count") != len(outputs):
            raise ValueError("chat-provenance: row_count does not match output")
    if knowledge_path is not None and payload.get("knowledge_checksum") != file_checksum(knowledge_path):
        raise ValueError("chat-provenance: knowledge_checksum does not match knowledge file")
    if require_backend is not None and payload.get("backend_used") != require_backend:
        raise ValueError("chat-provenance: backend_used does not match required backend")
    fallback_used = bool(payload.get("fallback_used"))
    fallback_count = int(fallback_used)
    if max_fallback_used is not None and fallback_count > max_fallback_used:
        raise ValueError("chat-provenance: fallback_used exceeds threshold")
    if fallback_used and not payload.get("fallback_reason"):
        raise ValueError("chat-provenance: fallback_reason is required when fallback is used")
    if require_model_checksum and not payload.get("model_checksum"):
        raise ValueError("chat-provenance: model_checksum is required")
    if require_retrieved_docs:
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValueError(f"chat-provenance: row {index} must be an object")
            retrieved = row.get("retrieved")
            if not isinstance(retrieved, list) or not retrieved:
                raise ValueError(f"chat-provenance: row {index} lacks retrieved docs")
            for item in retrieved:
                if not isinstance(item, dict):
                    raise ValueError(f"chat-provenance: row {index} retrieved item must be an object")
                if not item.get("doc_id") or not item.get("source_url"):
                    raise ValueError(f"chat-provenance: row {index} retrieved item lacks source evidence")


def _validate_chat_evidence_alignment(rows: list[ChatOutput], knowledge_path: Path) -> None:
    from nlp_term.chat.router import route_question
    from nlp_term.retrieve.knowledge import load_knowledge
    from nlp_term.retrieve.rank import rank_docs

    docs = load_knowledge(knowledge_path)
    docs_by_id = {doc.doc_id: doc for doc in docs}
    for row in rows:
        route = route_question(row.user)
        ranked = [doc for doc in rank_docs(row.user, docs=docs, top_k=3) if doc.label == route.label]
        if not ranked:
            continue
        top_doc = docs_by_id.get(ranked[0].doc_id)
        if top_doc is None:
            raise ValueError(f"chat-quality: missing ranked knowledge doc for {row.user}")
        if top_doc.source_url not in row.model:
            raise ValueError(f"chat-quality: answer does not cite top evidence URL for {row.user}")
        excerpts = QA_EVIDENCE_RE.findall(row.model)
        if not excerpts:
            raise ValueError(f"chat-quality: answer lacks quoted evidence excerpt for {row.user}")
        token_hits = sum(1 for token in excerpts[-1].split() if len(token) > 1 and token in top_doc.body)
        if token_hits < 6:
            raise ValueError(f"chat-quality: evidence excerpt is not aligned with ranked source for {row.user}")


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
    parser.add_argument("--source-inventory", action="store_true", help="Validate source inventory candidate stages.")
    parser.add_argument("--source-stage-coverage", type=Path, help="Validate staged source inventory coverage.")
    parser.add_argument("--knowledge-provenance", type=Path, help="Validate knowledge docs against source probe metadata.")
    parser.add_argument("--require-official-chain", action="store_true", help="Require provenance sources to be official-chain verified.")
    parser.add_argument("--require-official-chain-evidence", action="store_true")
    parser.add_argument("--require-raw-provenance", action="store_true")
    parser.add_argument("--model-shortlist", type=Path, help="Validate model shortlist metadata.")
    parser.add_argument("--knowledge-quality", type=Path, help="Validate source-backed knowledge quality gates.")
    parser.add_argument("--tier1-coverage", action="store_true", help="Validate Tier 1 curated RAG-ready coverage.")
    parser.add_argument("--dataset-quality", action="store_true", help="Validate generated classification/QA quality gates.")
    parser.add_argument("--gold-data", type=Path, help="Validate human/gold evaluation artifact contracts.")
    parser.add_argument("--metric-claim", type=Path, help="Validate metric claim metadata and checksum binding.")
    parser.add_argument("--classifier-metrics", type=Path, help="Validate classifier metric gates.")
    parser.add_argument("--task1-hard-gates", action="store_true", help="Validate Task 1 generated-data hard gates.")
    parser.add_argument("--task1-hard-report-output", type=Path, help="Write a Task 1 hard-gate report.")
    parser.add_argument("--retrieval-metrics", type=Path, help="Validate retrieval metric gates.")
    parser.add_argument("--chat-quality", type=Path, help="Validate chat output quality gates.")
    parser.add_argument("--chat-provenance", type=Path, help="Validate Task 2 chat backend provenance.")
    parser.add_argument("--realtime-provenance", type=Path, help="Validate realtime output against source provenance.")
    parser.add_argument("--runtime-knowledge-consistency", action="store_true", help="Validate runtime knowledge loader consistency.")
    parser.add_argument("--final-readiness", action="store_true", help="Reject placeholder terms in final-facing outputs.")
    parser.add_argument("--require-raw-files", action="store_true", help="Require source probe raw files to exist.")
    parser.add_argument("--require-realtime", action="store_true", help="Require realtime input/output files.")
    parser.add_argument("--input", type=Path, help="Input artifact used by a metric or output validator.")
    parser.add_argument("--output", type=Path, help="Output artifact used by a provenance validator.")
    parser.add_argument("--knowledge", type=Path, help="Knowledge artifact used by runtime or retrieval validators.")
    parser.add_argument("--qa", type=Path, help="QA artifact used by retrieval validators.")
    parser.add_argument("--min-docs-per-label", type=int)
    parser.add_argument("--min-total-docs", type=int)
    parser.add_argument("--min-body-chars", type=int)
    parser.add_argument("--min-source-parse-ratio", type=float)
    parser.add_argument("--min-index-eligible-sources", type=int)
    parser.add_argument("--min-raw-sources", type=int)
    parser.add_argument("--min-accepted-docs", type=int)
    parser.add_argument("--min-structured-rows", type=int)
    parser.add_argument("--min-index-chunk-candidates", type=int)
    parser.add_argument("--min-graduation-docs", type=int)
    parser.add_argument("--min-graduation-rows", type=int)
    parser.add_argument("--min-notice-docs", type=int)
    parser.add_argument("--max-notice-docs", type=int)
    parser.add_argument("--max-notice-doc-ratio", type=float)
    parser.add_argument("--max-notice-duplicate-ratio", type=float)
    parser.add_argument("--max-source-concentration", type=float)
    parser.add_argument("--min-calendar-rows", type=int)
    parser.add_argument("--min-dining-rows", type=int)
    parser.add_argument("--min-shuttle-rows", type=int)
    parser.add_argument("--min-cls-rows", type=int)
    parser.add_argument("--min-cls-per-label", type=int)
    parser.add_argument("--min-ambiguous-per-label", type=int)
    parser.add_argument("--min-qa-rows", type=int)
    parser.add_argument("--min-qa-per-label", type=int)
    parser.add_argument("--min-task1-gold-rows", type=int)
    parser.add_argument("--min-task1-gold-per-label", type=int)
    parser.add_argument("--min-task2-facts-per-label", type=int)
    parser.add_argument("--min-task2-answer-rows", type=int)
    parser.add_argument("--no-dry-run", action="store_true")
    parser.add_argument("--require-validated", action="store_true")
    parser.add_argument("--require-qa-source", action="store_true")
    parser.add_argument("--require-source-disjoint", action="store_true")
    parser.add_argument("--require-cls-source-docs", action="store_true")
    parser.add_argument("--max-normalized-duplicate-count", type=int)
    parser.add_argument("--max-conflicting-duplicate-count", type=int)
    parser.add_argument("--max-title-cue-ratio", type=float)
    parser.add_argument("--min-source-docs-per-label", type=int)
    parser.add_argument("--max-source-concentration-ratio", type=float)
    parser.add_argument("--min-macro-f1", type=float)
    parser.add_argument("--min-weighted-f1", type=float)
    parser.add_argument("--min-class-f1", type=float)
    parser.add_argument("--min-top1-label-accuracy", type=float)
    parser.add_argument("--min-top3-source-hit-rate", type=float)
    parser.add_argument("--min-top3-doc-id-hit-rate", type=float)
    parser.add_argument("--min-per-label-top1-label-accuracy", type=float)
    parser.add_argument("--min-per-label-top3-source-hit-rate", type=float)
    parser.add_argument("--min-per-label-top3-doc-id-hit-rate", type=float)
    parser.add_argument("--min-graduation-top3-source-hit-rate", type=float)
    parser.add_argument("--min-graduation-top3-doc-id-hit-rate", type=float)
    parser.add_argument("--min-graduation-curriculum-pdf-hit-rate", type=float)
    parser.add_argument("--min-retrieved-evidence-alignment-rate", type=float)
    parser.add_argument("--max-alignment-failures", type=int)
    parser.add_argument("--require-metadata-aware", action="store_true")
    parser.add_argument("--require-retrieval-diagnostics", action="store_true")
    parser.add_argument("--min-answer-chars", type=int)
    parser.add_argument("--require-evidence-alignment", action="store_true")
    parser.add_argument("--require-backend", choices=["llama", "deterministic"])
    parser.add_argument("--max-fallback-used", type=int)
    parser.add_argument("--require-retrieved-docs", action="store_true")
    parser.add_argument("--require-model-checksum", action="store_true")
    parser.add_argument("--require-dataset-origin", choices=sorted(METRIC_DATASET_ORIGINS))
    parser.add_argument("--require-claim-level", choices=sorted(METRIC_CLAIM_LEVELS))
    parser.add_argument("--stage", default="stage0")
    parser.add_argument("--min-stage-sources", type=int)
    parser.add_argument("--max-stage-sources", type=int)
    parser.add_argument("--min-stage1-candidates", type=int)
    parser.add_argument("--min-stage2-candidates", type=int)
    parser.add_argument("--require-stage-candidate-labels", action="store_true")
    parser.add_argument("--require-stage-labels", action="store_true")
    parser.add_argument("--require-graduation-departments", type=int)
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
        and not args.source_inventory
        and not args.source_stage_coverage
        and not args.knowledge_provenance
        and not args.model_shortlist
        and not args.knowledge_quality
        and not args.tier1_coverage
        and not args.dataset_quality
        and not args.gold_data
        and not args.metric_claim
        and not args.classifier_metrics
        and not args.task1_hard_gates
        and not args.retrieval_metrics
        and not args.chat_quality
        and not args.chat_provenance
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
            validate_source_probe(
                args.source_probe,
                require_raw_files=args.require_raw_files,
                require_official_chain_evidence=args.require_official_chain_evidence,
            )
        if args.source_inventory:
            validate_source_inventory(
                min_stage1_candidates=args.min_stage1_candidates,
                min_stage2_candidates=args.min_stage2_candidates,
                require_stage_candidate_labels=args.require_stage_candidate_labels,
            )
        if args.source_stage_coverage:
            validate_source_stage_coverage(
                args.source_stage_coverage,
                stage=args.stage,
                min_stage_sources=args.min_stage_sources,
                max_stage_sources=args.max_stage_sources,
                require_stage_labels=args.require_stage_labels,
                require_graduation_departments=args.require_graduation_departments,
            )
        if args.knowledge_provenance:
            validate_knowledge_provenance(
                args.data_dir,
                args.knowledge_provenance,
                require_official_chain=args.require_official_chain,
                require_raw_provenance=args.require_raw_provenance,
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
                min_total_docs=args.min_total_docs,
            )
        if args.tier1_coverage:
            if args.source_probe is None:
                raise ValueError("--tier1-coverage requires --source-probe")
            validate_tier1_coverage(
                data_dir=args.data_dir,
                source_probe_path=args.source_probe,
                min_index_eligible_sources=args.min_index_eligible_sources,
                min_raw_sources=args.min_raw_sources,
                min_accepted_docs=args.min_accepted_docs,
                min_structured_rows=args.min_structured_rows,
                min_index_chunk_candidates=args.min_index_chunk_candidates,
                min_graduation_docs=args.min_graduation_docs,
                min_graduation_rows=args.min_graduation_rows,
                min_notice_docs=args.min_notice_docs,
                max_notice_docs=args.max_notice_docs,
                max_notice_doc_ratio=args.max_notice_doc_ratio,
                max_notice_duplicate_ratio=args.max_notice_duplicate_ratio,
                max_source_concentration=args.max_source_concentration,
                min_calendar_rows=args.min_calendar_rows,
                min_dining_rows=args.min_dining_rows,
                min_shuttle_rows=args.min_shuttle_rows,
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
        if args.gold_data:
            validate_gold_data(
                args.gold_data,
                min_task1_rows=args.min_task1_gold_rows,
                min_task1_per_label=args.min_task1_gold_per_label,
                min_task2_facts_per_label=args.min_task2_facts_per_label,
                min_task2_answer_rows=args.min_task2_answer_rows,
            )
        if args.metric_claim:
            validate_metric_claim(
                args.metric_claim,
                input_path=args.input,
                require_dataset_origin=args.require_dataset_origin,
                require_claim_level=args.require_claim_level,
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
        if args.task1_hard_gates:
            validate_task1_hard_gates(
                args.data_dir,
                report_output=args.task1_hard_report_output,
                require_cls_source_docs=args.require_cls_source_docs,
                max_normalized_duplicate_count=args.max_normalized_duplicate_count,
                max_conflicting_duplicate_count=args.max_conflicting_duplicate_count,
                max_title_cue_ratio=args.max_title_cue_ratio,
                min_source_docs_per_label=args.min_source_docs_per_label,
                max_source_concentration_ratio=args.max_source_concentration_ratio,
            )
        if args.retrieval_metrics:
            validate_retrieval_metrics(
                args.retrieval_metrics,
                knowledge_path=args.knowledge,
                qa_path=args.qa,
                min_top1_label_accuracy=args.min_top1_label_accuracy,
                min_top3_source_hit_rate=args.min_top3_source_hit_rate,
                min_top3_doc_id_hit_rate=args.min_top3_doc_id_hit_rate,
                min_per_label_top1_label_accuracy=args.min_per_label_top1_label_accuracy,
                min_per_label_top3_source_hit_rate=args.min_per_label_top3_source_hit_rate,
                min_per_label_top3_doc_id_hit_rate=args.min_per_label_top3_doc_id_hit_rate,
                min_graduation_top3_source_hit_rate=args.min_graduation_top3_source_hit_rate,
                min_graduation_top3_doc_id_hit_rate=args.min_graduation_top3_doc_id_hit_rate,
                min_graduation_curriculum_pdf_hit_rate=args.min_graduation_curriculum_pdf_hit_rate,
                min_retrieved_evidence_alignment_rate=args.min_retrieved_evidence_alignment_rate,
                max_alignment_failures=args.max_alignment_failures,
                require_metadata_aware=args.require_metadata_aware,
                require_diagnostics=args.require_retrieval_diagnostics,
            )
        if args.chat_quality:
            validate_chat_quality(
                args.chat_quality,
                input_path=args.input,
                knowledge_path=args.knowledge,
                min_answer_chars=args.min_answer_chars,
                require_source_hint=args.require_source_hint,
                require_evidence_alignment=args.require_evidence_alignment,
            )
        if args.chat_provenance:
            validate_chat_provenance(
                args.chat_provenance,
                input_path=args.input,
                output_path=args.output,
                knowledge_path=args.knowledge,
                require_backend=args.require_backend,
                max_fallback_used=args.max_fallback_used,
                require_retrieved_docs=args.require_retrieved_docs,
                require_model_checksum=args.require_model_checksum,
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
