"""
Korean BM25 retrieval using Kiwi morphological tokenizer + bm25s.
Experimental — not promoted to src/sutra.
"""

import logging
from pathlib import Path
from typing import Any

import numpy as np

from sutra.config import Config
from sutra.models import Document, Evidence, EvidencePack

logger = logging.getLogger(__name__)

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


def check_deps() -> dict[str, Any]:
    status: dict[str, Any] = {
        "kiwipiepy_available": _KIWI_AVAILABLE,
        "kiwipiepy_version": None,
        "bm25s_available": _BM25S_AVAILABLE,
        "bm25s_version": None,
    }
    if _KIWI_AVAILABLE:
        try:
            from importlib.metadata import version

            status["kiwipiepy_version"] = version("kiwipiepy")
        except Exception:
            pass
    if _BM25S_AVAILABLE:
        try:
            from importlib.metadata import version

            status["bm25s_version"] = version("bm25s")
        except Exception:
            status["bm25s_version"] = "0.3.9"
    return status


# ── Kiwi global instance (lazy-loaded) ──────────────────────────

_kiwi_instance = None


def _get_kiwi():
    global _kiwi_instance
    if _kiwi_instance is None and _KIWI_AVAILABLE:
        _kiwi_instance = Kiwi()
    return _kiwi_instance


# ── POS tag sets (review-approved) ──────────────────────────────

KEEP_TAGS: set[str] = {
    "NNG",  # common noun
    "NNP",  # proper noun
    "NNB",  # dependent noun
    "NR",   # numeral
    "SN",   # number
    "SL",   # foreign/alphabet
    "SH",   # hanja
    "VV",   # verb (stem only)
    "VA",   # adjective (stem only)
    "MM",   # determiner/adnominal
    "MAG",  # general adverb
    "MAJ",  # conjunctive adverb
}

# Explicitly dropped per review: VCP, VCN, VX are too common (copula/auxiliary)
# and reduce BM25 discriminative power.
DROP_TAGS: set[str] = {
    "JKS", "JKC", "JKG", "JKO", "JKB", "JKV", "JKQ",  # case particles
    "JX",   # auxiliary particles
    "JC",   # conjunctive particles
    "EP", "EF", "EC", "ETN", "ETM",  # endings
    "XSN", "XSV", "XSA",  # derivational suffixes
    "VCP", "VCN", "VX",   # copula/auxiliary (dropped per review)
    "SF", "SP", "SS", "SE", "SO",  # punctuation
    "SW",   # other symbols
    "NF", "NV", "NA",  # unknown / not analyzed
    "W_URL", "W_EMAIL", "W_HASHTAG", "W_MENTION",  # web tokens
}


# ── Compound merge table ────────────────────────────────────────
#
# Kiwi may split some campus-specific compounds into separate tokens.
# This table merges adjacent token sequences back into compounds.
#
# Caveat: This is a small explicit table for high-value CNU terms only.
# Adding too many entries may overfit to the 39-set. Extend with caution.
COMPOUND_MAP: dict[tuple[str, ...], str] = {
    ("수강", "신청"): "수강신청",
    ("월평", "역"): "월평역",
    ("제", "2", "학생", "회관"): "제2학생회관",
    ("2", "학생", "회관"): "제2학생회관",
    ("컴퓨터", "인공지능", "학부"): "컴퓨터인공지능학부",
    ("컴퓨터", "융합", "학부"): "컴퓨터융합학부",
    ("인공지능", "학과"): "인공지능학과",
    ("캡스톤", "디자인"): "캡스톤디자인",
    ("통학", "버스"): "통학버스",
    ("졸업", "학점"): "졸업학점",
    ("130", "학점"): "130학점",
    ("셔틀", "버스"): "셔틀버스",
    ("학생", "회관"): "학생회관",
    ("컴퓨터", "공학", "과"): "컴퓨터공학과",
}


