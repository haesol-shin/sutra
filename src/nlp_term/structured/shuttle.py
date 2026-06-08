from __future__ import annotations

from dataclasses import dataclass
import re

from bs4 import BeautifulSoup

from nlp_term.collect.source_inventory import SourceSpec
from nlp_term.paths import PROJECT_ROOT
from nlp_term.schemas import KnowledgeDoc, RawSource, SourceVerification
from nlp_term.structured.rows import ShuttleRow, ShuttleSegmentRow, shuttle_row_id, shuttle_segment_row_id


TIME_RE = re.compile(r"\d{1,2}:\d{2}")
ROUTE_MARK_RE = re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱]\s*")


@dataclass(frozen=True)
class _RouteDetails:
    route_text: str
    first_time: str | None
    last_time: str | None
    stops: list[str]
    operation_count: str | None
    operation_period: str | None


class ShuttleAdapter:
    source_id = "shuttle_bus"
    valid_start = "2026-03-03"
    valid_end = "2026-06-21"
    operating_days = "학기 중 평일 주간"
    non_operating_days = ["평일 야간", "주말", "공휴일", "방학", "수학능력시험일(10시 이전)"]

    def parse(
        self,
        *,
        spec: SourceSpec,
        raw: RawSource,
        verification: SourceVerification,
    ) -> list[ShuttleRow | ShuttleSegmentRow]:
        raw_path = PROJECT_ROOT / raw.raw_path
        soup = BeautifulSoup(raw_path.read_bytes(), "lxml")
        tables = soup.select("#txt table")
        if len(tables) < 2:
            raise ValueError("shuttle timetable tables not found")
        schedule_rows = _schedule_rows(tables[0])
        route_rows = _route_rows(tables[1])
        rows: list[ShuttleRow | ShuttleSegmentRow] = []
        notes = _operation_notes(soup)
        for route_key, route_name, departure_times, schedule_evidence in schedule_rows:
            details = route_rows.get(route_key)
            if details is None:
                continue
            route_row = ShuttleRow.from_source_context(
                spec=spec,
                raw=raw,
                verification=verification,
                row_id=shuttle_row_id(
                    source_id=spec.source_id,
                    route_key=route_key,
                    valid_start=self.valid_start,
                    valid_end=self.valid_end,
                ),
                evidence_text=f"{schedule_evidence} {details.route_text}".strip(),
                route_key=route_key,
                route_name=route_name,
                departure_times=departure_times,
                first_time=details.first_time,
                last_time=details.last_time,
                stops=details.stops,
                operation_count=details.operation_count,
                operation_period=details.operation_period,
                operating_days=self.operating_days,
                non_operating_days=self.non_operating_days,
                valid_start=self.valid_start,
                valid_end=self.valid_end,
                notes=notes,
            )
            rows.append(route_row)
            rows.extend(
                _segment_rows(
                    spec=spec,
                    raw=raw,
                    verification=verification,
                    route_key=route_key,
                    route_name=route_name,
                    departure_times=departure_times,
                    stops=details.stops,
                    valid_start=self.valid_start,
                    valid_end=self.valid_end,
                    operating_days=self.operating_days,
                )
            )
        return rows

    def to_knowledge_docs(self, rows: list[ShuttleRow | ShuttleSegmentRow]) -> list[KnowledgeDoc]:
        return [row.to_knowledge_doc() for row in rows]


def _segment_rows(
    *,
    spec: SourceSpec,
    raw: RawSource,
    verification: SourceVerification,
    route_key: str,
    route_name: str,
    departure_times: list[str],
    stops: list[str],
    valid_start: str,
    valid_end: str,
    operating_days: str,
) -> list[ShuttleSegmentRow]:
    rows: list[ShuttleSegmentRow] = []
    for index, departure_time in enumerate(departure_times, start=1):
        rows.append(
            _segment_row(
                spec=spec,
                raw=raw,
                verification=verification,
                route_key=route_key,
                route_name=route_name,
                segment_kind="departure_time",
                segment_value=departure_time,
                segment_index=index,
                valid_start=valid_start,
                valid_end=valid_end,
                operating_days=operating_days,
            )
        )
    for index, stop in enumerate(stops, start=1):
        rows.append(
            _segment_row(
                spec=spec,
                raw=raw,
                verification=verification,
                route_key=route_key,
                route_name=route_name,
                segment_kind="stop",
                segment_value=stop,
                segment_index=index,
                valid_start=valid_start,
                valid_end=valid_end,
                operating_days=operating_days,
            )
        )
    return rows


