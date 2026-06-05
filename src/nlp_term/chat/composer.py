from __future__ import annotations

from nlp_term.chat.router import RoutedQuestion
from nlp_term.chat.templates import fallback_answer
from nlp_term.retrieve.rank import rank_docs


def compose_answer(route: RoutedQuestion) -> str:
    docs = [doc for doc in rank_docs(route.user, top_k=3) if doc.label == route.label]
    if not docs:
        return fallback_answer(route)
    doc = docs[0]
    return f"{fallback_answer(route)}\n근거 후보: {doc.title} ({doc.source_url})"
