from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
import logging
import re
import time
import warnings
from pathlib import Path
from typing import Any

from sutra.config import Config
from sutra.models import Document, Evidence, EvidencePack, ScoredDocument

logger = logging.getLogger(__name__)

# Domains whose docs are snapshot/fallback-only and must NOT pollute general RAG
# search. notices live behind live tools (fetch_recent_notices); their indexed
# snapshots are reserved for the forced-tool fallback path, which calls retrieve()
# with exclude_domains=set() to re-include them. dining is removed from the corpus
# entirely (tool-only). Keep this the single policy point for domain exclusion.
GENERAL_SEARCH_EXCLUDED_DOMAINS = frozenset({"notices"})

# Soft dependencies checking
_KIWI_AVAILABLE = False
_BM25S_AVAILABLE = False
_SENTENCE_TRANSFORMERS_AVAILABLE = False
_NUMPY_AVAILABLE = False
Kiwi = None
BM25 = None
SentenceTransformer = None

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

try:
    from sentence_transformers import SentenceTransformer as _ST
    SentenceTransformer = _ST
    _SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    pass

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    np = None  # type: ignore[assignment]

DROP_TAGS: set[str] = {
    "JKS", "JKC", "JKG", "JKO", "JKB", "JKV", "JKQ",
    "JX",
    "JC",
    "EP", "EF", "EC", "ETN", "ETM",
    "XSN", "XSV", "XSA",
    "VCP", "VCN", "VX",
    "SF", "SP", "SS", "SE", "SO",
    "SW",
    "NF", "NV", "NA",
    "W_URL", "W_EMAIL", "W_HASHTAG", "W_MENTION",
}

_kiwi_instance = None
_bm25_cache_index = None
_bm25_cache_corpus_hash = None
_embedding_model = None
_embedding_cache_embeddings = None
_embedding_cache_corpus_hash = None
_legacy_warned = False


def _get_kiwi():
    global _kiwi_instance
    if _kiwi_instance is None and _KIWI_AVAILABLE:
        _kiwi_instance = Kiwi()
    return _kiwi_instance