def _segment_row(
    *,
    spec: SourceSpec,
    raw: RawSource,
    verification: SourceVerification,
    route_key: str,
    route_name: str,
    segment_kind: str,
    segment_value: str,
    segment_index: int,
    valid_start: str,
    valid_end: str,
    operating_days: str,
) -> ShuttleSegmentRow:
    return ShuttleSegmentRow.from_source_context(
        spec=spec,
        raw=raw,
        verification=verification,
        row_id=shuttle_segment_row_id(
            source_id=spec.source_id,
            route_key=route_key,
            segment_kind=segment_kind,
            segment_value=segment_value,
            segment_index=segment_index,
            valid_start=valid_start,
            valid_end=valid_end,
        ),
        evidence_text=f"{route_name} {segment_kind} {segment_value}",
        route_key=route_key,
        route_name=route_name,
        segment_kind=segment_kind,
        segment_value=segment_value,
        segment_index=segment_index,
        valid_start=valid_start,
        valid_end=valid_end,
        operating_days=operating_days,
    )


def _schedule_rows(table) -> list[tuple[str, str, list[str], str]]:
    rows: list[tuple[str, str, list[str], str]] = []
    for tr in table.select("tr")[1:]:
        cells = [_cell_text(cell) for cell in tr.select("th, td")]
        if len(cells) < 2:
            continue
        route_key = _route_key(cells[0])
        route_name = _route_name(route_key)
        departure_times = [_normalize_time_text(cell) for cell in cells[1:] if _normalize_time_text(cell) != "미운영"]
        if not departure_times:
            continue
        rows.append((route_key, route_name, departure_times, " ".join(cells)))
    return rows


def _route_rows(table) -> dict[str, _RouteDetails]:
    details: dict[str, _RouteDetails] = {}
    for tr in table.select("tr")[2:]:
        cells = [_cell_text(cell) for cell in tr.select("th, td")]
        if len(cells) < 5:
            continue
        route_key = _route_key(cells[0])
        operation_text = cells[4]
        details[route_key] = _RouteDetails(
            route_text=cells[3],
            first_time=_first_time(cells[1]),
            last_time=_first_time(cells[2]),
            stops=_stops(cells[3]),
            operation_count=_operation_count(operation_text),
            operation_period=_operation_period(operation_text),
        )
    return details


def _operation_notes(soup: BeautifulSoup) -> list[str]:
    notes: list[str] = []
    for item in soup.select("#txt li"):
        text = _compact_spaces(item.get_text(" "))
        if text.startswith("운영기준:"):
            notes.append(text)
    return notes


def _route_key(text: str) -> str:
    if "캠퍼스 순환" in text:
        return "intercampus_loop"
    return "campus_loop"


def _route_name(route_key: str) -> str:
    if route_key == "intercampus_loop":
        return "캠퍼스 순환"
    return "교내 순환"


def _normalize_time_text(text: str) -> str:
    compact = _compact_spaces(text)
    match = TIME_RE.search(compact)
    if not match:
        return compact
    time_text = _normalize_time(match.group(0))
    suffix = compact[match.end() :].strip()
    return f"{time_text} {suffix}".strip()


def _first_time(text: str) -> str | None:
    match = TIME_RE.search(text)
    if not match:
        return None
    return _normalize_time(match.group(0))


def _normalize_time(value: str) -> str:
    hour, minute = value.split(":")
    return f"{int(hour):02d}:{minute}"


def _stops(route_text: str) -> list[str]:
    stops: list[str] = []
    for raw_part in re.split(r"\s*[→⟶]\s*", route_text):
        part = ROUTE_MARK_RE.sub("", raw_part).strip()
        part = re.sub(r"\([^)]*\d{1,2}:\s*\d{2}[^)]*\)", "", part)
        part = re.sub(r"\([^)]*\)", "", part)
        part = _compact_spaces(part)
        if "※" in part:
            part = part.split("※", 1)[0].strip()
        if part and part not in stops:
            stops.append(part)
    if "월평역" in route_text and "월평역" not in stops:
        stops.append("월평역")
    return stops


def _operation_count(text: str) -> str | None:
    match = re.search(r"\d+회", text)
    return match.group(0) if match else None


def _operation_period(text: str) -> str | None:
    compact = _compact_spaces(text)
    match = re.search(r"학기 중 운영\s*\(총\s*\d+일\)", compact)
    return match.group(0) if match else None


def _cell_text(cell) -> str:
    return _compact_spaces(cell.get_text(" "))


def _compact_spaces(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r":\s+", ":", text)
    return text.strip()