def _merge_compounds(tokens: list[str]) -> list[str]:
    """Merge adjacent tokens that form known compounds."""
    if not tokens:
        return tokens

    merged: list[str] = tokens[:1]
    i = 1
    while i < len(tokens):
        # Try to find longest matching compound starting at i-1 or i
        matched = False
        # Check if the last merged token + current token(s) form a compound
        for length in range(min(len(tokens) - i + 1, 5), 0, -1):
            window = tuple(merged[-1:] + tokens[i:i + length - 1]) if merged else tuple(tokens[i:i+length])
            if window in COMPOUND_MAP:
                merged[-1:] = [COMPOUND_MAP[window]]
                i += length - 1
                matched = True
                break
        if not matched:
            merged.append(tokens[i])
            i += 1
    return merged


# ── Alias map (query-side expansion only, not index-side) ──────
#
# Caveat: This is a small explicit map for high-value CNU synonyms.
# Department aliases (컴퓨터인공지능학부 ↔ 컴퓨터융합학부) should be
# verified for false positives beyond the 39-set.
ALIAS_MAP: dict[str, list[str]] = {
    "학식": ["메뉴", "식단"],
    "메뉴": ["식단", "학식"],
    "식단": ["학식", "메뉴"],
    "셔틀": ["통학버스", "셔틀버스"],
    "통학버스": ["셔틀", "셔틀버스"],
    "셔틀버스": ["셔틀", "통학버스"],
    "컴퓨터인공지능학부": ["컴퓨터융합학부", "인공지능학과"],
    "컴퓨터융합학부": ["컴퓨터인공지능학부", "인공지능학과"],
    "졸업": ["졸업요건", "졸업학점"],
}


def _expand_aliases(tokens: list[str]) -> list[str]:
    """Expand query tokens with alias terms (query-side only)."""
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        if token in ALIAS_MAP:
            alias_tokens = ALIAS_MAP[token]
            expanded.extend(alias_tokens[:2])
    return expanded


# ── Tokenization ────────────────────────────────────────────────


def tokenize_korean(text: str, use_aliases: bool = False) -> list[str]:
    """Kiwi-based Korean tokenization following review-approved policy.

    - Keeps content-bearing POS tags only.
    - Drops VCP/VCN/VX (copula/auxiliary — too common for BM25).
    - Length filter: only drops zero-length tokens after stripping.
    - Merges known compounds from COMPOUND_MAP.
    - Optionally expands aliases (query-side only).
    """
    kiwi = _get_kiwi()
    if kiwi is None:
        raise ImportError("kiwipiepy is not available")

    raw_tokens: list[str] = []
    analyzed = kiwi.analyze(text, top_n=1)
    if not analyzed or not analyzed[0]:
        return []

    for token in analyzed[0][0]:
        tag = token.tag
        if tag in DROP_TAGS:
            continue
        form = token.lemma if token.lemma else token.form
        form = form.strip()
        if len(form) < 1:
            continue
        raw_tokens.append(form.lower())

    merged = _merge_compounds(raw_tokens)

    if use_aliases:
        merged = _expand_aliases(merged)

    return merged


# ── BM25 index ──────────────────────────────────────────────────


def compute_corpus_hash(documents: list[Document]) -> str:
    import hashlib
    raw = "".join(doc.id for doc in documents).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def build_bm25_index(
    documents: list[Document],
) -> tuple[Any, dict[str, Any]]:
    """Build BM25 index from documents using Kiwi tokenization.

    Note: bm25s 0.3.9 save/load does not properly round-trip the internal
    scores CSC matrix (see eval_39 review). Cache is omitted; for 355 docs
    the rebuild takes < 30s and the BM25 scoring is near-instant.

    Returns (bm25_instance, metadata_dict).
    """
    tokenized_docs = [
        tokenize_korean(f"{doc.title} {doc.text}", use_aliases=False)
        for doc in documents
    ]

    bm25 = BM25()
    bm25.index(tokenized_docs)

    meta: dict[str, Any] = {
        "corpus_size": len(documents),
        "corpus_hash": compute_corpus_hash(documents),
    }

    return bm25, meta


# ── Retrieval ────────────────────────────────────────────────────


