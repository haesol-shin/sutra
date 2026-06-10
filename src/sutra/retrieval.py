from __future__ import annotations

import logging
import re
import warnings
from typing import Any

from sutra.config import Config
from sutra.models import Document, Evidence, EvidencePack, ScoredDocument

logger = logging.getLogger(__name__)

# Soft dependencies checking
_KIWI_AVAILABLE = False
_BM25S_AVAILABLE = False
Kiwi = None
BM25 = None

try:
    from kiwipiepy import Kiwi as _Kiwi
    Kiwi = _Kiwi
    _KIWI_AVAILABLE = True
except ImportError:
    pass

try:
    import bm25s as _bm25s
    BM25 = _bm25s.BM25
    _BM25S_AVAILABLE = True
except ImportError:
    pass

DROP_TAGS: set[str] = {
    "JKS", "JKC", "JKG", "JKO", "JKB", "JKV", "JKQ", "JX", "JC",
    "EP", "EF", "EC", "ETN", "ETM", "XSN", "XSV", "XSA",
    "VCP", "VCN", "VX", "SF", "SP", "SS", "SE", "SO", "SW",
    "NF", "NV", "NA", "W_URL", "W_EMAIL", "W_HASHTAG", "W_MENTION"
}

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
_kiwi_instance = None
_bm25_cache_index = None
_bm25_cache_corpus_hash = None
_legacy_warned = False


def _get_kiwi():
    global _kiwi_instance
    if _kiwi_instance is None and _KIWI_AVAILABLE:
        _kiwi_instance = Kiwi()
    return _kiwi_instance


def tokenize_korean(text: str) -> list[str]:
    """Tokenize Korean text using Kiwi morphological analyzer."""
    kiwi = _get_kiwi()
    if kiwi is None:
        raise ImportError("kiwipiepy is not available")

    analyzed = kiwi.analyze(text, top_n=1)
    if not analyzed or not analyzed[0]:
        return []

    tokens: list[str] = []
    for token in analyzed[0][0]:
        if token.tag in DROP_TAGS:
            continue
        form = token.lemma if token.lemma else token.form
        form = form.strip()
        if len(form) >= 1:
            tokens.append(form.lower())
    return tokens


def _get_corpus_hash(documents: list[Document]) -> str:
    import hashlib
    raw = "".join(f"{doc.id}{doc.title}{doc.text}" for doc in documents).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _get_or_build_bm25(documents: list[Document]) -> Any:
    global _bm25_cache_index, _bm25_cache_corpus_hash
    current_hash = _get_corpus_hash(documents)

    if _bm25_cache_index is not None and _bm25_cache_corpus_hash == current_hash:
        return _bm25_cache_index

    tokenized_docs = [
        tokenize_korean(f"{doc.title} {doc.text}")
        for doc in documents
    ]

    bm25 = BM25()
    bm25.index(tokenized_docs, show_progress=False)

    _bm25_cache_index = bm25
    _bm25_cache_corpus_hash = current_hash
    return bm25


def retrieve(question: str, documents: list[Document], config: Config) -> EvidencePack:
    """Rank, build evidence, and return an EvidencePack for a question."""
    scored = rank(question, documents, config.rag.top_k)
    return build_evidence(question, scored, config)


def rank(question: str, documents: list[Document], k: int = 8) -> list[ScoredDocument]:
    """Score and rank documents by relevance to the question."""
    global _legacy_warned
    bm25_failed = False

    if _KIWI_AVAILABLE and _BM25S_AVAILABLE:
        try:
            bm25 = _get_or_build_bm25(documents)
            query_tokens = tokenize_korean(question)
            if not query_tokens:
                logger.debug("Empty query_tokens from tokenize_korean, returning empty results")
                return []

            results = bm25.retrieve([query_tokens], k=k, show_progress=False)
            indices = results.documents[0]
            scores = results.scores[0]

            return [
                ScoredDocument(document=documents[idx], score=float(scores[i]))
                for i, idx in enumerate(indices)
                if float(scores[i]) > 0.0
            ]
        except Exception as e:
            logger.warning("BM25 retrieval failed, falling back to legacy lexical. Error: %s", e)
            bm25_failed = True

    if (bm25_failed or not (_KIWI_AVAILABLE and _BM25S_AVAILABLE)) and not _legacy_warned:
        warnings.warn(
            "Lexical retrieval is deprecated and will be removed in a future release. "
            "Install kiwipiepy and bm25s for the default Korean BM25 retrieval.",
            DeprecationWarning,
            stacklevel=2,
        )
        _legacy_warned = True

    query_tokens = set(_tokens(question))
    if not query_tokens:
        logger.debug("Empty query_tokens from fallback _tokens, returning empty results")
        return []

    scored = [
        ScoredDocument(document=document, score=_score_document(query_tokens, document))
        for document in documents
    ]
    scored = [row for row in scored if row.score > 0]
    scored.sort(key=lambda row: (-row.score, row.document.id))
    return scored[:k]


def build_evidence(question: str, scored: list[ScoredDocument], config: Config) -> EvidencePack:
    """Build an EvidencePack from scored documents."""
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
    """Render an EvidencePack as a formatted string."""
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

