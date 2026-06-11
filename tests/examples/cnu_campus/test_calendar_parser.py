import sys
import json
from pathlib import Path
import pytest

tests_dir = Path(__file__).resolve().parent
project_root = tests_dir.parent.parent.parent
scripts_dir = project_root / "examples" / "cnu-campus" / "scripts"
sys.path.insert(0, str(scripts_dir))

from cnu_calendar import (  # noqa: E402
    CalendarEvent,
    parse_calendar_file,
    SKIP_FILENAMES,
)
from build_calendar_index import _build_month_doc, _write_fallback_report, main as build_main  # noqa: E402


def raw_calendar_path(filename: str) -> Path:
    path = project_root / "data" / "raw" / "academic_calendar" / filename
    if not path.exists():
        pytest.skip(f"Missing gitignored raw calendar fixture: {path}")
    return path


def test_parses_all_four_target_year_files():
    for year in [2023, 2024, 2025, 2026]:
        path = raw_calendar_path(f"academic_calendar_{year}.html")
        result = parse_calendar_file(str(path))
        assert result.status == "success", f"{year}: {result.error_msg}"
        assert len(result.events) == 70, f"{year}: expected 70 events, got {len(result.events)}"
        assert len(result.date_failures) == 0, f"{year}: {len(result.date_failures)} date failures"


def test_skips_duplicate_and_module_files():
    for fname in SKIP_FILENAMES:
        path = project_root / "data" / "raw" / "academic_calendar" / fname
        if path.exists():
            result = parse_calendar_file(str(path))
            assert result.status == "skipped", f"{fname} should be skipped"


def test_extracts_valid_iso_dates():
    path = raw_calendar_path("academic_calendar_2026.html")
    result = parse_calendar_file(str(path))
    import re
    iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for event in result.events:
        assert iso_pattern.match(event.start_date), f"Invalid start_date: {event.start_date}"
        assert iso_pattern.match(event.end_date), f"Invalid end_date: {event.end_date}"
        assert event.start_date <= event.end_date, f"start > end: {event.start_date} > {event.end_date}"


def test_known_important_events_2026():
    path = raw_calendar_path("academic_calendar_2026.html")
    result = parse_calendar_file(str(path))
    gyechoel = [e for e in result.events if "계절학기" in e.event_name]
    assert len(gyechoel) >= 3, f"Expected >= 3 계절학기 events, got {len(gyechoel)}"

    sugang = [e for e in result.events if "수강신청" in e.event_name]
    assert len(sugang) >= 5, f"Expected >= 5 수강신청 events, got {len(sugang)}"

    banghak = [e for e in result.events if "방학" in e.event_name]
    assert len(banghak) >= 1, f"Expected >= 1 방학 events, got {len(banghak)}"


def test_single_day_and_range_dates():
    path = raw_calendar_path("academic_calendar_2025.html")
    result = parse_calendar_file(str(path))

    single_day = [e for e in result.events if e.start_date == e.end_date]
    ranges = [e for e in result.events if e.start_date != e.end_date]
    assert len(single_day) >= 30, f"Expected >= 30 single-day events, got {len(single_day)}"
    assert len(ranges) >= 10, f"Expected >= 10 range events, got {len(ranges)}"

    for e in ranges:
        assert e.start_date < e.end_date, f"Range start >= end: {e.start_date} >= {e.end_date}"


def test_cross_year_range():
    path = raw_calendar_path("academic_calendar_2026.html")
    result = parse_calendar_file(str(path))
    cross_year = [e for e in result.events if e.start_date[:4] != e.end_date[:4]]
    assert len(cross_year) >= 2, f"Expected >= 2 cross-year ranges, got {len(cross_year)}"
    for e in cross_year:
        assert int(e.start_date[:4]) < int(e.end_date[:4])


