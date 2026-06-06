from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import unicodedata

from pydantic import BaseModel

from nlp_term.paths import PROJECT_ROOT
from nlp_term.prepare.document_parsers import document_to_text
from nlp_term.prepare.normalize import clip_text
from nlp_term.prepare.parsers import html_to_text, source_doc_from_text
from nlp_term.schemas import KnowledgeDoc, RawSource
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


def parse_source(raw: RawSource, *, chunks_per_source: int = 3) -> tuple[list[KnowledgeDoc], SourceParseFailure | None]:
    raw_path = PROJECT_ROOT / Path(raw.raw_path)
    try:
        text = _extract_text(raw, raw_path)
        chunks = _chunk_text(text, chunks_per_source=chunks_per_source, label=raw.label)
        docs = [
            source_doc_from_text(
                raw,
                title=f"{raw.domain} source {index + 1}",
                body=chunk,
                section=f"chunk_{index + 1}",
                parser_name=_parser_name(raw),
            )
            for index, chunk in enumerate(chunks)
        ]
        return docs, None
    except Exception as exc:
        return [], SourceParseFailure(source_id=raw.source_id, raw_path=str(raw_path), reason=str(exc))


def build_knowledge_from_probe(source_probe_path: Path) -> tuple[list[KnowledgeDoc], list[SourceParseFailure]]:
    payload = read_json(source_probe_path)
    if not isinstance(payload, list):
        raise ValueError(f"{source_probe_path} must contain a JSON list")
    docs: list[KnowledgeDoc] = []
    failures: list[SourceParseFailure] = []
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError(f"{source_probe_path} rows must be objects")
        raw = RawSource.model_validate(row.get("raw"))
        parsed_docs, failure = parse_source(raw)
        docs.extend(parsed_docs)
        if failure:
            failures.append(failure)
    return docs, failures


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
    args = parser.parse_args()

    docs, failures = build_knowledge_from_probe(args.source_probe)
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


def _chunk_text(text: str, *, chunks_per_source: int, label: int, chunk_chars: int = 300) -> list[str]:
    clipped = clip_text(text, max_chars=60000)
    if label == 1:
        chunk_chars = 220
    chunks = _ranked_content_chunks(clipped, label=label, chunk_chars=chunk_chars, limit=chunks_per_source)
    if not chunks:
        raise ValueError("no clean source chunk passed content quality gates")
    return chunks


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
