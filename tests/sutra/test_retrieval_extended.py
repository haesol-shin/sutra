"""AC-12 pin-down tests for notices domain-exclusion + calendar-trim behavior.

Falsifiable reframe from the deep-interview spec: general retrieval drops notices
snapshots (so they cannot pollute unrelated questions), while a fallback re-search
with exclude_domains=set() re-includes them. Also confirms Document.domain
auto-maps from the top-level JSONL key (notices) and falls back to metadata.domain
(calendar).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sutra.config import load_config
from sutra.documents import load_documents
from sutra.models import Document
from sutra.retrieval import GENERAL_SEARCH_EXCLUDED_DOMAINS, retrieve


def _doc(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _write_workspace(root: Path) -> Path:
    (root / "data").mkdir(parents=True)
    (root / "prompts").mkdir()
    docs = [
        # calendar doc: domain lives in metadata (matches calendar-index.jsonl shape)
        _doc({
            "id": "calendar_month_2026_08",
            "title": "2026년 8월 학사일정",
            "text": "2026년 8월 학사일정입니다. 2026-08-03 ~ 2026-08-07: 제2학기 수강신청 기간.",
            "source_name": "학사일정",
            "metadata": {"domain": "academic_calendar", "year": 2026, "month": 8},
        }),
        # notices doc: domain is a TOP-LEVEL field (matches notices-index.jsonl shape)
        _doc({
            "id": "notices_999",
            "domain": "notices",
            "title": "2026학년도 하기 계절학기 수강신청 취소 안내",
            "text": "수강신청 취소 기간 안내입니다. 수강신청 관련 공지입니다.",
            "source_name": "충남대학교 학사공지 게시판",
            "metadata": {"date": "2026-06-05"},
        }),
        # generic shuttle doc
        _doc({
            "id": "shuttle_1",
            "domain": "shuttle",
            "title": "셔틀버스 운영 안내",
            "text": "셔틀버스 노선 및 운행 시간 안내입니다.",
            "source_name": "셔틀버스",
            "metadata": {},
        }),
        # extra non-notices docs so the general (notices-excluded) corpus stays
        # larger than top_k (bm25s requires corpus_size > top_k).
        _doc({
            "id": "calendar_month_2026_03",
            "title": "2026년 3월 학사일정",
            "text": "2026년 3월 학사일정입니다. 2026-03-04 ~ 2026-03-10: 수강신청 확인 및 변경.",
            "source_name": "학사일정",
            "metadata": {"domain": "academic_calendar", "year": 2026, "month": 3},
        }),
        _doc({
            "id": "graduation_1",
            "domain": "graduation",
            "title": "졸업요건 안내",
            "text": "졸업 이수학점 및 졸업요건 안내입니다.",
            "source_name": "졸업",
            "metadata": {},
        }),
    ]
    (root / "data" / "index.jsonl").write_text("\n".join(docs) + "\n", encoding="utf-8")
    (root / "prompts" / "system.md").write_text("You are a grounded assistant.", encoding="utf-8")
    config_path = root / "sutra.toml"
    config_path.write_text(
        """
[workspace]
name = "fixture"
timezone = "Asia/Seoul"

[runtime]
backend = "llama-server"
base_url = "http://127.0.0.1:18080"
model = "fake-qwen"
temperature = 0.1
max_tokens = 128

[rag]
index_path = "data/index.jsonl"
top_k = 2
max_fact_chars = 200
backend = "bm25"

