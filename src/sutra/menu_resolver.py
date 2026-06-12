from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo


_WEEKDAY_OFFSETS = {
    "월": 0,
    "화": 1,
    "수": 2,
    "목": 3,
    "금": 4,
    "토": 5,
    "일": 6,
}
_WEEKDAY_FULL = {f"{name}요일": offset for name, offset in _WEEKDAY_OFFSETS.items()}
_RELATIVE_DAY_OFFSETS = {
    "내일모레": 2,
    "오늘": 0,
    "금일": 0,
    "내일": 1,
    "명일": 1,
    "모레": 2,
    "어제": -1,
}
_WEEK_TERM_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"이번\s*주"), 0),
    (re.compile(r"다음\s*주|담주"), 7),
    (re.compile(r"지난\s*주"), -7),
)
_DELIMITERS = set(" \t\r\n,，.·~/~부터까지이랑와과및")


def resolve_menu_dates(question: str, config: Any) -> list[str] | None:
    """Resolve dining-menu date expressions in a Korean user question."""
    today = datetime.now(ZoneInfo(config.workspace.timezone)).date()
    current_monday = today - timedelta(days=today.weekday())
    masked = question

    explicit_dates, masked = _consume_explicit_dates(masked, today)
    relative_dates, masked = _consume_relative_days(masked, today)

    week_matches = _find_week_terms(question)
    scan_limit = week_matches[1][0] if len(week_matches) > 1 else len(question)
    week_scan_text = masked[:scan_limit]
    first_week_offset = week_matches[0][2] if week_matches else None

    has_weekday_group = bool(re.search(r"평일|주중", week_scan_text))
    weekday_scan_text = re.sub(r"평일|주중", "  ", week_scan_text)
    ranges = _weekday_ranges(weekday_scan_text)
    full_weekdays, masked_after_full = _consume_full_weekdays(weekday_scan_text)
    single_weekdays = _single_weekdays(masked_after_full, week_term_present=bool(week_matches))
    weekday_offsets = [*ranges, *full_weekdays, *single_weekdays]
    has_weekday_or_range = bool(weekday_offsets)
    has_weekend = "주말" in week_scan_text
    has_week_only = first_week_offset is not None or bool(re.search(r"주간\s*식단|주간\s*식단표|주간\s*메뉴", week_scan_text))

    if explicit_dates:
        return _iso_sorted_capped(explicit_dates)
    if relative_dates:
        return _iso_sorted_capped(relative_dates)

    if has_weekday_or_range or has_weekend:
        base_monday = current_monday + timedelta(days=first_week_offset or 0)
        dates = [base_monday + timedelta(days=offset) for offset in weekday_offsets]
        if has_weekend:
            dates.extend(base_monday + timedelta(days=offset) for offset in (5, 6))
        return _iso_sorted_capped(dates)

    if has_week_only or has_weekday_group:
        base_monday = current_monday + timedelta(days=first_week_offset or 0)
        return _iso_sorted_capped(base_monday + timedelta(days=offset) for offset in range(5))

    return None

CAFETERIA_TOKENS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("제1학생회관", re.compile(r"(?:제\s*)?1\s*학(?!기|년)(?:생\s*회관)?")),
    ("제2학생회관", re.compile(r"(?:제\s*)?2\s*학(?!기|년)(?:생\s*회관)?")),
    ("제3학생회관", re.compile(r"(?:제\s*)?3\s*학(?!기|년)(?:생\s*회관)?")),
    ("제4학생회관", re.compile(r"(?:제\s*)?4\s*학(?!기|년)(?:생\s*회관)?")),
    ("생활과학대학", re.compile(r"생활\s*과학(?:대학)?")),
)


def resolve_cafeteria(question: str) -> str | None:
    """Deterministically resolve an explicit cafeteria named in the question.

    Returns the canonical cafeteria name when the question names one
    (제1학생회관 is the food court). Returns None when no cafeteria is named,
    meaning "all daily-menu cafeterias" (전체). The 9B forced-tool model is
    unreliable at picking the cafeteria enum (verified live), so the server
    derives it from the question text — same determinism applied to dates.
    """
    for name, pattern in CAFETERIA_TOKENS:
        if pattern.search(question):
            return name
    return None

