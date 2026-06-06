from __future__ import annotations

from nlp_term.schemas import KnowledgeDoc, RetrievedDoc
from nlp_term.retrieve.knowledge import load_knowledge


def tokenize(text: str) -> set[str]:
    compact = text.lower().replace(" ", "")
    tokens = {compact[index : index + 2] for index in range(max(len(compact) - 1, 0))}
    tokens.update(part.lower() for part in text.split())
    return {token for token in tokens if token}


def rank_docs(question: str, docs: list[KnowledgeDoc] | None = None, *, top_k: int = 3) -> list[RetrievedDoc]:
    candidates = load_knowledge() if docs is None else docs
    query_tokens = tokenize(question)
    ranked: list[RetrievedDoc] = []
    for doc in candidates:
        doc_tokens = tokenize(f"{doc.title} {doc.body}")
        overlap = len(query_tokens & doc_tokens)
        score = overlap / max(len(query_tokens), 1)
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
