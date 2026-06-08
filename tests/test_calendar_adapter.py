from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from nlp_term.collect.base import PARSER_VERSION
from nlp_term.collect.source_inventory import iter_specs
from nlp_term.retrieve.rank import rank_docs
from nlp_term.schemas import RawSource, SourceVerification
from nlp_term.structured.calendar import CalendarAdapter


RAW_PATH = Path("data/raw/academic_calendar/academic_calendar.html")


def _context(fetched_at: str = "2026-06-06T17:55:38+00:00"):
    spec = next(item for item in iter_specs(stage="stage0") if item.source_id == "academic_calendar")
    raw = RawSource(
        source_id=spec.source_id,
        label=spec.label,
        domain=spec.domain,
        url=spec.url,
        fetched_at=fetched_at,
        content_type="text/html",
        raw_path=str(RAW_PATH),
        status_code=200,
        checksum="calendar-raw-checksum",
    )
    verification = SourceVerification(
        source_id=spec.source_id,
        official_chain_ok=spec.official_chain_ok,
        parser_name="calendar_stage_inventory",
        parser_version=PARSER_VERSION,
        evidence=[spec.url],
        warnings=[],
        verified_at="2026-06-06T17:55:39+00:00",
    )
    return spec, raw, verification


def test_calendar_adapter_parses_official_calendar_rows() -> None:
    spec, raw, verification = _context()

    rows = CalendarAdapter().parse(spec=spec, raw=raw, verification=verification)

    assert len(rows) >= 30
    assert any(row.event_name == "2026학년도 제1학기 수강신청" for row in rows)
    assert any(row.event_name == "제1학기 개강일" and row.start_date == "2026-03-03" for row in rows)
    assert all(row.start_date for row in rows)


def test_calendar_adapter_parses_summer_session_period_end() -> None:
    spec, raw, verification = _context()

    rows = CalendarAdapter().parse(spec=spec, raw=raw, verification=verification)

    summer = next(row for row in rows if row.event_name == "하기 계절학기")
    assert summer.start_date == "2026-06-22"
    assert summer.end_date == "2026-07-10"
    assert summer.is_range is True


def test_calendar_adapter_handles_cross_year_ranges() -> None:
    spec, raw, verification = _context()

    rows = CalendarAdapter().parse(spec=spec, raw=raw, verification=verification)

    winter_previous = next(row for row in rows if row.event_name == "동기 계절학기" and row.start_date == "2025-12-22")
    assert winter_previous.end_date == "2026-01-13"
    winter_next = next(row for row in rows if row.event_name == "동기 계절학기" and row.start_date == "2026-12-21")
    assert winter_next.end_date == "2027-01-12"


def test_calendar_adapter_row_ids_ignore_fetched_at() -> None:
    spec, raw, verification = _context(fetched_at="2026-06-06T17:55:38+00:00")
    newer_raw = raw.model_copy(update={"fetched_at": "2026-06-08T17:55:38+00:00"})

    first_ids = [row.row_id for row in CalendarAdapter().parse(spec=spec, raw=raw, verification=verification)]
    second_ids = [row.row_id for row in CalendarAdapter().parse(spec=spec, raw=newer_raw, verification=verification)]

    assert first_ids == second_ids


def test_calendar_adapter_uses_source_curriculum_year() -> None:
    spec, raw, verification = _context()
    yearly_spec = replace(spec, source_id="academic_calendar_2025", curriculum_year="2025")
    yearly_raw = raw.model_copy(update={"source_id": yearly_spec.source_id})
    yearly_verification = verification.model_copy(update={"source_id": yearly_spec.source_id})

    rows = CalendarAdapter().parse(spec=yearly_spec, raw=yearly_raw, verification=yearly_verification)

    assert any(row.event_name == "제1학기 개강일" and row.start_date == "2025-03-03" for row in rows)
    assert all(row.academic_year == 2025 for row in rows)