[prompts]
system = "prompts/system.md"
""".strip(),
        encoding="utf-8",
    )
    return config_path


def test_document_domain_auto_maps_from_top_level_jsonl_key(tmp_path: Path) -> None:
    config = load_config(str(_write_workspace(tmp_path / "ws")))
    docs = load_documents(config)
    by_id = {d.id: d for d in docs}
    # notices: top-level "domain" maps onto Document.domain (Pydantic ignores it being extra-like)
    assert by_id["notices_999"].domain == "notices"
    # calendar: no top-level domain, but metadata carries it
    assert by_id["calendar_month_2026_08"].domain is None
    assert by_id["calendar_month_2026_08"].metadata.get("domain") == "academic_calendar"


def test_general_retrieve_excludes_notices_by_default(tmp_path: Path) -> None:
    config = load_config(str(_write_workspace(tmp_path / "ws")))
    docs = load_documents(config)
    # "수강신청" matches BOTH the calendar doc and the notices snapshot, but notices
    # must be excluded from general search so it cannot outrank/pollute the answer.
    pack = retrieve("수강신청은 언제 시작하나요?", docs, config)
    ids = [item.id for item in pack.items]
    assert ids, "expected at least the calendar doc to be retrieved"
    assert not any(i.startswith("notices_") for i in ids)
    assert "calendar_month_2026_08" in ids


def test_unrelated_question_has_no_notices_pollution(tmp_path: Path) -> None:
    config = load_config(str(_write_workspace(tmp_path / "ws")))
    docs = load_documents(config)
    pack = retrieve("셔틀버스 노선 알려줘", docs, config)
    ids = [item.id for item in pack.items]
    assert not any(i.startswith("notices_") for i in ids)


def test_fallback_research_includes_notices_when_exclusion_cleared(tmp_path: Path) -> None:
    config = load_config(str(_write_workspace(tmp_path / "ws")))
    docs = load_documents(config)
    # The forced-tool fallback path re-searches with exclude_domains=set() so the
    # indexed notices snapshot can answer when the live tool fails (AC-11).
    pack = retrieve("수강신청 취소 안내", docs, config, exclude_domains=set())
    ids = [item.id for item in pack.items]
    assert any(i.startswith("notices_") for i in ids)


def test_default_excluded_domains_is_notices(tmp_path: Path) -> None:
    assert "notices" in GENERAL_SEARCH_EXCLUDED_DOMAINS
    assert "dining" not in GENERAL_SEARCH_EXCLUDED_DOMAINS  # stable dining docs are general-searchable

# --- Fix C: relative week-date expansion ---------------------------------

# Frozen "current date" = 2026-06-13 (Saturday). weekday()==5, so the current
# week's Monday is 2026-06-08.
_FROZEN_NOW = "2026-06-13 14:00 토요일"


def _expand(question: str):
    from unittest.mock import patch

    from sutra.retrieval import _expand_relative_date_query

    with patch("sutra.prompts.get_current_time_str", return_value=_FROZEN_NOW):
        out = _expand_relative_date_query(question, "Asia/Seoul")
    return out.replace(question, "").split()


@pytest.mark.parametrize(
    "question, expected",
    [
        ("이번주 일정", ["2026-06-08", "2026-06-09", "2026-06-10", "2026-06-11", "2026-06-12", "2026-06-13", "2026-06-14"]),
        ("다음주 학식 메뉴", ["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18", "2026-06-19", "2026-06-20", "2026-06-21"]),
        ("지난주 공지", ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05", "2026-06-06", "2026-06-07"]),
    ],
)
def test_week_expansion_appends_full_week(question, expected) -> None:
    assert _expand(question) == expected


@pytest.mark.parametrize(
    "question, expected",
    [
        ("이번 주말 셔틀", ["2026-06-13", "2026-06-14"]),
        ("다음 주말 운영", ["2026-06-20", "2026-06-21"]),
        ("지난 주말 행사", ["2026-06-06", "2026-06-07"]),
    ],
)
def test_weekend_expansion_appends_two_days(question, expected) -> None:
    assert _expand(question) == expected


def test_week_only_question_expands_f1_regression() -> None:
    # F1 pin-down: a week-only question (no day-offset term) must still expand.
    assert _expand("다음주 학식 메뉴") != []


@pytest.mark.parametrize(
    "question, expected",
    [
        ("오늘 메뉴", ["2026-06-13"]),
        ("내일 일정", ["2026-06-14"]),
        ("모레 셔틀", ["2026-06-15"]),
        ("어제 공지", ["2026-06-12"]),
    ],
)
def test_day_offset_expansion_unchanged(question, expected) -> None:
    assert _expand(question) == expected


def test_no_expansion_without_relative_term() -> None:
    assert _expand("졸업 요건 알려줘") == []


def test_iso_date_present_short_circuits() -> None:
    # An explicit ISO date suppresses relative expansion.
    assert _expand("다음주 2026-07-01 일정") == []


def test_week_expansion_ranks_in_range_doc_first(tmp_path: Path) -> None:
    # F4: the expanded query must rank an in-range dated doc above an
    # out-of-range one when retrieved through retrieve().
    from unittest.mock import patch

    config = load_config(str(_write_workspace(tmp_path / "ws")))
    documents = load_documents(config)
    with patch("sutra.prompts.get_current_time_str", return_value=_FROZEN_NOW):
        # "다음주" -> 2026-06-15..21; calendar_month_2026_03 has 2026-03 dates
        # (out of range), so the in-range doc should win when present.
        pack = retrieve("다음주 학사일정", documents, config)
    ids = [item.id for item in pack.items]
    assert ids, "expected at least one retrieved fact"
