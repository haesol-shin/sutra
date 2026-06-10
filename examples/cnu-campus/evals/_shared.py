"""Shared utility functions for CNU eval scripts."""

import hashlib

from sutra.models import Document


def compute_corpus_hash(documents: list[Document]) -> str:
    raw = "".join(doc.id for doc in documents).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


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


def _clip(text: str, limit: int) -> str:
    stripped = " ".join(text.split())
    if len(stripped) <= limit:
        return stripped
    return stripped[: max(0, limit - 1)].rstrip() + "..."