def _load_token_config(config: Config) -> dict | None:
    if config.rag.token_config is None:
        return None
    token_config_path = Path(config.rag.token_config)
    if not token_config_path.exists():
        logger.warning("token_config path does not exist: %s", token_config_path)
        return None
    try:
        return json.loads(token_config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to load token_config from %s: %s", token_config_path, exc)
        return None


def _merge_compounds(tokens: list[str], compounds: dict[str, str]) -> list[str]:
    if not tokens:
        return tokens

    compound_lookup: dict[tuple[str, ...], str] = {}
    for key_str, value in compounds.items():
        compound_lookup[tuple(key_str.split(","))] = value

    merged: list[str] = tokens[:1]
    i = 1
    while i < len(tokens):
        matched = False
        for length in range(min(len(tokens) - i + 1, 5), 0, -1):
            window = tuple(merged[-1:] + tokens[i:i + length - 1]) if merged else tuple(tokens[i:i + length])
            if window in compound_lookup:
                merged[-1:] = [compound_lookup[window]]
                i += length - 1
                matched = True
                break
        if not matched:
            merged.append(tokens[i])
            i += 1
    return merged


def _expand_aliases(tokens: list[str], aliases: dict[str, list[str]]) -> list[str]:
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        if token in aliases:
            expanded.extend(aliases[token][:2])
    return expanded


def tokenize_korean(text: str, token_config: dict | None = None, use_aliases: bool = False) -> list[str]:
    """Kiwi-based Korean tokenization with optional compound merging and alias expansion."""
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

    if token_config and "compounds" in token_config:
        raw_tokens = _merge_compounds(raw_tokens, token_config["compounds"])

    if use_aliases and token_config and "aliases" in token_config:
        raw_tokens = _expand_aliases(raw_tokens, token_config["aliases"])

    return raw_tokens


def _get_corpus_hash(documents: list[Document]) -> str:
    raw = "".join(f"{doc.id}{doc.title}{doc.text}" for doc in documents).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def build_bm25_index(
    documents: list[Document],
    token_config: dict | None = None,
) -> tuple[Any, dict[str, Any]]:
    if not _BM25S_AVAILABLE:
        raise ImportError("bm25s is not available")

    tokenized_docs = [
        tokenize_korean(f"{doc.title} {doc.text}", token_config=token_config, use_aliases=False)
        for doc in documents
    ]

    bm25 = BM25()
    bm25.index(tokenized_docs)

    meta: dict[str, Any] = {
        "corpus_size": len(documents),
        "corpus_hash": _get_corpus_hash(documents),
    }

    return bm25, meta


def _get_or_build_bm25(documents: list[Document], token_config: dict | None = None) -> Any:
    global _bm25_cache_index, _bm25_cache_corpus_hash
    current_hash = _get_corpus_hash(documents)

    if _bm25_cache_index is not None and _bm25_cache_corpus_hash == current_hash:
        return _bm25_cache_index

    bm25, _meta = build_bm25_index(documents, token_config=token_config)

    _bm25_cache_index = bm25
    _bm25_cache_corpus_hash = current_hash
    return bm25


def bm25_retrieve(
    query: str,
    documents: list[Document],
    bm25: Any,
    config: Config,
    token_config: dict | None = None,
) -> EvidencePack:
    query_tokens = tokenize_korean(query, token_config=token_config, use_aliases=True)
    if not query_tokens:
        return EvidencePack(question=query, items=[])

    results = bm25.retrieve([query_tokens], k=config.rag.top_k, show_progress=False)
    indices = results.documents[0]
    scores = results.scores[0]

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


def load_embedding_model(
    model_name: str = "Qwen/Qwen3-Embedding-0.6B",
    device: str = "cpu",
):
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    if not _SENTENCE_TRANSFORMERS_AVAILABLE:
        raise ImportError(
            "sentence-transformers is not installed.\n"
            "Install: uv pip install sentence-transformers>=2.7.0\n"
            "Also ensure: transformers>=4.51.0 is available."
        )
    logger.info("Loading embedding model %s on %s...", model_name, device)
    t0 = time.time()
    _embedding_model = SentenceTransformer(model_name, device=device)
    elapsed = time.time() - t0
    logger.info("Model loaded in %.1fs on %s", elapsed, _embedding_model.device)
    return _embedding_model


def get_cache_dir(workspace_path: Path, subdir: str = "embeddings") -> Path:
    return workspace_path / ".cache" / subdir


def get_cached_embeddings(
    documents: list[Document],
    model,
    cache_dir: Path,
) -> tuple[Any, dict[str, Any]]:
    global _embedding_cache_embeddings, _embedding_cache_corpus_hash
    if not _NUMPY_AVAILABLE:
        raise ImportError("numpy is not available")

    current_hash = _get_corpus_hash(documents)
    current_size = len(documents)
    current_model_name = get_model_name(model)

    cache_dir.mkdir(parents=True, exist_ok=True)
    meta_path = cache_dir / "cache_meta.json"
    emb_path = cache_dir / "dense_embeddings.npy"

    if _embedding_cache_embeddings is not None and _embedding_cache_corpus_hash == current_hash:
        return _embedding_cache_embeddings, {"cache_hit": True, "corpus_hash": current_hash}

    if meta_path.exists() and emb_path.exists():
        try:
            meta: dict[str, Any] = json.loads(meta_path.read_text("utf-8"))
            if (
                meta.get("corpus_hash") == current_hash
                and meta.get("corpus_size") == current_size
                and meta.get("model_name") == current_model_name
            ):
                embeddings = np.load(str(emb_path)).astype(np.float32)
                meta["cache_hit"] = True
                _embedding_cache_embeddings = embeddings
                _embedding_cache_corpus_hash = current_hash
                return embeddings, meta
        except Exception:
            pass

    doc_texts = [_doc_text(d) for d in documents]
    logger.info("Encoding %d documents...", current_size)
    t0 = time.time()
    embeddings = model.encode(doc_texts, show_progress_bar=True).astype(np.float32)
    elapsed = time.time() - t0
    logger.info("Encoded %s in %.1fs", embeddings.shape, elapsed)

    np.save(str(emb_path), embeddings)
    meta = {
        "model_name": get_model_name(model),
        "embedding_dim": int(embeddings.shape[1]),
        "corpus_size": current_size,
        "corpus_hash": current_hash,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cache_hit": False,
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), "utf-8")
    _embedding_cache_embeddings = embeddings
    _embedding_cache_corpus_hash = current_hash
    return embeddings, meta


