from __future__ import annotations

import re


WHITESPACE_RE = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def clip_text(text: str, *, max_chars: int | None = None) -> str:
    normalized = normalize_whitespace(text)
    if max_chars is None or len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars].rsplit(" ", 1)[0].strip()