def test_calendar_knowledge_doc_metadata_contract() -> None:
    spec, raw, verification = _context()
    adapter = CalendarAdapter()
    rows = adapter.parse(spec=spec, raw=raw, verification=verification)

    doc = next(doc for doc in adapter.to_knowledge_docs(rows) if doc.metadata["structured"]["event_name"] == "하기 계절학기")

    assert doc.metadata["structured"]["start_date"] == "2026-06-22"
    assert doc.metadata["structured"]["end_date"] == "2026-07-10"
    assert doc.metadata["structured"]["event_type"] == "summer_session_end"
    assert "여름 계절학기 종강일" in doc.metadata["structured"]["aliases"]
    assert doc.metadata["event_name"] == "하기 계절학기"
    assert doc.metadata["event_type"] == "summer_session_end"
    assert doc.metadata["start_date"] == "2026-06-22"
    assert doc.metadata["end_date"] == "2026-07-10"
    assert doc.metadata["date_span"] == "2026-06-22/2026-07-10"
    assert doc.metadata["structured_fields"] == [
        "academic_year",
        "month",
        "event_name",
        "event_type",
        "aliases",
        "start_date",
        "end_date",
        "semester",
        "is_range",
    ]
    assert doc.metadata["verification_official_chain_ok"] is True


def test_calendar_adapter_records_absence_of_exact_semester_end() -> None:
    spec, raw, verification = _context()

    rows = CalendarAdapter().parse(spec=spec, raw=raw, verification=verification)

    assert not any("종강" in row.event_name for row in rows)


def test_calendar_break_rows_include_semester_end_search_aliases() -> None:
    spec, raw, verification = _context()
    adapter = CalendarAdapter()
    rows = adapter.parse(spec=spec, raw=raw, verification=verification)

    summer_break = next(row for row in rows if row.event_name == "하기방학")
    winter_break = next(row for row in rows if row.event_name == "동기방학")
    summer_doc = summer_break.to_knowledge_doc()
    winter_doc = winter_break.to_knowledge_doc()

    assert summer_doc.metadata["event_type"] == "semester_end"
    assert summer_doc.metadata["search_aliases"] == ["1학기 종강", "이번 학기 종강", "종강일", "여름방학 시작", "방학 시작"]
    assert winter_doc.metadata["search_aliases"] == ["2학기 종강", "종강일", "겨울방학 시작", "방학 시작"]
    assert "1학기 종강" in summer_doc.body
    assert "2학기 종강" in winter_doc.body

    docs = adapter.to_knowledge_docs(rows)
    top = rank_docs("이번 학기 종강일이 언제인가요?", docs=docs, top_k=1)[0]

    assert top.doc_id == summer_doc.doc_id


def test_calendar_adapter_adds_monthly_aggregate_knowledge_docs() -> None:
    spec, raw, verification = _context()
    adapter = CalendarAdapter()
    rows = adapter.parse(spec=spec, raw=raw, verification=verification)

    docs = adapter.to_knowledge_docs(rows)

    june = next(
        doc
        for doc in docs
        if doc.metadata.get("row_type") == "academic_calendar_monthly" and doc.metadata.get("month") == 6
    )
    assert june.metadata["period_start"] == "2026-06-01"
    assert june.metadata["period_end"] == "2026-06-30"
    assert june.metadata["academic_year"] == 2026
    assert "하기방학" in june.body
    assert "하기 계절학기" in june.body
    assert "6월 학사일정" in june.title


def test_calendar_adapter_adds_semester_aggregate_knowledge_docs() -> None:
    spec, raw, verification = _context()
    adapter = CalendarAdapter()
    rows = adapter.parse(spec=spec, raw=raw, verification=verification)

    docs = adapter.to_knowledge_docs(rows)

    first_semester = next(
        doc
        for doc in docs
        if doc.metadata.get("row_type") == "academic_calendar_semester" and doc.metadata.get("semester") == "1학기"
    )
    assert first_semester.metadata["period_start"] <= "2026-03-03"
    assert first_semester.metadata["period_end"] >= "2026-06-22"
    assert "제1학기 개강일" in first_semester.body
    assert "하기방학" in first_semester.body
    assert "1학기 학사일정" in first_semester.title
