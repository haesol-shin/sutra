from __future__ import annotations

from sutra.models import Document
from sutra.retrieval import rank


def test_rank_uses_text_relevance_not_label_metadata() -> None:
    docs = [
        Document(
            id="metadata-only",
            title="식단",
            text="학생식당 메뉴 안내입니다.",
            metadata={"label": "calendar", "domain": "academic_calendar"},
        ),
        Document(
            id="text-match",
            title="학사 일정",
            text="수강신청은 2월 1일에 시작합니다.",
            metadata={"label": "dining", "domain": "dining"},
        ),
    ]

    ranked = rank("수강신청 일정", docs, k=2)

    assert [row.document.id for row in ranked] == ["text-match"]
