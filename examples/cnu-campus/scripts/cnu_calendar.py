import re
from typing import Optional, NamedTuple, List, Tuple
from bs4 import BeautifulSoup

SKIP_FILENAMES = {
    "academic_calendar.html",
    "homepage_academic_calendar_module.html",
    "academic_calendar_english_education_undergrad.html",
}


class CalendarEvent(NamedTuple):
    year: int
    page_year: int
    start_date: str
    end_date: str
    event_name: str
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    source_file: Optional[str] = None


class DateParseFailure(NamedTuple):
    raw_date: str
    raw_event: str
    source_file: str
    reason: str


class ParseResult(NamedTuple):
    status: str
    events: List[CalendarEvent]
    date_failures: List[DateParseFailure]
    error_msg: Optional[str] = None


def _resolve_date_year(page_year: int, month: int, box_index: int) -> int:
    if month == 12 and box_index == 0:
        return page_year - 1
    return page_year


def _parse_li_dates(
    strong_text: str, page_year: int, box_index: int
) -> Tuple[Optional[str], Optional[str], Optional[DateParseFailure]]:
    date_pattern = re.compile(r"(\d{2})\.(\d{2})")
    matches = date_pattern.findall(strong_text)
    if not matches:
        return (None, None, None)

    mm1, dd1 = int(matches[0][0]), int(matches[0][1])
    start_year = _resolve_date_year(page_year, mm1, box_index)
    start_date = f"{start_year:04d}-{mm1:02d}-{dd1:02d}"

    if len(matches) >= 2:
        mm2, dd2 = int(matches[1][0]), int(matches[1][1])
        end_year = start_year
        if mm2 < mm1:
            end_year = start_year + 1
        end_date = f"{end_year:04d}-{mm2:02d}-{dd2:02d}"
    else:
        end_date = start_date

    return (start_date, end_date, None)


def _is_target_year_file(path: str) -> Optional[int]:
    filename = path.replace("\\", "/").split("/")[-1]
    m = re.search(r"_(\d{4})\.html$", filename)
    if not m:
        return None
    year = int(m.group(1))
    if year in {2023, 2024, 2025, 2026}:
        return year
    return None


def parse_calendar_file(path: str, source_meta: Optional[dict] = None) -> ParseResult:
    filename = path.replace("\\", "/").split("/")[-1]

    if filename in SKIP_FILENAMES:
        return ParseResult(
            status="skipped", events=[], date_failures=[],
            error_msg=f"Skipped file: {filename}",
        )

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return ParseResult(
            status="skipped", events=[], date_failures=[],
            error_msg=f"Failed to read file: {e}",
        )

    soup = BeautifulSoup(content, "html.parser")

    year_tag = soup.find("strong", class_="year")
    if not year_tag:
        return ParseResult(
            status="skipped", events=[], date_failures=[],
            error_msg="No year tag found",
        )
    try:
        page_year = int(year_tag.get_text(strip=True))
    except ValueError:
        return ParseResult(
            status="skipped", events=[], date_failures=[],
            error_msg=f"Invalid year: {year_tag.get_text(strip=True)}",
        )

    boxes = soup.find_all("div", class_="calen_box")
    if not boxes:
        return ParseResult(
            status="skipped", events=[], date_failures=[],
            error_msg="No calen_box elements found",
        )

    source_url = source_meta.get("url") if source_meta else None
    source_name = (
        source_meta.get("source_name")
        if source_meta and source_meta.get("source_name")
        else "충남대학교 학사일정"
    )

    events: List[CalendarEvent] = []
    date_failures: List[DateParseFailure] = []

    for box_index, box in enumerate(boxes):
        fl_month = box.find("div", class_="fl_month")
        if not fl_month:
            continue
        month_match = re.search(r"(\d+)", fl_month.get_text(strip=True))
        if not month_match:
            continue

        fr_list = box.find("div", class_="fr_list")
        if not fr_list:
            continue

        for ul in fr_list.find_all("ul"):
            for li in ul.find_all("li"):
                strong_tag = li.find("strong")
                span_tag = li.find("span", class_="list")
                if not strong_tag or not span_tag:
                    continue

                date_str = strong_tag.get_text(strip=True)
                event_name = span_tag.get_text(strip=True)
                event_name = re.sub(r"\s+", " ", event_name).strip()
                if not event_name:
                    continue

                start_date, end_date, failure = _parse_li_dates(
                    date_str, page_year, box_index
                )

                if failure or not start_date:
                    date_failures.append(
                        DateParseFailure(
                            raw_date=date_str,
                            raw_event=event_name,
                            source_file=path,
                            reason=failure.reason if failure else "No date pattern found",
                        )
                    )
                    continue

                events.append(
                    CalendarEvent(
                        year=int(start_date[:4]),
                        page_year=page_year,
                        start_date=start_date,
                        end_date=end_date,
                        event_name=event_name,
                        source_url=source_url,
                        source_name=source_name,
                        source_file=path,
                    )
                )

    return ParseResult(status="success", events=events, date_failures=date_failures)