def bm25_retrieve(
    query: str,
    documents: list[Document],
    bm25,
    config: Config,
) -> EvidencePack:
    query_tokens = tokenize_korean(query, use_aliases=True)
    if not query_tokens:
        return EvidencePack(question=query, items=[])

    results = bm25.retrieve([query_tokens], k=config.rag.top_k, show_progress=False)
    indices = results.documents[0]  # shape (k,)
    scores = results.scores[0]      # shape (k,)

    items = [
        Evidence(
            id=documents[idx].id,
            title=documents[idx].title,
            text=_clip(documents[idx].text, config.rag.max_fact_chars),
            source_url=documents[idx].source_url,
            source_name=documents[idx].source_name,
            score=float(scores[i]),
            metadata=documents[idx].metadata,
        )
        for i, idx in enumerate(indices)
    ]
    return EvidencePack(question=query, items=items)


# ── Hybrid BM25 + Dense ─────────────────────────────────────────


def hybrid_bm25_dense(
    query: str,
    documents: list[Document],
    bm25,
    model,
    embeddings: np.ndarray,
    config: Config,
) -> EvidencePack:
    from embedding_retrieval import dense_retrieve

    bm25_pack = bm25_retrieve(query, documents, bm25, config)
    dense_pack = dense_retrieve(query, documents, model, embeddings, config)

    pool: dict[str, dict[str, Any]] = {}
    for item in bm25_pack.items:
        pool[item.id] = {"item": item, "bm25": item.score, "dense": None}
    for item in dense_pack.items:
        if item.id in pool:
            pool[item.id]["dense"] = item.score
        else:
            pool[item.id] = {"item": item, "bm25": None, "dense": item.score}

    if not pool:
        return EvidencePack(question=query, items=[])

    bm25_norm = _normalize_dict({k: v["bm25"] for k, v in pool.items()})
    dense_norm = _normalize_dict({k: v["dense"] for k, v in pool.items()})

    for doc_id in pool:
        bn = bm25_norm.get(doc_id, 0.0)
        dn = dense_norm.get(doc_id, 0.0)
        pool[doc_id]["final"] = 0.5 * bn + 0.5 * dn

    sorted_pool = sorted(
        pool.values(),
        key=lambda x: (-x["final"], x["item"].id),
    )[: config.rag.top_k]

    items = [
        Evidence(
            id=entry["item"].id,
            title=entry["item"].title,
            text=entry["item"].text,
            source_url=entry["item"].source_url,
            source_name=entry["item"].source_name,
            score=entry["final"],
            metadata=entry["item"].metadata,
        )
        for entry in sorted_pool
    ]
    return EvidencePack(question=query, items=items)


# ── Normalization ────────────────────────────────────────────────


def _normalize_dict(score_dict: dict[str, float | None]) -> dict[str, float]:
    valid = {k: v for k, v in score_dict.items() if v is not None}
    if not valid:
        return {k: 0.0 for k in score_dict}
    vals = list(valid.values())
    mn, mx = min(vals), max(vals)
    if mx - mn < 1e-12:
        return {k: 0.0 for k in score_dict}
    result = {k: (v - mn) / (mx - mn) for k, v in valid.items()}
    for k in score_dict:
        result.setdefault(k, 0.0)
    return result


# ── Helpers ──────────────────────────────────────────────────────


def get_cache_dir(workspace_path: Path) -> Path:
    return workspace_path.resolve().parent / ".cache" / "bm25"


def _clip(text: str, limit: int) -> str:
    stripped = " ".join(text.split())
    if len(stripped) <= limit:
        return stripped
    return stripped[: max(0, limit - 1)].rstrip() + "..."


def get_tokenizer_config() -> dict[str, Any]:
    return {
        "pipeline": "kiwi_analyze → tag_filter → stem_extract → lowercase → compound_merge → [alias_expand]",
        "keep_tags": sorted(KEEP_TAGS),
        "drop_tags": sorted(DROP_TAGS),
        "compound_map": {str(k): v for k, v in COMPOUND_MAP.items()},
        "alias_map": ALIAS_MAP,
        "length_filter_policy": "drop if len(token.strip()) < 1",
        "notes": [
            "VCP, VCN, VX dropped per review (too common, hurt BM25 discrimination).",
            "Compound merge is a small explicit table for high-value CNU terms only.",
            "Alias expansion is query-side only; index remains stable.",
            "Department aliases may overfit; verify beyond 39-set before promoting.",
        ],
    }