def _consume_explicit_dates(text: str, today: date) -> tuple[list[date], str]:
    dates: list[date] = []
    spans: list[tuple[int, int]] = []

    for match in re.finditer(r"\d{4}-\d{2}-\d{2}", text):
        try:
            dates.append(date.fromisoformat(match.group(0)))
            spans.append(match.span())
        except ValueError:
            continue

    occupied = _spans_to_mask(spans, len(text))
    for match in re.finditer(r"(\d{1,2})월\s*(\d{1,2})일", text):
        if _span_overlaps_mask(match.span(), occupied):
            continue
        month = int(match.group(1))
        day = int(match.group(2))
        resolved = _safe_date(today.year, month, day)
        if resolved is not None:
            dates.append(resolved)
            spans.append(match.span())
            occupied[match.start() : match.end()] = [True] * (match.end() - match.start())

    for match in re.finditer(r"(?<!\d)(\d{1,2})일(?!\s*요일)", text):
        if _span_overlaps_mask(match.span(), occupied):
            continue
        resolved = _safe_date(today.year, today.month, int(match.group(1)))
        if resolved is not None:
            dates.append(resolved)
            spans.append(match.span())
            occupied[match.start() : match.end()] = [True] * (match.end() - match.start())

    return dates, _blank_spans(text, spans)


def _consume_relative_days(text: str, today: date) -> tuple[list[date], str]:
    dates: list[date] = []
    spans: list[tuple[int, int]] = []
    pattern = re.compile("|".join(re.escape(term) for term in _RELATIVE_DAY_OFFSETS))
    for match in pattern.finditer(text):
        term = match.group(0)
        dates.append(today + timedelta(days=_RELATIVE_DAY_OFFSETS[term]))
        spans.append(match.span())
    return dates, _blank_spans(text, spans)


def _consume_full_weekdays(text: str) -> tuple[list[int], str]:
    offsets: list[int] = []
    spans: list[tuple[int, int]] = []
    pattern = re.compile("|".join(_WEEKDAY_FULL))
    for match in pattern.finditer(text):
        offsets.append(_WEEKDAY_FULL[match.group(0)])
        spans.append(match.span())
    return offsets, _blank_spans(text, spans)


def _single_weekdays(text: str, *, week_term_present: bool) -> list[int]:
    offsets: list[int] = []
    for match in re.finditer(r"[월화수목금토일]", text):
        token = match.group(0)
        if token == "월" and match.start() > 0 and text[match.start() - 1].isdigit():
            continue
        if not week_term_present and not _is_standalone(text, match.start(), match.end()):
            continue
        offsets.append(_WEEKDAY_OFFSETS[token])
    return offsets


def _weekday_ranges(text: str) -> list[int]:
    offsets: list[int] = []
    token = r"(월요일|화요일|수요일|목요일|금요일|토요일|일요일|월|화|수|목|금|토|일)"
    patterns = [
        re.compile(rf"{token}\s*[~～]\s*{token}"),
        re.compile(rf"{token}\s*부터\s*{token}\s*까지"),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text):
            start = _weekday_token_offset(match.group(1))
            end = _weekday_token_offset(match.group(2))
            if start is None or end is None:
                continue
            if match.group(1) == "월" and match.start(1) > 0 and text[match.start(1) - 1].isdigit():
                continue
            if start <= end:
                offsets.extend(range(start, end + 1))
            else:
                offsets.extend([*range(start, 7), *range(0, end + 1)])
    return offsets


def _weekday_token_offset(token: str) -> int | None:
    if token in _WEEKDAY_FULL:
        return _WEEKDAY_FULL[token]
    return _WEEKDAY_OFFSETS.get(token)


def _find_week_terms(text: str) -> list[tuple[int, int, int]]:
    matches: list[tuple[int, int, int]] = []
    for pattern, offset in _WEEK_TERM_PATTERNS:
        for match in pattern.finditer(text):
            matches.append((match.start(), match.end(), offset))
    return sorted(matches, key=lambda item: item[0])


def _is_standalone(text: str, start: int, end: int) -> bool:
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    before_ok = start == 0 or before in _DELIMITERS
    after_ok = end == len(text) or after in _DELIMITERS
    return before_ok and after_ok


def _blank_spans(text: str, spans: list[tuple[int, int]]) -> str:
    if not spans:
        return text
    chars = list(text)
    for start, end in sorted(spans):
        for idx in range(start, end):
            chars[idx] = " "
    return "".join(chars)


def _spans_to_mask(spans: list[tuple[int, int]], length: int) -> list[bool]:
    mask = [False] * length
    for start, end in spans:
        mask[start:end] = [True] * (end - start)
    return mask


def _span_overlaps_mask(span: tuple[int, int], mask: list[bool]) -> bool:
    start, end = span
    return any(mask[start:end])


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _iso_sorted_capped(values) -> list[str]:
    return [item.isoformat() for item in sorted(set(values))[:5]]
