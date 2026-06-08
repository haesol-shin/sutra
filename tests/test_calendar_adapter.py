from __future__ import annotations

from pathlib import Path

from nlp_term.collect.base import PARSER_VERSION
from nlp_term.collect.source_inventory import iter_specs
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


def test_calendar_knowledge_doc_metadata_contract() -> None:
    spec, raw, verification = _context()
    adapter = CalendarAdapter()
    rows = adapter.parse(spec=spec, raw=raw, verification=verification)

    doc = next(doc for doc in adapter.to_knowledge_docs(rows) if doc.metadata["structured"]["event_name"] == "하기 계절학기")

    assert doc.metadata["structured"]["start_date"] == "2026-06-22"
    assert doc.metadata["structured"]["end_date"] == "2026-07-10"
    assert doc.metadata["event_name"] == "하기 계절학기"
    assert doc.metadata["start_date"] == "2026-06-22"
    assert doc.metadata["end_date"] == "2026-07-10"
    assert doc.metadata["date_span"] == "2026-06-22/2026-07-10"
    assert doc.metadata["structured_fields"] == [
        "academic_year",
        "month",
        "event_name",
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
