import json
import re
from pathlib import Path
from collections import defaultdict
from cnu_calendar import parse_calendar_file, CalendarEvent

TARGET_YEARS = [2023, 2024, 2025, 2026]
CALENDAR_SOURCE_NAME = "충남대학교 학사일정"
CALENDAR_SOURCE_URL = "https://plus.cnu.ac.kr/_prog/academic_calendar"


def _month_dates(year: int, month: int) -> tuple[str, str]:
    import calendar as cal_mod
    last_day = cal_mod.monthrange(year, month)[1]
    return (f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}")


def _event_overlaps_month(
    start_date: str, end_date: str, month_start: str, month_end: str
) -> bool:
    return start_date <= month_end and end_date >= month_start


def _is_month_doc(doc: dict) -> bool:
    metadata = doc.get("metadata", {})
    return doc.get("id", "").startswith("calendar_month_") or metadata.get("doc_type") == "month"


def _write_jsonl(path: Path, docs: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")


def _load_existing_month_docs(path: Path) -> list[dict]:
    docs = []
    if not path.exists():
        return docs
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            if _is_month_doc(doc):
                docs.append(_normalize_month_doc(doc))
    return docs


def _normalize_month_doc(doc: dict) -> dict:
    metadata = doc.get("metadata", {})
    year = metadata.get("year")
    month = metadata.get("month")
    if not isinstance(year, int) or not isinstance(month, int):
        return doc
    padded = f"{year:04d}년 {month:02d}월"
    natural = f"{year:04d}년 {month}월"
    for field in ("title", "text"):
        value = doc.get(field)
        if isinstance(value, str):
            doc[field] = value.replace(padded, natural)
    return doc


def _write_fallback_report(report_path: Path, month_docs: list[dict]) -> None:
    report = {}
    if report_path.exists():
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
        except (json.JSONDecodeError, OSError):
            report = {}

    provenance_keys = (
        "parsed_files",
        "skipped_files",
        "raw_event_count",
        "unique_event_count",
        "duplicate_count",
        "date_parse_failures",
        "date_range_coverage",
        "events_by_year",
    )
    previous_raw_provenance = report.get("previous_raw_provenance")
    if previous_raw_provenance is None:
        previous_raw_provenance = {
            key: report[key]
            for key in provenance_keys
            if key in report and report[key] not in (None, [], {}, 0)
        }

    months_by_year: dict[str, list[int]] = defaultdict(list)
    for doc in month_docs:
        metadata = doc.get("metadata", {})
        year = metadata.get("year")
        month = metadata.get("month")
        if not isinstance(year, int) or not isinstance(month, int):
            match = re.match(r"calendar_month_(\d{4})_(\d{2})$", doc.get("id", ""))
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
        if isinstance(year, int) and isinstance(month, int) and month not in months_by_year[str(year)]:
            months_by_year[str(year)].append(month)

    limitations = list(report.get("known_limitations", []))
    fallback_note = "Raw academic calendar HTML was unavailable; existing calendar index was pruned to month docs only"
    if fallback_note not in limitations:
        limitations.append(fallback_note)

    report = {
        "parsed_files": [],
        "skipped_files": [],
        "raw_event_count": 0,
        "unique_event_count": 0,
        "generated_event_docs": 0,
        "generated_month_docs": len(month_docs),
        "duplicate_count": 0,
        "date_parse_failures": [],
        "date_range_coverage": {},
        "events_by_year": {},
        "months_by_year": {
            year: sorted(months)
            for year, months in sorted(months_by_year.items())
        },
        "known_limitations": limitations,
        "raw_missing_fallback": True,
    }
    if previous_raw_provenance:
        report["previous_raw_provenance"] = previous_raw_provenance
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def _build_month_doc(
    year: int,
    month: int,
    events: list[CalendarEvent],
    event_start_idx: int,
) -> dict:
    doc_id = f"calendar_month_{year:04d}_{month:02d}"
    month_label = f"{year}년 {month}월"
    title = f"{month_label} 학사일정"
    bullet_lines = []
    for e in events:
        if e.start_date == e.end_date:
            bullet_lines.append(f"- {e.start_date}: {e.event_name}")
        else:
            bullet_lines.append(f"- {e.start_date} ~ {e.end_date}: {e.event_name}")
    text = f"{month_label} 충남대학교 학사일정입니다.\n\n" + "\n".join(bullet_lines)
    return {
        "id": doc_id,
        "title": title,
        "text": text,
        "source_url": events[0].source_url or CALENDAR_SOURCE_URL,
        "source_name": events[0].source_name or CALENDAR_SOURCE_NAME,
        "metadata": {
            "domain": "academic_calendar",
            "doc_type": "month",
            "year": year,
            "month": month,
            "start_date": f"{year:04d}-{month:02d}-01",
            "end_date": f"{year:04d}-{month:02d}-{__import__('calendar').monthrange(year, month)[1]:02d}",
            "event_count": len(events),
            "page_years": sorted(set(e.page_year for e in events)),
            "source_file": None,
        },
    }


def main():
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent

    raw_dir = project_root / "data" / "raw" / "academic_calendar"
    probe_path = project_root / "data" / "sources" / "source_probe.json"

    processed_dir = project_root / "examples" / "cnu-campus" / "data" / "processed"
    reports_dir = project_root / "examples" / "cnu-campus" / "data" / "reports"
    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    output_index_path = processed_dir / "calendar-index.jsonl"
    output_report_path = reports_dir / "calendar-build-report.json"

    meta_map = {}
    if probe_path.exists():
        try:
            with open(probe_path, "r", encoding="utf-8") as f:
                for item in json.load(f):
                    raw_info = item.get("raw", {})
                    raw_p = raw_info.get("raw_path")
                    if raw_p:
                        key = Path(raw_p).as_posix().lower()
                        meta_map[key] = {
                            "url": raw_info.get("url"),
                            "fetched_at": raw_info.get("fetched_at"),
                            "source_id": raw_info.get("source_id"),
                        }
        except Exception as e:
            print(f"Warning: Failed to load source_probe.json: {e}")

    parsed_files = []
    skipped_files = []
    all_events: list[CalendarEvent] = []
    all_date_failures = []

    if raw_dir.exists():
        html_files = sorted(list(raw_dir.glob("*.html")))
        for filepath in html_files:
            rel_path = filepath.relative_to(project_root)
            rel_str = rel_path.as_posix()
            key = rel_path.as_posix().lower()
            meta = meta_map.get(key)

            result = parse_calendar_file(str(filepath), meta)

            if result.status == "success":
                # Only keep events from target year files
                filename = filepath.name
                year_match = re.search(r"_(\d{4})\.html$", filename)
                if year_match and int(year_match.group(1)) in TARGET_YEARS:
                    all_events.extend(result.events)
                    parsed_files.append(rel_str)
                else:
                    skipped_files.append({
                        "file": rel_str,
                        "reason": "Not a target year file",
                    })
                all_date_failures.extend(result.date_failures)
            else:
                skipped_files.append({
                    "file": rel_str,
                    "reason": result.error_msg or "Unknown skip reason",
                })
    else:
        month_docs = _load_existing_month_docs(output_index_path)
        if not month_docs:
            print(f"Error: Raw directory not found at {raw_dir} and no existing month docs were available")
            return
        _write_jsonl(output_index_path, month_docs)
        _write_fallback_report(output_report_path, month_docs)
        print(f"Raw directory not found at {raw_dir}; kept {len(month_docs)} month docs in {output_index_path}")
        return

    raw_event_count = len(all_events)

    seen = set()
    unique_events = []
    duplicate_count = 0
    for e in all_events:
        key = (e.start_date, e.end_date, e.event_name)
        if key not in seen:
            seen.add(key)
            unique_events.append(e)
        else:
            duplicate_count += 1

    unique_event_count = len(unique_events)

    events_by_year = defaultdict(list)
    for e in unique_events:
        events_by_year[e.year].append(e)

    month_events_map = defaultdict(list)
    covered_year_months = set()
    for e in unique_events:
        s_year = int(e.start_date[:4])
        s_month = int(e.start_date[5:7])
        e_year = int(e.end_date[:4])
        e_month = int(e.end_date[5:7])

        cursor_year, cursor_month = s_year, s_month
        while (cursor_year, cursor_month) <= (e_year, e_month):
            m_start, m_end = _month_dates(cursor_year, cursor_month)
            if _event_overlaps_month(e.start_date, e.end_date, m_start, m_end):
                month_events_map[(cursor_year, cursor_month)].append(e)
                covered_year_months.add((cursor_year, cursor_month))
            cursor_month += 1
            if cursor_month > 12:
                cursor_month = 1
                cursor_year += 1

    month_docs = []
    for (year, month) in sorted(covered_year_months):
        events = month_events_map[(year, month)]
        month_docs.append(_build_month_doc(year, month, events, 0))

    all_chunks = month_docs

    try:
        _write_jsonl(output_index_path, all_chunks)
        print(f"Successfully wrote {len(all_chunks)} docs to {output_index_path}")
    except Exception as e:
        print(f"Error writing index JSONL: {e}")

    date_range_coverage = {
        str(year): {
            "min_date": min(e.start_date for e in events),
            "max_date": max(e.end_date for e in events),
        }
        for year, events in sorted(events_by_year.items())
    }

    years_with_months = defaultdict(set)
    for (year, month) in sorted(covered_year_months):
        years_with_months[year].add(month)

    report = {
        "parsed_files": parsed_files,
        "skipped_files": skipped_files,
        "raw_event_count": raw_event_count,
        "unique_event_count": unique_event_count,
        "generated_event_docs": 0,
        "generated_month_docs": len(month_docs),
        "duplicate_count": duplicate_count,
        "date_parse_failures": [
            {
                "raw_date": f.raw_date,
                "raw_event": f.raw_event,
                "source_file": f.source_file,
                "reason": f.reason,
            }
            for f in all_date_failures
        ],
        "date_range_coverage": date_range_coverage,
        "events_by_year": {
            str(year): len(events)
            for year, events in sorted(events_by_year.items())
        },
        "months_by_year": {
            str(year): sorted(years_with_months[year])
            for year in sorted(years_with_months)
        },
        "known_limitations": [
            "Event year metadata reflects the resolved event start year; source academic calendar page year is preserved as page_year for traceability",
            "In-source duplicates (e.g. 수강신청 확인 및 정정 appears twice in March 2026) are collapsed by (start_date, end_date, event_name) key",
            "Cross-year date ranges (e.g., Dec 2025 ~ Jan 2026) produce event and month docs for both years; year reflects actual event start year, page_year tracks the source page",
            "Month docs are generated per year-month; events spanning multiple months appear in all covered month docs",
            "Holiday names (e.g., 설날, 추석) are preserved as-is from source without normalization",
        ],
    }

    try:
        with open(output_report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Successfully wrote build report to {output_report_path}")
    except Exception as e:
        print(f"Error writing build report: {e}")


if __name__ == "__main__":
    main()
