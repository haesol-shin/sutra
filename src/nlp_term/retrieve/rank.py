from __future__ import annotations

import json
from pathlib import Path

from nlp_term.prepare.knowledge import build_seed_knowledge
from nlp_term.schemas import KnowledgeDoc, RetrievedDoc


def tokenize(text: str) -> set[str]:
    compact = text.lower().replace(" ", "")
    tokens = {compact[index : index + 2] for index in range(max(len(compact) - 1, 0))}
    tokens.update(part.lower() for part in text.split())
    return {token for token in tokens if token}


def load_knowledge(path: Path | None = None) -> list[KnowledgeDoc]:
    if path is None or not path.exists():
        return build_seed_knowledge()
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return [KnowledgeDoc.model_validate(row) for row in payload]


def rank_docs(question: str, docs: list[KnowledgeDoc] | None = None, *, top_k: int = 3) -> list[RetrievedDoc]:
    candidates = docs or build_seed_knowledge()
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