def dense_retrieve(
    query: str,
    documents: list[Document],
    model,
    embeddings,
    config: Config,
) -> EvidencePack:
    if not _NUMPY_AVAILABLE:
        raise ImportError("numpy is not available")

    query_emb = model.encode([query], prompt_name="query")[0]
    scores = np.dot(embeddings, query_emb)
    k = config.rag.top_k
    top_indices = np.argsort(scores)[::-1][:k]
    items = [
        Evidence(
            id=documents[i].id,
            title=documents[i].title,
            text=_clip(documents[i].text, config.rag.max_fact_chars),
            source_url=documents[i].source_url,
            source_name=documents[i].source_name,
            score=float(scores[i]),
            metadata=documents[i].metadata,
        )
        for i in top_indices
    ]
    return EvidencePack(question=query, items=items)


def hybrid_combine(
    lexical_pack: EvidencePack,
    dense_pack: EvidencePack,
    config: Config,
) -> EvidencePack:
    pool: dict[str, dict[str, Any]] = {}
    for item in lexical_pack.items:
        pool[item.id] = {"item": item, "lexical": item.score or 0.0, "dense": None}
    for item in dense_pack.items:
        if item.id in pool:
            pool[item.id]["dense"] = item.score or 0.0
        else:
            pool[item.id] = {"item": item, "lexical": None, "dense": item.score or 0.0}

    if not pool:
        return EvidencePack(question=lexical_pack.question, items=[])

    lex_norm = _normalize_dict({k: v["lexical"] for k, v in pool.items()})
    dense_norm = _normalize_dict({k: v["dense"] for k, v in pool.items()})

    for doc_id in pool:
        ln = lex_norm.get(doc_id, 0.0)
        dn = dense_norm.get(doc_id, 0.0)
        pool[doc_id]["final"] = 0.5 * ln + 0.5 * dn

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
    return EvidencePack(question=lexical_pack.question, items=items)


def hybrid_bm25_dense(
    query: str,
    documents: list[Document],
    bm25: Any,
    model,
    embeddings,
    config: Config,
    token_config: dict | None = None,
) -> EvidencePack:
    bm25_pack = bm25_retrieve(query, documents, bm25, config, token_config=token_config)
    dense_pack = dense_retrieve(query, documents, model, embeddings, config)
    return hybrid_combine(bm25_pack, dense_pack, config)


