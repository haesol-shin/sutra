from __future__ import annotations

from nlp_term.schemas import KnowledgeDoc, RetrievedDoc
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
GENERIC_QUERY_TOKENS = {
    "공식",
    "안내",
    "어디",
    "에서",
    "확인",
    "페이",
    "이지",
    "페이지",
}


def tokenize(text: str) -> set[str]:
    compact = text.lower().replace(" ", "")
    tokens = {compact[index : index + 2] for index in range(max(len(compact) - 1, 0))}
    tokens.update(part.lower() for part in text.split())
    return {token for token in tokens if token and token not in GENERIC_QUERY_TOKENS}


def rank_docs(question: str, docs: list[KnowledgeDoc] | None = None, *, top_k: int = 3) -> list[RetrievedDoc]:
    candidates = load_knowledge() if docs is None else docs
    query_tokens = tokenize(question)
    latest_query = _is_latest_query(question)
    bare_latest_notice_query = latest_query and _is_bare_latest_notice_query(question)
    ranked: list[tuple[RetrievedDoc, str]] = []
    for doc in candidates:
        title_tokens = tokenize(doc.title)
        doc_tokens = tokenize(doc.body)
        metadata_tokens = tokenize(_metadata_text(doc))
        title_overlap = len(query_tokens & title_tokens)
        body_overlap = len(query_tokens & doc_tokens)
        metadata_overlap = len(query_tokens & metadata_tokens)
        score = (
            title_overlap * 2.0
            + body_overlap
            + metadata_overlap * 1.5
        ) / max(len(query_tokens), 1)
        retrieved = RetrievedDoc(
            doc_id=doc.doc_id,
            score=score,
            title=doc.title,
            source_url=doc.source_url,
            label=doc.label,
        )
        ranked.append(
            (
                retrieved,
                _notice_posted_date(doc) if latest_query else "",
            )
        )
    if bare_latest_notice_query:
        ranked.sort(key=lambda row: (row[1], row[0].score, -row[0].label), reverse=True)
    else:
        ranked.sort(key=lambda row: (row[0].score, row[1], -row[0].label), reverse=True)
    return [row for row, _ in ranked[:top_k]]


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


def _is_bare_latest_notice_query(question: str) -> bool:
    compact = question.replace(" ", "")
    for token in (
        "가장최근",
        "최근",
        "최신",
        "이번에",
        "방금",
        "올라온",
        "공지사항",
        "공지",
        "언제",
        "게시되었나요",
        "게시",
        "등록",
        "알려줘",
        "보여줘",
        "나요",
        "은",
        "는",
        "이",
        "가",
        "에",
        "의",
        "을",
        "를",
        "요",
        "?",
    ):
        compact = compact.replace(token, "")
    return compact == ""


def _notice_posted_date(doc: KnowledgeDoc) -> str:
    if doc.domain != "notices":
        return ""
    posted_date = doc.metadata.get("posted_date")
    if isinstance(posted_date, str):
        return posted_date
    return ""
