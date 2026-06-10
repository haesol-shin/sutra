"""Qwen3 embedding retrieval helper for CNU workspace experiments."""

import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np

from sutra.config import Config
from sutra.models import Document, Evidence, EvidencePack

from _shared import _clip, _normalize_dict, compute_corpus_hash

logger = logging.getLogger(__name__)

_SENTENCE_TRANSFORMERS_AVAILABLE = False
SentenceTransformer = None
try:
    from sentence_transformers import SentenceTransformer as _ST

    SentenceTransformer = _ST
    _SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    pass


def check_deps() -> dict[str, Any]:
    status: dict[str, Any] = {
        "sentence_transformers_available": _SENTENCE_TRANSFORMERS_AVAILABLE,
        "sentence_transformers_version": None,
        "transformers_version": None,
    }
    if _SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            from importlib.metadata import version

            status["sentence_transformers_version"] = version("sentence-transformers")
        except Exception:
            pass
    try:
        import transformers
        status["transformers_version"] = transformers.__version__
    except Exception:
        pass
    return status


def load_embedding_model(
    model_name: str = "Qwen/Qwen3-Embedding-0.6B",
    device: str = "cpu",
):
    if not _SENTENCE_TRANSFORMERS_AVAILABLE:
        raise ImportError(
            "sentence-transformers is not installed.\n"
            "Install: uv pip install sentence-transformers>=2.7.0\n"
            "Also ensure: transformers>=4.51.0 is available."
        )
    logger.info("Loading embedding model %s on %s...", model_name, device)
    t0 = time.time()
    model = SentenceTransformer(model_name, device=device)
    elapsed = time.time() - t0
    logger.info("Model loaded in %.1fs on %s", elapsed, model.device)
    return model


def get_cache_dir(workspace_path: Path) -> Path:
    return workspace_path.resolve().parent / ".cache" / "embeddings"


def get_cached_embeddings(
    documents: list[Document],
    model,
    cache_dir: Path,
) -> tuple[np.ndarray, dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    meta_path = cache_dir / "cache_meta.json"
    emb_path = cache_dir / "dense_embeddings.npy"

    current_hash = compute_corpus_hash(documents)
    current_size = len(documents)
    current_model_name = get_model_name(model)

    if meta_path.exists() and emb_path.exists():
        try:
            meta: dict[str, Any] = json.loads(
                meta_path.read_text("utf-8")
            )
            if (
                meta.get("corpus_hash") == current_hash
                and meta.get("corpus_size") == current_size
                and meta.get("model_name") == current_model_name
            ):
                embeddings = np.load(str(emb_path)).astype(np.float32)
                meta["cache_hit"] = True
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
    return embeddings, meta


def dense_retrieve(
    query: str,
    documents: list[Document],
    model,
    embeddings: np.ndarray,
    config: Config,
) -> EvidencePack:
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


def normalize_scores(values: list[float]) -> list[float]:
    if not values:
        return []
    mn, mx = min(values), max(values)
    if mx - mn < 1e-12:
        return [0.0] * len(values)
    return [(v - mn) / (mx - mn) for v in values]


def get_model_name(model) -> str:
    try:
        return str(model.model_card_data.model_id)
    except Exception:
        pass
    return "Qwen/Qwen3-Embedding-0.6B"


def get_model_device(model) -> str:
    return str(getattr(model, "_target_device", "unknown"))


def _doc_text(doc: Document) -> str:
    return f"{doc.title} {doc.text}"
