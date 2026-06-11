from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from sutra.models import Evidence

TraceSource = Literal["ui", "batch"]
FeedbackRating = Literal["helpful", "unhelpful", "comment"]


def append_chat_trace(
    path: str | Path,
    *,
    source: TraceSource,
    question: str,
    answer: str,
    evidence: list[Evidence],
    tools_called: list[str] | None = None,
    tool_args: list[dict[str, Any]] | None = None,
    mode: str,
    latency_ms: int,
    usage: dict[str, Any] | None = None,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Append one chat/debug trace row as UTF-8 JSONL."""
    trace_path = Path(path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "question": question,
        "answer": answer,
        "doc_ids": [item.id for item in evidence],
        "doc_scores": [item.score for item in evidence],
        "tools_called": tools_called or [],
        "tool_args": tool_args or [],
        "mode": mode,
        "latency_ms": latency_ms,
        "usage": usage,
        "error": error,
    }
    if extra:
        row.update(extra)
    with trace_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
        f.write("\n")


def append_feedback(
    path: str | Path,
    *,
    question: str,
    answer: str,
    rating: FeedbackRating,
    comment: str | None = None,
) -> None:
    """Append one UI feedback row as UTF-8 JSONL."""
    trace_path = Path(path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": "feedback",
        "question": question,
        "answer": answer,
        "rating": rating,
        "comment": comment,
    }
    with trace_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
        f.write("\n")


def default_trace_path(root: str | Path) -> Path:
    return Path(root) / "logs" / "chat_trace.jsonl"