def test_month_chunk_includes_events():
    build_main()
    index_path = project_root / "examples" / "cnu-campus" / "data" / "processed" / "calendar-index.jsonl"
    assert index_path.exists()

    month_docs = []
    with open(index_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            if doc.get("metadata", {}).get("doc_type") == "month":
                month_docs.append(doc)

    assert len(month_docs) == 50, f"Expected 50 month docs, got {len(month_docs)}"
    assert all(doc["id"].startswith("calendar_month_") for doc in month_docs)

    mar2026 = [d for d in month_docs if d["metadata"].get("year") == 2026 and d["metadata"].get("month") == 3]
    assert len(mar2026) == 1, f"Expected 1 March 2026 month doc, got {len(mar2026)}"
    assert mar2026[0]["metadata"]["event_count"] >= 5, "March 2026 should have >=5 events"


def test_calendar_index_omits_event_docs():
    build_main()
    index_path = project_root / "examples" / "cnu-campus" / "data" / "processed" / "calendar-index.jsonl"
    with open(index_path, "r", encoding="utf-8") as f:
        docs = [json.loads(line) for line in f if line.strip()]

    assert docs
    assert all(not doc["id"].startswith("calendar_event_") for doc in docs)
    assert {doc["metadata"]["doc_type"] for doc in docs} == {"month"}


def test_month_doc_uses_natural_month_text_for_bm25():
    event = CalendarEvent(
        year=2026,
        page_year=2026,
        start_date="2026-06-01",
        end_date="2026-06-01",
        event_name="수강신청",
        source_url="https://example.test/calendar",
        source_name="학사일정",
        source_file=None,
    )

    doc = _build_month_doc(2026, 6, [event], 0)

    assert "2026년 6월 학사일정" in doc["title"]
    assert "2026년 6월 충남대학교 학사일정" in doc["text"]


def test_no_nav_chrome_in_output():
    path = raw_calendar_path("academic_calendar_2026.html")
    result = parse_calendar_file(str(path))

    nav_terms = ["로그인", "주메뉴", "사이트맵", "본문 바로가기", "이전 페이지", "다음 페이지"]
    for event in result.events:
        for term in nav_terms:
            assert term not in event.event_name, f"Nav term '{term}' found in event: {event.event_name}"


def test_generated_docs_have_required_sutra_fields():
    build_main()
    index_path = project_root / "examples" / "cnu-campus" / "data" / "processed" / "calendar-index.jsonl"
    required = {"id", "title", "text", "source_url", "source_name", "metadata"}

    with open(index_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) > 0
    for i, line in enumerate(lines):
        doc = json.loads(line)
        missing = required - set(doc.keys())
        assert not missing, f"Line {i}: missing fields: {missing}"
        assert doc.get("source_url"), f"Line {i}: empty source_url"
        assert doc.get("source_name"), f"Line {i}: empty source_name"
        meta = doc.get("metadata", {})
        assert "domain" in meta, f"Line {i}: missing metadata.domain"
        assert meta["domain"] == "academic_calendar"


def test_build_report_fields():
    build_main()
    report_path = project_root / "examples" / "cnu-campus" / "data" / "reports" / "calendar-build-report.json"
    assert report_path.exists()
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    expected = [
        "parsed_files", "skipped_files", "raw_event_count", "unique_event_count",
        "generated_event_docs", "generated_month_docs", "duplicate_count",
        "date_parse_failures", "date_range_coverage", "events_by_year",
        "months_by_year", "known_limitations",
    ]
    for field in expected:
        assert field in report, f"Missing report field: {field}"

    if report.get("raw_missing_fallback"):
        assert report["parsed_files"] == []
        assert report["skipped_files"] == []
        assert report["raw_event_count"] == 0
        assert report["unique_event_count"] == 0
        assert report["duplicate_count"] == 0
        assert report["date_parse_failures"] == []
        assert report["date_range_coverage"] == {}
        assert report["events_by_year"] == {}
        assert report["previous_raw_provenance"]["raw_event_count"] == 280
    else:
        assert len(report["parsed_files"]) == 4
        assert report["raw_event_count"] == 280
        assert report["unique_event_count"] <= 280
    assert report["generated_event_docs"] == 0
    assert report["generated_month_docs"] == 50


def test_fallback_report_separates_previous_raw_provenance(tmp_path):
    report_path = tmp_path / "calendar-build-report.json"
    report_path.write_text(
        json.dumps(
            {
                "parsed_files": ["data/raw/academic_calendar/academic_calendar_2026.html"],
                "skipped_files": [{"file": "ignored.html", "reason": "ignored"}],
                "raw_event_count": 280,
                "unique_event_count": 276,
                "duplicate_count": 4,
                "date_parse_failures": [{"raw_date": "bad"}],
                "date_range_coverage": {"2026": {"min_date": "2026-01-01", "max_date": "2026-12-31"}},
                "events_by_year": {"2026": 68},
                "months_by_year": {"2026": [1, 2]},
                "generated_event_docs": 0,
                "generated_month_docs": 50,
                "known_limitations": ["Existing limitation"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    _write_fallback_report(report_path, [{"id": "calendar_month_2026_01"}, {"id": "calendar_month_2026_02"}])

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["raw_missing_fallback"] is True
    assert report["parsed_files"] == []
    assert report["skipped_files"] == []
    assert report["raw_event_count"] == 0
    assert report["unique_event_count"] == 0
    assert report["duplicate_count"] == 0
    assert report["date_parse_failures"] == []
    assert report["date_range_coverage"] == {}
    assert report["events_by_year"] == {}
    assert report["months_by_year"] == {"2026": [1, 2]}
    assert report["previous_raw_provenance"]["raw_event_count"] == 280
    assert report["previous_raw_provenance"]["parsed_files"] == [
        "data/raw/academic_calendar/academic_calendar_2026.html"
    ]


def test_event_year_assignment():
    path = raw_calendar_path("academic_calendar_2023.html")
    result = parse_calendar_file(str(path))
    cross_year_found = False
    for event in result.events:
        assert event.year == int(event.start_date[:4]), (
            f"year={event.year} != start_date year={event.start_date[:4]} for {event.event_name}"
        )
        if event.year != event.page_year:
            cross_year_found = True
    # At least one cross-year event (December previous-year box) expected
    assert cross_year_found, "Expected at least one event with year != page_year"

    # Generated docs should be month aggregates only.
    build_main()
    index_path = project_root / "examples" / "cnu-campus" / "data" / "processed" / "calendar-index.jsonl"
    with open(index_path, "r", encoding="utf-8") as f:
        docs = []
        for line in f:
            line = line.strip()
            if not line:
                continue
            docs.append(json.loads(line))
    assert len(docs) == 50
    for doc in docs:
        meta = doc["metadata"]
        assert "year" in meta, f"Missing year in month doc {doc['id']}"
        assert "page_years" in meta, f"Missing page_years in month doc {doc['id']}"
        assert meta["doc_type"] == "month"
        assert meta["year"] == int(meta["start_date"][:4])


def test_generated_docs_have_no_body_field():
    build_main()
    index_path = project_root / "examples" / "cnu-campus" / "data" / "processed" / "calendar-index.jsonl"
    with open(index_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            assert "body" not in doc, f"Doc {doc['id']} has forbidden 'body' field"


def test_merged_knowledge_index_includes_all_domains():
    from build_clean_index import main as build_clean_main
    build_clean_main()
    merged_path = project_root / "examples" / "cnu-campus" / "data" / "processed" / "knowledge-index.jsonl"
    assert merged_path.exists()

    domains = set()
    with open(merged_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            domain = doc.get("domain") or doc.get("metadata", {}).get("domain", "unknown")
            domains.add(domain)

    assert "dining" in domains, "Missing dining domain in merged index"
    assert "shuttle" in domains, "Missing shuttle domain in merged index"
    assert "academic_calendar" in domains, "Missing academic_calendar domain in merged index"
