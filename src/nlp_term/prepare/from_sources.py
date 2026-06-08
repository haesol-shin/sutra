from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import unicodedata

from pydantic import BaseModel

from nlp_term.paths import PROJECT_ROOT
from nlp_term.prepare.chunking import SourceChunk, split_source_text
from nlp_term.prepare.document_parsers import document_to_text
from nlp_term.prepare.normalize import clip_text
from nlp_term.prepare.parsers import html_to_text, source_doc_from_text
from nlp_term.schemas import KnowledgeDoc, RawSource, SourceVerification
from nlp_term.collect.source_inventory import SourceSpec, iter_specs
from nlp_term.structured.calendar import CalendarAdapter
from nlp_term.structured.dining import DiningAdapter
from nlp_term.structured.notices import NoticeAdapter
from nlp_term.structured.shuttle import ShuttleAdapter
from nlp_term.validators import read_json


BOILERPLATE_TERMS = (
    "본문 바로가기",
    "사이드메뉴",
    "주요메뉴",
    "통합검색",
    "사이트맵",
    "CNU홍보",
    "홍보동영상",
    "홍보브로슈어",
    "사이버투어",
    "캠퍼스투어",
    "대학/대학원",
    "열기 버튼",
    "닫기버튼",
    "All Rights Reserved",
    "The Strong CNU",
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
MOJIBAKE_RE = re.compile(r"[泲湮ȯմϴбտαøũĴ�]+")
DOMAIN_KEYWORDS: dict[int, tuple[str, ...]] = {
    0: ("졸업", "교양", "전공", "학점", "교육과정", "이수"),
    1: ("공지", "학사정보", "게시", "백마광장", "학사지원과", "작성일", "조회수", "수강신청", "휴학", "복학"),
    2: ("학사일정", "일정", "학기"),
    3: ("식단", "메뉴", "학생회관", "조식", "중식", "석식"),
    4: ("셔틀", "버스", "통학", "시간표", "운행"),
}


class SourceParseFailure(BaseModel):
    source_id: str
    raw_path: str
    reason: str


STRUCTURED_ADAPTERS = {
    "academic_calendar": CalendarAdapter(),
    "cnu_mobile_food": DiningAdapter(),
    "academic_notice_board": NoticeAdapter(),
    "shuttle_bus": ShuttleAdapter(),
}


def parse_source(raw: RawSource, *, chunks_per_source: int = 3) -> tuple[list[KnowledgeDoc], SourceParseFailure | None]:
    raw_path = PROJECT_ROOT / Path(raw.raw_path)
    try:
        text = _extract_text(raw, raw_path)
        chunks = _chunk_text(text, chunks_per_source=chunks_per_source, label=raw.label)
        docs = []
        for index, chunk in enumerate(chunks):
            chunk_index = index + 1
            doc = source_doc_from_text(
                raw,
                title=f"{raw.domain} source {chunk_index}",
                body=chunk.text,
                section=f"chunk_{chunk_index}",
                parser_name=_parser_name(raw),
            )
            doc.metadata.update(
                {
                    "chunking_strategy": chunk.strategy,
                    "boundary_type": chunk.boundary_type,
                    "chunk_confidence": chunk.chunk_confidence,
                    "chunk_index": chunk_index,
                    "source_chunk_index": chunk.index,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                }
            )
            docs.append(doc)
        return docs, None
    except Exception as exc:
        return [], SourceParseFailure(source_id=raw.source_id, raw_path=str(raw_path), reason=str(exc))


def build_knowledge_from_probe(
    source_probe_path: Path,
    *,
    chunks_per_source: int = 9,
) -> tuple[list[KnowledgeDoc], list[SourceParseFailure]]:
    payload = read_json(source_probe_path)
    if not isinstance(payload, list):
        raise ValueError(f"{source_probe_path} must contain a JSON list")
    docs: list[KnowledgeDoc] = []
    failures: list[SourceParseFailure] = []
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError(f"{source_probe_path} rows must be objects")
        raw = RawSource.model_validate(row.get("raw"))
        verification = SourceVerification.model_validate(row.get("verification"))
        structured_docs, structured_failure = parse_structured_source(raw, verification=verification)
        docs.extend(structured_docs)
        if structured_failure:
            failures.append(structured_failure)
        parsed_docs, failure = parse_source(raw, chunks_per_source=chunks_per_source)
        inventory = row.get("inventory")
        if isinstance(inventory, dict):
            for doc in [*structured_docs, *parsed_docs]:
                doc.metadata.update({f"source_{key}": value for key, value in inventory.items()})
                doc.metadata.update(_tier1_lifecycle_metadata(raw, verification, inventory=inventory))
        for doc in parsed_docs:
            doc.metadata.update(_raw_provenance_metadata(raw, verification))
        docs.extend(parsed_docs)
        if failure:
            failures.append(failure)
    return docs, failures


def parse_structured_source(
    raw: RawSource,
    *,
    verification: SourceVerification,
) -> tuple[list[KnowledgeDoc], SourceParseFailure | None]:
    adapter = STRUCTURED_ADAPTERS.get(raw.source_id)
    if adapter is None:
        return [], None
    try:
        spec = _spec_for(raw.source_id)
        rows = adapter.parse(spec=spec, raw=raw, verification=verification)
        return adapter.to_knowledge_docs(rows), None
    except Exception as exc:
        return [], SourceParseFailure(source_id=raw.source_id, raw_path=raw.raw_path, reason=f"structured parse failed: {exc}")


def _raw_provenance_metadata(raw: RawSource, verification: SourceVerification) -> dict[str, object]:
    return {
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


def _tier1_lifecycle_metadata(
    raw: RawSource,
    verification: SourceVerification,
    *,
    inventory: dict,
) -> dict[str, object]:
    active = bool(inventory.get("active", True))
    freshness_policy = str(inventory.get("freshness_policy", "snapshot"))
    source_is_usable = active and (verification.official_chain_ok or freshness_policy == "short_ttl")
    raw_ok = raw.status_code is None or 200 <= raw.status_code < 300
    index_eligible = source_is_usable and raw_ok
    return {
        "source_id": raw.source_id,
        "source_url": raw.url,
        "source_domain": raw.domain,
        "source_label": raw.label,
        "official_chain_ok": verification.official_chain_ok,
        "freshness_policy": freshness_policy,
        "lifecycle_status": "index_eligible" if index_eligible else "parsed",
        "index_eligible": index_eligible,
        "parser_name": verification.parser_name,
        "parser_version": verification.parser_version,
    }


def _spec_for(source_id: str) -> SourceSpec:
    for spec in iter_specs(stage="all", active_only=False):
        if spec.source_id == source_id:
            return spec
    raise ValueError(f"source spec not found: {source_id}")


def write_payload(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build source-backed knowledge docs from raw source snapshots.")
    parser.add_argument("--source-probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--failures-output", type=Path, default=Path("data/source_parse_failures.json"))
    parser.add_argument("--chunks-per-source", type=int, default=9)
    args = parser.parse_args()

    docs, failures = build_knowledge_from_probe(args.source_probe, chunks_per_source=args.chunks_per_source)
    write_payload(args.output, [doc.model_dump() for doc in docs])
    write_payload(args.failures_output, [failure.model_dump() for failure in failures])
    print(f"wrote {len(docs)} knowledge docs to {args.output}")
    if failures:
        print(f"wrote {len(failures)} parse failures to {args.failures_output}")


def _extract_text(raw: RawSource, raw_path: Path) -> str:
    if not raw_path.exists():
        raise FileNotFoundError(raw_path)
    suffix = raw_path.suffix.lower()
    content_type = raw.content_type.lower()
    if suffix in {".pdf", ".hwp", ".hwpx"} or any(kind in content_type for kind in ("pdf", "hwp", "hwpx")):
        return document_to_text(raw_path, content_type=raw.content_type)
    return html_to_text(raw_path.read_bytes(), source_id=raw.source_id)


def _chunk_text(text: str, *, chunks_per_source: int, label: int) -> list[SourceChunk]:
    clipped = clip_text(text, max_chars=60000)
    chunks = split_source_text(
        clipped,
        label=label,
        max_chunk_chars=_chunk_chars_for_label(label),
        max_chunks=max(chunks_per_source * 4, chunks_per_source),
    )
    chunks = _ranked_source_chunks(chunks, label=label, limit=chunks_per_source)
    if not chunks:
        raise ValueError("no clean source chunk passed content quality gates")
    return chunks


def _chunk_chars_for_label(label: int) -> int:
    if label == 1:
        return 220
    return 300


def _ranked_source_chunks(chunks: list[SourceChunk], *, label: int, limit: int) -> list[SourceChunk]:
    scored: list[tuple[int, int, SourceChunk]] = []
    for chunk in chunks:
        score = _source_chunk_score(chunk, label)
        if score > 0:
            scored.append((score, chunk.char_start if chunk.char_start is not None else chunk.index, chunk))
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = sorted(scored[:limit], key=lambda item: item[1])
    return [chunk for _, _, chunk in selected]


def _source_chunk_score(chunk: SourceChunk, label: int) -> int:
    if chunk.chunk_confidence == "high":
        keyword_hits = sum(1 for keyword in DOMAIN_KEYWORDS[label] if keyword in chunk.text)
        hangul_count = sum(1 for char in chunk.text if "가" <= char <= "힣")
        return 10000 + keyword_hits * 100 + hangul_count
    score = _chunk_score(chunk.text, label)
    if chunk.chunk_confidence == "medium":
        score = max(score, 1)
    return score


def _ranked_content_chunks(text: str, *, label: int, chunk_chars: int, limit: int) -> list[str]:
    scored: list[tuple[int, int, str]] = []
    step = max(chunk_chars // 2, 80)
    for start in range(0, len(text), step):
        chunk = text[start : start + chunk_chars].strip()
        if len(chunk) < 80:
            continue
        score = _chunk_score(chunk, label)
        if score > 0:
            scored.append((score, start, chunk))
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = sorted(scored[:limit], key=lambda item: item[1])
    return [chunk for _, _, chunk in selected]


def _chunk_score(chunk: str, label: int) -> int:
    folded = chunk.casefold()
    boilerplate_hits = sum(1 for term in BOILERPLATE_TERMS if term.casefold() in folded)
    if boilerplate_hits >= 1:
        return 0
    if MOJIBAKE_RE.search(chunk) or _contains_private_use(chunk):
        return 0
    hangul_count = sum(1 for char in chunk if "가" <= char <= "힣")
    if hangul_count < 30:
        return 0
    keyword_hits = sum(1 for keyword in DOMAIN_KEYWORDS[label] if keyword in chunk)
    if keyword_hits < 1:
        return 0
    if not _has_source_specific_signal(chunk, label):
        return 0
    return hangul_count + keyword_hits * 40 - boilerplate_hits * 50


def _has_source_specific_signal(chunk: str, label: int) -> bool:
    if label == 1:
        return bool(re.search(r"20\d{2}-\d{2}-\d{2}", chunk)) and any(
            term in chunk for term in ("공지", "학사지원과", "작성일", "조회수")
        )
    if label == 2:
        return bool(re.search(r"\d{2}\.\d{2}", chunk)) and any(
            term in chunk for term in ("개강", "수강신청", "휴학", "복학", "등록", "계절학기", "성적")
        )
    if label == 3:
        return any(term in chunk for term in ("조식", "중식", "석식", "메뉴운영내역", "원산지"))
    if label == 4:
        return any(term in chunk for term in ("운영기준", "운행", "시간표", "평일", "주말", "공휴일", "월평역"))
    return True


def _contains_private_use(text: str) -> bool:
    return any(unicodedata.category(char) == "Co" for char in text)


def _parser_name(raw: RawSource) -> str:
    suffix = Path(raw.raw_path).suffix.lower().lstrip(".") or "html"
    return f"{suffix}_source_parse"


if __name__ == "__main__":
    main()
