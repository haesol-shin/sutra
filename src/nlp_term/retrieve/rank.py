from __future__ import annotations

from datetime import date

from nlp_term.schemas import KnowledgeDoc, RetrievedDoc
from nlp_term.classify.predict import predict_label
from nlp_term.retrieve.knowledge import load_knowledge


METADATA_FIELDS = (
    "source_id",
    "domain",
    "section",
    "source_stage",
    "source_department",
    "source_curriculum_year",
    "source_parser_type",
    "source_notes",
    "search_aliases",
    "notice_title",
    "posted_date",
    "author",
    "detail_url",
)
LABEL_HINTS = {
    0: ("졸업", "교육과정", "학점", "전공", "교양", "이수"),
    1: ("공지", "학사", "수강신청", "휴학", "복학", "장학", "신청"),
    2: ("학사일정", "일정", "개강", "종강", "등록", "계절학기"),
    3: ("식단", "메뉴", "조식", "중식", "석식", "학생회관"),
    4: ("셔틀", "버스", "통학", "운행", "시간표", "월평역"),
}


def tokenize(text: str) -> set[str]:
    compact = text.lower().replace(" ", "")
    tokens = {compact[index : index + 2] for index in range(max(len(compact) - 1, 0))}
    tokens.update(part.lower() for part in text.split())
    return {token for token in tokens if token}


def rank_docs(question: str, docs: list[KnowledgeDoc] | None = None, *, top_k: int = 3) -> list[RetrievedDoc]:
    candidates = load_knowledge() if docs is None else docs
    query_tokens = tokenize(question)
    predicted_label = predict_label(question)
    latest_query = _is_latest_query(question)
    ranked: list[RetrievedDoc] = []
    for doc in candidates:
        title_tokens = tokenize(doc.title)
        doc_tokens = tokenize(doc.body)
        metadata_tokens = tokenize(_metadata_text(doc))
        label_tokens = tokenize(" ".join(LABEL_HINTS[doc.label]))
        title_overlap = len(query_tokens & title_tokens)
        body_overlap = len(query_tokens & doc_tokens)
        metadata_overlap = len(query_tokens & metadata_tokens)
        label_overlap = len(query_tokens & label_tokens)
        score = (
            title_overlap * 2.0
            + body_overlap
            + metadata_overlap * 1.5
            + label_overlap * 0.75
            + (1.0 if doc.label == predicted_label else 0.0)
        ) / max(len(query_tokens), 1)
        if latest_query and doc.domain == "notices":
            score += _posted_date_bonus(doc)
        ranked.append(
            RetrievedDoc(
                doc_id=doc.doc_id,
                score=score,
                title=doc.title,
                source_url=doc.source_url,
                label=doc.label,
            )
        )
    ranked.sort(key=lambda row: (row.score, -row.label), reverse=True)
    return ranked[:top_k]


def _metadata_text(doc: KnowledgeDoc) -> str:
    values: list[str] = [doc.source_id, doc.domain, doc.section or ""]
    for field in METADATA_FIELDS:
        value = doc.metadata.get(field)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            values.extend(str(item) for item in value)
        elif isinstance(value, bool | int | float):
            values.append(str(value))
    return " ".join(values)


def _is_latest_query(question: str) -> bool:
    compact = question.replace(" ", "")
    return any(token in compact for token in ("가장최근", "최근", "최신", "이번에", "방금")) and any(
        token in compact for token in ("공지", "올라온", "게시", "등록")
    )


def _posted_date_bonus(doc: KnowledgeDoc) -> float:
    posted_date = doc.metadata.get("posted_date")
    if not isinstance(posted_date, str):
        return 0.0
    try:
        parsed = date.fromisoformat(posted_date)
    except ValueError:
        return 0.0
    return parsed.timetuple().tm_yday / 100.0