def retrieve(
    question: str,
    documents: list[Document],
    config: Config,
    exclude_domains: "frozenset[str] | set[str] | None" = None,
) -> EvidencePack:
    """Rank, build evidence, and return an EvidencePack for a question.

    Dispatches on config.rag.backend:
    - "bm25" (default): Kiwi BM25 with optional token_config compound/alias support
    - "qwen3": Qwen3-Embedding dense retrieval
    - "hybrid": BM25 + Qwen3 combined (0.5/0.5 weight)
    - "lexical": Legacy regex-based fallback

    exclude_domains: domains dropped from general search. Defaults to
    GENERAL_SEARCH_EXCLUDED_DOMAINS ({"notices"}); pass an empty set to include
    every domain (used by the forced-tool fallback re-search path).
    """
    if exclude_domains is None:
        exclude_domains = GENERAL_SEARCH_EXCLUDED_DOMAINS
    if exclude_domains:
        documents = [
            doc
            for doc in documents
            if (doc.domain or (doc.metadata or {}).get("domain")) not in exclude_domains
        ]
    retrieval_question = _expand_relative_date_query(question, config.workspace.timezone)
    backend = config.rag.backend
    token_config = _load_token_config(config)
    bm25_pack = EvidencePack(question=question, items=[])
    dense_pack = EvidencePack(question=question, items=[])

    if backend in ("bm25", "hybrid") and _KIWI_AVAILABLE and _BM25S_AVAILABLE:
        bm25 = _get_or_build_bm25(documents, token_config=token_config)
        try:
            bm25_pack = _with_question(
                bm25_retrieve(retrieval_question, documents, bm25, config, token_config=token_config),
                question,
            )
        except Exception as e:
            logger.warning("BM25 retrieval failed: %s", e)
            bm25_pack = EvidencePack(question=question, items=[])
    else:
        bm25_pack = EvidencePack(question=question, items=[])

    if backend == "bm25":
        if bm25_pack.items:
            return bm25_pack
        # Fall through to lexical for bm25 if no results or deps unavailable
        if not (_KIWI_AVAILABLE and _BM25S_AVAILABLE):
            return _with_question(_lexical_retrieve(retrieval_question, documents, config), question)

    if backend in ("qwen3", "hybrid"):
        if not _SENTENCE_TRANSFORMERS_AVAILABLE:
            if backend == "qwen3":
                raise ImportError("sentence-transformers is not available for qwen3 backend")
            logger.warning("sentence-transformers not available, hybrid falling back to BM25")
            return bm25_pack

        try:
            model = load_embedding_model()
            cache_dir = get_cache_dir(config.root / ".cache")
            embeddings, _cache_meta = get_cached_embeddings(documents, model, cache_dir)
            dense_pack = _with_question(
                dense_retrieve(retrieval_question, documents, model, embeddings, config),
                question,
            )
        except Exception as e:
            logger.warning("Dense retrieval failed: %s", e)
            dense_pack = EvidencePack(question=question, items=[])

    if backend == "qwen3":
        if dense_pack.items:
            return dense_pack
        return bm25_pack

    if backend == "hybrid":
        if bm25_pack.items and dense_pack.items:
            return hybrid_combine(bm25_pack, dense_pack, config)
        if bm25_pack.items:
            return bm25_pack
        if dense_pack.items:
            return dense_pack
        return EvidencePack(question=question, items=[])

    if backend == "lexical":
        return _with_question(_lexical_retrieve(retrieval_question, documents, config), question)

    if bm25_pack.items:
        return bm25_pack
    return _with_question(_lexical_retrieve(retrieval_question, documents, config), question)


def _with_question(pack: EvidencePack, question: str) -> EvidencePack:
    if pack.question == question:
        return pack
    return EvidencePack(question=question, items=pack.items)


def _lexical_retrieve(question: str, documents: list[Document], config: Config) -> EvidencePack:
    global _legacy_warned
    if not _legacy_warned:
        warnings.warn(
            "Lexical retrieval is deprecated and will be removed in a future release. "
            "Install kiwipiepy and bm25s for the default Korean BM25 retrieval.",
            DeprecationWarning,
            stacklevel=2,
        )
        _legacy_warned = True

    query_tokens = set(_tokens(question))
    if not query_tokens:
        return EvidencePack(question=question, items=[])

    scored = [
        ScoredDocument(document=document, score=_score_document(query_tokens, document))
        for document in documents
    ]
    scored = [row for row in scored if row.score > 0]
    scored.sort(key=lambda row: (-row.score, row.document.id))
    scored = scored[: config.rag.top_k]
    return build_evidence(question, scored, config)


def rank(question: str, documents: list[Document], k: int = 8) -> list[ScoredDocument]:
    """Score and rank documents by relevance to the question (BM25 backend)."""
    global _legacy_warned

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

    if not _legacy_warned:
        warnings.warn(
            "Lexical retrieval is deprecated and will be removed in a future release. "
            "Install kiwipiepy and bm25s for the default Korean BM25 retrieval.",
            DeprecationWarning,
            stacklevel=2,
        )
        _legacy_warned = True

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


