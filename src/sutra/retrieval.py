from __future__ import annotations

import re

from sutra.config import Config
from sutra.models import Document, Evidence, EvidencePack, ScoredDocument


_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


def retrieve(question: str, documents: list[Document], config: Config) -> EvidencePack:
    scored = rank(question, documents, config.rag.top_k)
    return build_evidence(question, scored, config)


def rank(question: str, documents: list[Document], k: int = 8) -> list[ScoredDocument]:
    query_tokens = set(_tokens(question))
    if not query_tokens:
        return []

    scored = [
        ScoredDocument(document=document, score=_score_document(query_tokens, document))
        for document in documents
    ]
    scored = [row for row in scored if row.score > 0]
    scored.sort(key=lambda row: (-row.score, row.document.id))
    return scored[:k]


def build_evidence(question: str, scored: list[ScoredDocument], config: Config) -> EvidencePack:
    items = [
        Evidence(
            id=row.document.id,
            title=row.document.title,
            text=_clip(row.document.text, config.rag.max_fact_chars),
            source_url=row.document.source_url,
            source_name=row.document.source_name,
            score=row.score,
            metadata=row.document.metadata,
        )
        for row in scored[: config.rag.top_k]
    ]
    return EvidencePack(question=question, items=items)


def render_evidence(pack: EvidencePack) -> str:
    if not pack.items:
        return "No evidence was retrieved from the workspace."

    lines: list[str] = []
    for index, item in enumerate(pack.items, start=1):
        source = item.source_name or item.source_url or item.id
        lines.append(f"[{index}] {item.title}".strip())
        lines.append(f"source: {source}")
        if item.source_url:
            lines.append(f"url: {item.source_url}")
        lines.append(item.text)
        lines.append("")
    return "\n".join(lines).strip()


def _score_document(query_tokens: set[str], document: Document) -> float:
    title_tokens = set(_tokens(document.title))
    text_tokens = set(_tokens(document.text))
    return (
        3.0 * len(query_tokens & title_tokens)
        + 1.0 * len(query_tokens & text_tokens)
    )


def _tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN_RE.finditer(text)]


def _clip(text: str, limit: int) -> str:
    stripped = " ".join(text.split())
    if len(stripped) <= limit:
        return stripped
    return stripped[: max(0, limit - 1)].rstrip() + "..."
