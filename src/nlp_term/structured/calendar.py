from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from bs4 import BeautifulSoup

from nlp_term.collect.source_inventory import SourceSpec
from nlp_term.paths import PROJECT_ROOT
from nlp_term.schemas import KnowledgeDoc, RawSource, SourceVerification
from nlp_term.structured.rows import CalendarRow, calendar_row_id


EVENT_RE = re.compile(
    r"(?P<start_month>\d{2})\.(?P<start_day>\d{2})\([^)]+\)"
    r"(?:\s*~\s*(?P<end_month>\d{2})\.(?P<end_day>\d{2})\([^)]+\))?"
    r"\s+(?P<name>.*?)(?=\s+\d{2}\.\d{2}\([^)]+\)|$)"
)
MONTH_RE = re.compile(r"(?P<month>\d{2})월")


@dataclass(frozen=True)
class _CalendarBox:
    index: int
    month: int
    text: str


class CalendarAdapter:
    source_id = "academic_calendar"
    academic_year = 2026

    def parse(
        self,
        *,
        spec: SourceSpec,
        raw: RawSource,
        verification: SourceVerification,
    ) -> list[CalendarRow]:
        raw_path = PROJECT_ROOT / raw.raw_path
        boxes = _calendar_boxes(raw_path)
        academic_year = _academic_year(spec)
        rows: list[CalendarRow] = []
        seen: set[tuple[str, str, str]] = set()
        ordinal = 0
        for box in boxes:
            box_year = _box_year(box, academic_year=academic_year)
            for match in EVENT_RE.finditer(box.text):
                event_name = " ".join(match.group("name").split())
                start_month = int(match.group("start_month"))
                start_day = int(match.group("start_day"))
                end_month = int(match.group("end_month") or start_month)
                end_day = int(match.group("end_day") or start_day)
                start_date = _iso_date(box_year, start_month, start_day)
                end_year = box_year + 1 if end_month < start_month else box_year
                end_date = _iso_date(end_year, end_month, end_day)
                key = (start_date, end_date, event_name)
                if key in seen:
                    continue
                seen.add(key)
                ordinal += 1
                rows.append(
                    CalendarRow.from_source_context(
                        spec=spec,
                        raw=raw,
                        verification=verification,
                        row_id=calendar_row_id(
                            source_id=spec.source_id,
                            academic_year=academic_year,
                            start_date=start_date,
                            end_date=end_date,
                            event_name=event_name,
                            ordinal=ordinal,
                        ),
                        evidence_text=match.group(0).strip(),
                        academic_year=academic_year,
                        month=box.month,
                        event_name=event_name,
                        event_type=_event_type(event_name),
                        aliases=_event_aliases(event_name),
                        start_date=start_date,
                        end_date=end_date,
                        semester=_semester(event_name),
                        is_range=end_date != start_date,
                    )
                )
        return rows

    def to_knowledge_docs(self, rows: list[CalendarRow]) -> list[KnowledgeDoc]:
        return [row.to_knowledge_doc() for row in rows]


def _calendar_boxes(raw_path: Path) -> list[_CalendarBox]:
    soup = BeautifulSoup(raw_path.read_bytes(), "lxml")
    boxes: list[_CalendarBox] = []
    for index, node in enumerate(soup.select(".calen_box")):
        text = " ".join(node.get_text(" ").split())
        month_match = MONTH_RE.search(text)
        if not month_match:
            continue
        boxes.append(_CalendarBox(index=index, month=int(month_match.group("month")), text=text))
    if not boxes:
        raise ValueError("calendar boxes not found")
    return boxes


def _academic_year(spec: SourceSpec) -> int:
    if spec.curriculum_year:
        return int(spec.curriculum_year)
    return CalendarAdapter.academic_year


def _box_year(box: _CalendarBox, *, academic_year: int) -> int:
    if box.index == 0 and box.month == 12:
        return academic_year - 1
    return academic_year


def _iso_date(year: int, month: int, day: int) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}"


def _semester(event_name: str) -> str | None:
    if "제1학기" in event_name or "1학기" in event_name:
        return "1학기"
    if "제2학기" in event_name or "2학기" in event_name:
        return "2학기"
    if "하기" in event_name:
        return "하기"
    if "동기" in event_name:
        return "동기"
    return None


def _event_type(event_name: str) -> str | None:
    if event_name in {"하기방학", "동기방학"}:
        return "semester_end"
    if event_name in {"하기 계절학기", "동기 계절학기"}:
        return "summer_session_end" if "하기" in event_name else "winter_session_end"
    if "중간고사" in event_name:
        return "midterm_period"
    if "수강신청" in event_name:
        return "course_registration"
    if "휴학" in event_name:
        return "leave_application"
    return None


def _event_aliases(event_name: str) -> list[str]:
    aliases: list[str] = []
    if event_name == "하기방학":
        aliases.extend(["1학기 종강", "이번 학기 종강", "종강일", "여름방학 시작", "방학 시작"])
    elif event_name == "동기방학":
        aliases.extend(["2학기 종강", "종강일", "겨울방학 시작", "방학 시작"])
    elif event_name == "하기 계절학기":
        aliases.extend(["여름 계절학기", "하계 계절학기", "계절학기 종강", "여름 계절학기 종강일"])
    elif event_name == "동기 계절학기":
        aliases.extend(["겨울 계절학기", "동계 계절학기", "계절학기 종강", "겨울 계절학기 종강일"])
    elif "수강신청" in event_name:
        aliases.extend(["수강 신청", "수강신청 일정", "수강신청 기간"])
    elif "휴학" in event_name:
        aliases.extend(["휴학 신청", "휴학 신청 마감", "휴복학 신청"])
    return aliases
