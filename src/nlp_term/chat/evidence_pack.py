from __future__ import annotations

from urllib.parse import urlparse
import re

from pydantic import BaseModel, Field

from nlp_term.schemas import Domain, KnowledgeDoc


GENERIC_SOURCE_RE = re.compile(r"(source\s*\d+|chunk_\d+|doc_\d+)", re.IGNORECASE)
DOMAIN_SOURCE_NAMES: dict[Domain, str] = {
    "graduation": "충남대학교 졸업요건",
    "notices": "충남대학교 공지사항",
    "academic_calendar": "충남대학교 학사일정",
    "dining": "충남대학교 식단",
    "shuttle": "충남대학교 셔틀 안내",
}


class EvidenceItem(BaseModel):
    source_name: str
    source_url: str
    facts: list[str] = Field(min_length=1)
    cautions: list[str] = Field(default_factory=list)


class EvidencePack(BaseModel):
    question: str
    intent_label: int = Field(ge=0, le=4)
    intent_domain: Domain
    temporal_context: str | None = None
    primary_structured_rows: list[EvidenceItem] = Field(default_factory=list)
    supporting_chunks: list[EvidenceItem] = Field(default_factory=list)
    items: list[EvidenceItem] = Field(default_factory=list)

    def to_prompt_text(self) -> str:
        lines = [
            f"질문: {self.question}",
            f"의도 라벨: {self.intent_label}",
            f"의도 도메인: {self.intent_domain}",
        ]
        if self.temporal_context:
            lines.extend(["시간 기준:", self.temporal_context])
        if self.primary_structured_rows:
            lines.append("주요 구조화 근거:")
            _append_items(lines, self.primary_structured_rows)
        if self.supporting_chunks:
            lines.append("보조 문서 근거:")
            _append_items(lines, self.supporting_chunks)
        if not self.primary_structured_rows and not self.supporting_chunks:
            lines.append("근거:")
            _append_items(lines, self.items)
        return "\n".join(lines)


def build_evidence_pack(
    *,
    question: str,
    label: int,
    domain: Domain,
    docs: list[KnowledgeDoc],
    max_items: int = 3,
    max_fact_chars: int = 500,
    temporal_context: str | None = None,
) -> EvidencePack:
    selected_docs = [doc for doc in docs[:max_items] if doc.body.strip()]
    primary_structured_rows = [_to_item(doc, max_fact_chars=max_fact_chars) for doc in selected_docs if _is_structured_row(doc)]
    supporting_chunks = [_to_item(doc, max_fact_chars=max_fact_chars) for doc in selected_docs if not _is_structured_row(doc)]
    items = [*primary_structured_rows, *supporting_chunks]
    return EvidencePack(
        question=question,
        intent_label=label,
        intent_domain=domain,
        temporal_context=temporal_context,
        primary_structured_rows=primary_structured_rows,
        supporting_chunks=supporting_chunks,
        items=items,
    )


def _append_items(lines: list[str], items: list[EvidenceItem]) -> None:
    for index, item in enumerate(items, start=1):
        lines.append(f"- 근거 {index}: {item.source_name}")
        for fact in item.facts:
            lines.append(f"  - 핵심 사실: {fact}")
        for caution in item.cautions:
            lines.append(f"  - 주의: {caution}")
        lines.append(f"  - 출처 URL: {item.source_url}")


def _to_item(doc: KnowledgeDoc, *, max_fact_chars: int) -> EvidenceItem:
    return EvidenceItem(
        source_name=_source_name(doc),
        source_url=doc.source_url,
        facts=[_clean_fact(doc.body, max_chars=max_fact_chars)],
        cautions=_cautions(doc),
    )


def _is_structured_row(doc: KnowledgeDoc) -> bool:
    return (
        doc.metadata.get("generation_method") == "structured_row"
        or isinstance(doc.metadata.get("structured_fields"), list)
        or isinstance(doc.metadata.get("row_type"), str)
    )


def _source_name(doc: KnowledgeDoc) -> str:
    metadata_name = doc.metadata.get("source_name")
    if isinstance(metadata_name, str) and _is_clean_source_name(metadata_name):
        return metadata_name
    department = doc.metadata.get("source_department")
    if doc.domain == "graduation" and isinstance(department, str) and department.strip():
        return f"{department.strip()} 졸업요건"
    if _is_clean_source_name(doc.title):
        return doc.title
    return DOMAIN_SOURCE_NAMES.get(doc.domain) or _hostname(doc.source_url)


def _is_clean_source_name(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and GENERIC_SOURCE_RE.search(stripped) is None


def _hostname(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or "충남대학교 공식 출처"


def _clean_fact(body: str, *, max_chars: int = 500) -> str:
    normalized = " ".join(body.replace("\r", " ").replace("\n", " ").split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars].rstrip() + "..."


def _cautions(doc: KnowledgeDoc) -> list[str]:
    if doc.domain in {"academic_calendar", "dining", "shuttle"}:
        return ["세부 정보는 시점에 따라 달라질 수 있으므로 공식 출처를 기준으로 확인한다."]
    if doc.domain == "graduation":
        return ["학과와 입학연도에 따라 기준이 다를 수 있으므로 해당 학과의 공식 기준을 확인한다."]
    return []
