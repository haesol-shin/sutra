from __future__ import annotations

import json
from pathlib import Path

from sutra.models import Evidence
from sutra.tracelog import append_chat_trace, append_feedback


def test_append_chat_trace_writes_required_jsonl_fields(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "chat_trace.jsonl"
    evidence = [
        Evidence(
            id="calendar-1",
            title="수강신청 일정",
            text="수강신청은 2월 1일에 시작합니다.",
            score=2.5,
        ),
        Evidence(
            id="calendar-2",
            title="정정 기간",
            text="수강신청 정정은 3월 4일입니다.",
        ),
    ]

    append_chat_trace(
        path,
        source="ui",
        question="수강신청 언제 시작해?",
        answer="수강신청은 2월 1일에 시작합니다.",
        evidence=evidence,
        tools_called=["fetch_cafeteria_menu"],
        tool_args=[{"date": "2026-06-11"}],
        mode="stream",
        latency_ms=123,
        usage={"total_tokens": 42},
        error=None,
    )

    rows = path.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert set(row) == {
        "ts",
        "source",
        "question",
        "answer",
        "doc_ids",
        "doc_scores",
        "tools_called",
        "tool_args",
        "mode",
        "latency_ms",
        "usage",
        "error",
    }
    assert row["source"] == "ui"
    assert row["question"] == "수강신청 언제 시작해?"
    assert row["answer"] == "수강신청은 2월 1일에 시작합니다."
    assert row["doc_ids"] == ["calendar-1", "calendar-2"]
    assert row["doc_scores"] == [2.5, None]
    assert row["tools_called"] == ["fetch_cafeteria_menu"]
    assert row["tool_args"] == [{"date": "2026-06-11"}]
    assert row["mode"] == "stream"
    assert row["latency_ms"] == 123
    assert row["usage"] == {"total_tokens": 42}
    assert row["error"] is None


def test_append_feedback_writes_turn_identifying_jsonl_fields(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "chat_trace.jsonl"

    append_feedback(
        path,
        question="학생식당 메뉴 알려줘",
        answer="오늘 학생식당 메뉴는 김치찌개입니다.",
        rating="helpful",
        comment="출처까지 있어서 좋았습니다.",
    )

    rows = path.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert set(row) == {
        "ts",
        "type",
        "question",
        "answer",
        "rating",
        "comment",
    }
    assert row["type"] == "feedback"
    assert row["question"] == "학생식당 메뉴 알려줘"
    assert row["answer"] == "오늘 학생식당 메뉴는 김치찌개입니다."
    assert row["rating"] == "helpful"
    assert row["comment"] == "출처까지 있어서 좋았습니다."