def check_deps() -> dict[str, Any]:
    status: dict[str, Any] = {
        "kiwipiepy_available": _KIWI_AVAILABLE,
        "kiwipiepy_version": None,
        "bm25s_available": _BM25S_AVAILABLE,
        "bm25s_version": None,
        "sentence_transformers_available": _SENTENCE_TRANSFORMERS_AVAILABLE,
        "sentence_transformers_version": None,
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
    if _SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            from importlib.metadata import version
            status["sentence_transformers_version"] = version("sentence-transformers")
        except Exception:
            pass
    return status


def get_model_name(model) -> str:
    try:
        return str(model.model_card_data.model_id)
    except Exception:
        pass
    return "Qwen/Qwen3-Embedding-0.6B"


def get_model_device(model) -> str:
    return str(getattr(model, "_target_device", "unknown"))


def get_tokenizer_config() -> dict[str, Any]:
    return {
        "pipeline": "kiwi_analyze -> tag_filter -> stem_extract -> lowercase -> compound_merge -> [alias_expand]",
        "drop_tags": sorted(DROP_TAGS),
    }


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


def _score_document(query_tokens: set[str], document: Document) -> float:
    title_tokens = set(_tokens(document.title))
    text_tokens = set(_tokens(document.text))
    return (
        3.0 * len(query_tokens & title_tokens)
        + 1.0 * len(query_tokens & text_tokens)
    )


_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_RELATIVE_DATE_OFFSETS: dict[str, int] = {
    "오늘": 0,
    "금일": 0,
    "내일": 1,
    "명일": 1,
    "모레": 2,
    "어제": -1,
}
_RELATIVE_DATE_RE = re.compile("|".join(_RELATIVE_DATE_OFFSETS))

# Week-level relative terms -> (start, end) day offsets from the current week's
# Monday (weekday()==0). The match regex is built longest-first so weekend
# variants ('이번 주말') win over plain-week variants ('이번 주').
_RELATIVE_WEEK_PATTERNS: dict[str, tuple[int, int]] = {
    "이번 주말": (5, 6),
    "이번주말": (5, 6),
    "다음 주말": (12, 13),
    "다음주말": (12, 13),
    "지난 주말": (-2, -1),
    "지난주말": (-2, -1),
    "이번 주": (0, 6),
    "이번주": (0, 6),
    "다음 주": (7, 13),
    "다음주": (7, 13),
    "지난 주": (-7, -1),
    "지난주": (-7, -1),
}
_RELATIVE_WEEK_RE = re.compile(
    "|".join(
        re.escape(term)
        for term in sorted(_RELATIVE_WEEK_PATTERNS, key=len, reverse=True)
    )
)


def _expand_relative_date_query(question: str, timezone_name: str) -> str:
    day_terms = _RELATIVE_DATE_RE.findall(question)
    week_terms = _RELATIVE_WEEK_RE.findall(question)
    if (not day_terms and not week_terms) or _ISO_DATE_RE.search(question):
        return question

    from sutra.prompts import get_current_time_str

    current_date_text = get_current_time_str(timezone_name).split()[0]
    current_date = datetime.strptime(current_date_text, "%Y-%m-%d").date()
    monday = current_date - timedelta(days=current_date.weekday())
    additions: list[str] = []
    seen: set[str] = set()

    def _add(day) -> None:
        date_text = day.strftime("%Y-%m-%d")
        if date_text not in question and date_text not in seen:
            additions.append(date_text)
            seen.add(date_text)

    for term in day_terms:
        _add(current_date + timedelta(days=_RELATIVE_DATE_OFFSETS[term]))
    for term in week_terms:
        start, end = _RELATIVE_WEEK_PATTERNS[term]
        for offset in range(start, end + 1):
            _add(monday + timedelta(days=offset))

    if not additions:
        return question
    return f"{question} {' '.join(additions)}"


def _tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN_RE.finditer(text)]


def _clip(text: str, limit: int) -> str:
    stripped = " ".join(text.split())
    if len(stripped) <= limit:
        return stripped
    return stripped[: max(0, limit - 1)].rstrip() + "..."


def _doc_text(doc: Document) -> str:
    return f"{doc.title} {doc.text}"
