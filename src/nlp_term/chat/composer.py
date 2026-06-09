from __future__ import annotations

from pathlib import Path

from nlp_term.chat.router import RoutedQuestion
from nlp_term.chat.templates import fallback_answer
from nlp_term.retrieve.knowledge import load_knowledge
from nlp_term.retrieve.rank import rank_docs


COMPOSER_RETRIEVAL_POOL_SIZE = 24


def compose_answer(route: RoutedQuestion, *, knowledge_path: Path | None = None) -> str:
    knowledge_docs = load_knowledge(knowledge_path)
    ranked_docs = rank_docs(route.user, docs=knowledge_docs, top_k=COMPOSER_RETRIEVAL_POOL_SIZE)
    docs = [doc for doc in ranked_docs if doc.label == route.label]
    if not docs:
        return fallback_answer(route)
    retrieved = docs[0]
    doc = next((item for item in knowledge_docs if item.doc_id == retrieved.doc_id), None)
    excerpt = _evidence_excerpt(doc.body if doc else "")
    return f"{fallback_answer(route)}\n근거 후보: {retrieved.title} ({retrieved.source_url})\n근거 요약: '{excerpt}'"


def _evidence_excerpt(body: str, *, max_chars: int = 120) -> str:
    compact = " ".join(body.split())
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars].rstrip()
