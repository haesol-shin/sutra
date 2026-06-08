from __future__ import annotations

from hashlib import sha1
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from nlp_term.collect.source_inventory import SourceSpec
from nlp_term.schemas import Domain, KnowledgeDoc, RawSource, SourceVerification


DINING_STRUCTURED_FIELDS = [
    "meal_date",
    "cafeteria",
    "meal_type",
    "user_type",
    "menu_name",
    "price",
    "menu_items",
    "is_closed",
    "closed_reason",
]
CALENDAR_STRUCTURED_FIELDS = [
    "academic_year",
    "month",
    "event_name",
    "start_date",
    "end_date",
    "semester",
    "is_range",
]
CALENDAR_SEARCH_ALIASES = {
    "하기방학": ["1학기 종강", "종강일", "여름방학 시작", "방학 시작"],
    "동기방학": ["2학기 종강", "종강일", "겨울방학 시작", "방학 시작"],
}
SHUTTLE_STRUCTURED_FIELDS = [
    "route_key",
    "route_name",
    "departure_times",
    "first_time",
    "last_time",
    "stops",
    "operation_count",
    "operation_period",
    "operating_days",
    "non_operating_days",
    "valid_start",
    "valid_end",
    "notes",
]
NOTICE_STRUCTURED_FIELDS = [
    "notice_no",
    "title",
    "posted_date",
    "author",
    "detail_url",
    "is_pinned",
    "hits",
    "has_attachment",
]


class BaseStructuredRow(BaseModel):
    source_id: str
    source_url: str
    label: int = Field(ge=0, le=4)
    domain: Domain
    raw_path: str
    raw_checksum: str
    raw_fetched_at: str
    parser_name: str
    parser_version: str
    verification_official_chain_ok: bool
    freshness_policy: str
    row_id: str
    row_type: str
    evidence_text: str

    @classmethod
    def provenance_from(
        cls,
        *,
        spec: SourceSpec,
        raw: RawSource,
        verification: SourceVerification,
        row_id: str,
        row_type: str,
        evidence_text: str,
    ) -> dict[str, object]:
        _validate_source_context(spec=spec, raw=raw, verification=verification)
        return {
            "source_id": spec.source_id,
            "source_url": raw.url,
            "label": spec.label,
            "domain": spec.domain,
            "raw_path": raw.raw_path,
            "raw_checksum": raw.checksum,
            "raw_fetched_at": raw.fetched_at,
            "parser_name": verification.parser_name,
            "parser_version": verification.parser_version,
            "verification_official_chain_ok": verification.official_chain_ok,
            "freshness_policy": spec.freshness_policy,
            "row_id": row_id,
            "row_type": row_type,
            "evidence_text": evidence_text,
        }


class DiningRow(BaseStructuredRow):
    row_type: Literal["dining_menu"] = "dining_menu"
    meal_date: str
    cafeteria: str
    meal_type: str
    user_type: str | None = None
    menu_name: str | None = None
    price: int | None = None
    menu_items: list[str] = Field(default_factory=list)
    is_closed: bool = False
    closed_reason: str | None = None

    @classmethod
    def from_source_context(
        cls,
        *,
        spec: SourceSpec,
        raw: RawSource,
        verification: SourceVerification,
        row_id: str,
        evidence_text: str,
        meal_date: str,
        cafeteria: str,
        meal_type: str,
        user_type: str | None,
        menu_name: str | None,
        price: int | None,
        menu_items: list[str],
        is_closed: bool,
        closed_reason: str | None,
    ) -> DiningRow:
        provenance = BaseStructuredRow.provenance_from(
            spec=spec,
            raw=raw,
            verification=verification,
            row_id=row_id,
            row_type="dining_menu",
            evidence_text=evidence_text,
        )
        return cls(
            **provenance,
            meal_date=meal_date,
            cafeteria=cafeteria,
            meal_type=meal_type,
            user_type=user_type,
            menu_name=menu_name,
            price=price,
            menu_items=menu_items,
            is_closed=is_closed,
            closed_reason=closed_reason,
        )

    def structured_payload(self) -> dict[str, Any]:
        return {
            "meal_date": self.meal_date,
            "cafeteria": self.cafeteria,
            "meal_type": self.meal_type,
            "user_type": self.user_type,
            "menu_name": self.menu_name,
            "price": self.price,
            "menu_items": self.menu_items,
            "is_closed": self.is_closed,
            "closed_reason": self.closed_reason,
        }

    def to_knowledge_doc(self) -> KnowledgeDoc:
        body = self._knowledge_body()
        metadata = {
            "structured": self.structured_payload(),
            "menu_date": self.meal_date,
            "location": self.cafeteria,
            "cafeteria": self.cafeteria,
            "meal_type": self.meal_type,
            "user_type": self.user_type,
            "structured_fields": DINING_STRUCTURED_FIELDS,
            "raw_path": self.raw_path,
            "raw_checksum": self.raw_checksum,
            "raw_fetched_at": self.raw_fetched_at,
            "verification_official_chain_ok": self.verification_official_chain_ok,
            "verification_parser_name": self.parser_name,
            "verification_parser_version": self.parser_version,
            "source_freshness_policy": self.freshness_policy,
            "parser": self.parser_name,
            "generation_method": "structured_row",
            "row_id": self.row_id,
            "row_type": self.row_type,
        }
        return KnowledgeDoc(
            doc_id=self.row_id,
            label=self.label,
            domain=self.domain,
            title=f"{self.meal_date} {self.cafeteria} {self.meal_type} 식단",
            body=body,
            date=self.meal_date,
            source_url=self.source_url,
            source_id=self.source_id,
            section=self.row_type,
            metadata=metadata,
        )

    def _knowledge_body(self) -> str:
        subject = f"{self.meal_date} {self.cafeteria} {self.meal_type}"
        if self.user_type:
            subject = f"{subject} {self.user_type}"
        if self.is_closed:
            reason = self.closed_reason or "운영안함"
            return f"{subject} 식단은 {reason}입니다."
        menu_label = self.menu_name or "메뉴"
        if self.price is not None:
            menu_label = f"{menu_label}({self.price})"
        items = ", ".join(self.menu_items)
        return f"{subject} {menu_label}: {items}."


class CalendarRow(BaseStructuredRow):
    row_type: Literal["academic_calendar_event"] = "academic_calendar_event"
    academic_year: int
    month: int
    event_name: str
    start_date: str
    end_date: str
    semester: str | None = None
    is_range: bool = False

    @classmethod
    def from_source_context(
        cls,
        *,
        spec: SourceSpec,
        raw: RawSource,
        verification: SourceVerification,
        row_id: str,
        evidence_text: str,
        academic_year: int,
        month: int,
        event_name: str,
        start_date: str,
        end_date: str,
        semester: str | None,
        is_range: bool,
    ) -> CalendarRow:
        provenance = BaseStructuredRow.provenance_from(
            spec=spec,
            raw=raw,
            verification=verification,
            row_id=row_id,
            row_type="academic_calendar_event",
            evidence_text=evidence_text,
        )
        return cls(
            **provenance,
            academic_year=academic_year,
            month=month,
            event_name=event_name,
            start_date=start_date,
            end_date=end_date,
            semester=semester,
            is_range=is_range,
        )

    def structured_payload(self) -> dict[str, Any]:
        return {
            "academic_year": self.academic_year,
            "month": self.month,
            "event_name": self.event_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "semester": self.semester,
            "is_range": self.is_range,
        }

    def to_knowledge_doc(self) -> KnowledgeDoc:
        date_span = self.start_date if self.start_date == self.end_date else f"{self.start_date}/{self.end_date}"
        search_aliases = self._search_aliases()
        metadata = {
            "structured": self.structured_payload(),
            "event_name": self.event_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "date_span": date_span,
            "search_aliases": search_aliases,
            "academic_year": self.academic_year,
            "month": self.month,
            "semester": self.semester,
            "structured_fields": CALENDAR_STRUCTURED_FIELDS,
            "raw_path": self.raw_path,
            "raw_checksum": self.raw_checksum,
            "raw_fetched_at": self.raw_fetched_at,
            "verification_official_chain_ok": self.verification_official_chain_ok,
            "verification_parser_name": self.parser_name,
            "verification_parser_version": self.parser_version,
            "source_freshness_policy": self.freshness_policy,
            "parser": self.parser_name,
            "generation_method": "structured_row",
            "row_id": self.row_id,
            "row_type": self.row_type,
        }
        return KnowledgeDoc(
            doc_id=self.row_id,
            label=self.label,
            domain=self.domain,
            title=f"{self.start_date} {self.event_name}",
            body=self._knowledge_body(),
            date=self.start_date,
            source_url=self.source_url,
            source_id=self.source_id,
            section=self.row_type,
            metadata=metadata,
        )

    def _knowledge_body(self) -> str:
        alias_sentence = self._alias_sentence()
        if self.start_date == self.end_date:
            return f"{self.academic_year}학년도 학사일정: {self.start_date} {self.event_name}.{alias_sentence}"
        return (
            f"{self.academic_year}학년도 학사일정: {self.event_name}은 "
            f"{self.start_date}부터 {self.end_date}까지입니다.{alias_sentence}"
        )

    def _search_aliases(self) -> list[str]:
        return CALENDAR_SEARCH_ALIASES.get(self.event_name, [])

    def _alias_sentence(self) -> str:
        aliases = self._search_aliases()
        if not aliases:
            return ""
        return f" 학생 표현으로는 {', '.join(aliases)}에 해당합니다."


class ShuttleRow(BaseStructuredRow):
    row_type: Literal["shuttle_route"] = "shuttle_route"
    route_key: str
    route_name: str
    departure_times: list[str] = Field(default_factory=list)
    first_time: str | None = None
    last_time: str | None = None
    stops: list[str] = Field(default_factory=list)
    operation_count: str | None = None
    operation_period: str | None = None
    operating_days: str
    non_operating_days: list[str] = Field(default_factory=list)
    valid_start: str
    valid_end: str
    notes: list[str] = Field(default_factory=list)

    @classmethod
    def from_source_context(
        cls,
        *,
        spec: SourceSpec,
        raw: RawSource,
        verification: SourceVerification,
        row_id: str,
        evidence_text: str,
        route_key: str,
        route_name: str,
        departure_times: list[str],
        first_time: str | None,
        last_time: str | None,
        stops: list[str],
        operation_count: str | None,
        operation_period: str | None,
        operating_days: str,
        non_operating_days: list[str],
        valid_start: str,
        valid_end: str,
        notes: list[str],
    ) -> ShuttleRow:
        provenance = BaseStructuredRow.provenance_from(
            spec=spec,
            raw=raw,
            verification=verification,
            row_id=row_id,
            row_type="shuttle_route",
            evidence_text=evidence_text,
        )
        return cls(
            **provenance,
            route_key=route_key,
            route_name=route_name,
            departure_times=departure_times,
            first_time=first_time,
            last_time=last_time,
            stops=stops,
            operation_count=operation_count,
            operation_period=operation_period,
            operating_days=operating_days,
            non_operating_days=non_operating_days,
            valid_start=valid_start,
            valid_end=valid_end,
            notes=notes,
        )

    def structured_payload(self) -> dict[str, Any]:
        return {
            "route_key": self.route_key,
            "route_name": self.route_name,
            "departure_times": self.departure_times,
            "first_time": self.first_time,
            "last_time": self.last_time,
            "stops": self.stops,
            "operation_count": self.operation_count,
            "operation_period": self.operation_period,
            "operating_days": self.operating_days,
            "non_operating_days": self.non_operating_days,
            "valid_start": self.valid_start,
            "valid_end": self.valid_end,
            "notes": self.notes,
        }

    def to_knowledge_doc(self) -> KnowledgeDoc:
        metadata = {
            "structured": self.structured_payload(),
            "route_key": self.route_key,
            "route_name": self.route_name,
            "departure_times": self.departure_times,
            "first_time": self.first_time,
            "last_time": self.last_time,
            "stops": self.stops,
            "operation_count": self.operation_count,
            "operation_period": self.operation_period,
            "operating_days": self.operating_days,
            "non_operating_days": self.non_operating_days,
            "valid_start": self.valid_start,
            "valid_end": self.valid_end,
            "date_span": f"{self.valid_start}/{self.valid_end}",
            "structured_fields": SHUTTLE_STRUCTURED_FIELDS,
            "raw_path": self.raw_path,
            "raw_checksum": self.raw_checksum,
            "raw_fetched_at": self.raw_fetched_at,
            "verification_official_chain_ok": self.verification_official_chain_ok,
            "verification_parser_name": self.parser_name,
            "verification_parser_version": self.parser_version,
            "source_freshness_policy": self.freshness_policy,
            "parser": self.parser_name,
            "generation_method": "structured_row",
            "row_id": self.row_id,
            "row_type": self.row_type,
        }
        return KnowledgeDoc(
            doc_id=self.row_id,
            label=self.label,
            domain=self.domain,
            title=f"2026학년도 셔틀버스 {self.route_name}",
            body=self._knowledge_body(),
            date=self.valid_start,
            source_url=self.source_url,
            source_id=self.source_id,
            section=self.row_type,
            metadata=metadata,
        )

    def _knowledge_body(self) -> str:
        departures = ", ".join(self.departure_times)
        stops = ", ".join(self.stops)
        non_operating = ", ".join(self.non_operating_days)
        notes = " ".join(self.notes)
        return (
            f"2026학년도 셔틀버스 {self.route_name}은 {self.valid_start}부터 {self.valid_end}까지 "
            f"{self.operating_days}에 정상 운행합니다. "
            f"평일 야간, 주말, 공휴일, 방학 등은 미운영입니다. "
            f"출발 시간표: {departures}. 첫차 {self.first_time}, 막차 {self.last_time}. "
            f"정류장 및 운행 노선: {stops}. "
            f"운행횟수는 {self.operation_count}, 운영기간 표기는 {self.operation_period}입니다. "
            f"미운영 조건: {non_operating}. {notes}"
        )


class NoticeRow(BaseStructuredRow):
    row_type: Literal["notice_board_item"] = "notice_board_item"
    notice_no: str
    title: str
    posted_date: str
    author: str
    detail_url: str
    is_pinned: bool = False
    hits: int | None = None
    has_attachment: bool = False

    @classmethod
    def from_source_context(
        cls,
        *,
        spec: SourceSpec,
        raw: RawSource,
        verification: SourceVerification,
        row_id: str,
        evidence_text: str,
        notice_no: str,
        title: str,
        posted_date: str,
        author: str,
        detail_url: str,
        is_pinned: bool,
        hits: int | None,
        has_attachment: bool,
    ) -> NoticeRow:
        provenance = BaseStructuredRow.provenance_from(
            spec=spec,
            raw=raw,
            verification=verification,
            row_id=row_id,
            row_type="notice_board_item",
            evidence_text=evidence_text,
        )
        return cls(
            **provenance,
            notice_no=notice_no,
            title=title,
            posted_date=posted_date,
            author=author,
            detail_url=detail_url,
            is_pinned=is_pinned,
            hits=hits,
            has_attachment=has_attachment,
        )

    def structured_payload(self) -> dict[str, Any]:
        return {
            "notice_no": self.notice_no,
            "title": self.title,
            "posted_date": self.posted_date,
            "author": self.author,
            "detail_url": self.detail_url,
            "is_pinned": self.is_pinned,
            "hits": self.hits,
            "has_attachment": self.has_attachment,
        }

    def to_knowledge_doc(self) -> KnowledgeDoc:
        metadata = {
            "structured": self.structured_payload(),
            "notice_no": self.notice_no,
            "notice_title": self.title,
            "posted_date": self.posted_date,
            "author": self.author,
            "detail_url": self.detail_url,
            "is_pinned": self.is_pinned,
            "hits": self.hits,
            "has_attachment": self.has_attachment,
            "structured_fields": NOTICE_STRUCTURED_FIELDS,
            "raw_path": self.raw_path,
            "raw_checksum": self.raw_checksum,
            "raw_fetched_at": self.raw_fetched_at,
            "verification_official_chain_ok": self.verification_official_chain_ok,
            "verification_parser_name": self.parser_name,
            "verification_parser_version": self.parser_version,
            "source_freshness_policy": self.freshness_policy,
            "parser": self.parser_name,
            "generation_method": "structured_row",
            "row_id": self.row_id,
            "row_type": self.row_type,
        }
        return KnowledgeDoc(
            doc_id=self.row_id,
            label=self.label,
            domain=self.domain,
            title=self.title,
            body=self._knowledge_body(),
            date=self.posted_date,
            source_url=self.detail_url,
            source_id=self.source_id,
            section=self.row_type,
            metadata=metadata,
        )

    def _knowledge_body(self) -> str:
        pinned = "상단 고정 공지" if self.is_pinned else "일반 공지"
        attachment = "첨부파일이 있습니다" if self.has_attachment else "첨부파일 표시는 없습니다"
        return (
            f"{self.title} 공지사항의 게시일은 {self.posted_date}입니다. "
            f"작성자는 {self.author}이고, 번호는 {self.notice_no}입니다. "
            f"{pinned}이며 {attachment}. 상세 링크: {self.detail_url}"
        )


def dining_row_id(
    *,
    source_id: str,
    meal_date: str,
    cafeteria: str,
    meal_type: str,
    user_type: str | None,
    ordinal_or_menu_key: str,
) -> str:
    parts = [
        source_id,
        "dining_menu",
        meal_date,
        cafeteria,
        meal_type,
        user_type or "",
        ordinal_or_menu_key,
    ]
    normalized = "__".join(_slug(part) for part in parts)
    digest = sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{normalized}__{digest}"


def calendar_row_id(
    *,
    source_id: str,
    academic_year: int,
    start_date: str,
    end_date: str,
    event_name: str,
    ordinal: int,
) -> str:
    parts = [
        source_id,
        "academic_calendar_event",
        str(academic_year),
        start_date,
        end_date,
        event_name,
        str(ordinal),
    ]
    normalized = "__".join(_slug(part) for part in parts)
    digest = sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{normalized}__{digest}"


def shuttle_row_id(
    *,
    source_id: str,
    route_key: str,
    valid_start: str,
    valid_end: str,
) -> str:
    parts = [
        source_id,
        "shuttle_route",
        route_key,
        valid_start,
        valid_end,
    ]
    normalized = "__".join(_slug(part) for part in parts)
    digest = sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{normalized}__{digest}"


def notice_row_id(
    *,
    source_id: str,
    notice_no: str,
    posted_date: str,
    title: str,
) -> str:
    parts = [
        source_id,
        "notice_board_item",
        notice_no,
        posted_date,
        title,
    ]
    normalized = "__".join(_slug(part) for part in parts)
    digest = sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{normalized}__{digest}"


def _validate_source_context(
    *,
    spec: SourceSpec,
    raw: RawSource,
    verification: SourceVerification,
) -> None:
    source_ids = {spec.source_id, raw.source_id, verification.source_id}
    if len(source_ids) != 1:
        raise ValueError(f"source_id mismatch: {sorted(source_ids)}")
    if spec.label != raw.label:
        raise ValueError(f"label mismatch for {spec.source_id}")
    if spec.domain != raw.domain:
        raise ValueError(f"domain mismatch for {spec.source_id}")
    if spec.url != raw.url:
        raise ValueError(f"url mismatch for {spec.source_id}")


def _slug(value: str) -> str:
    text = re.sub(r"\s+", "_", value.strip().lower())
    text = re.sub(r"[^0-9a-zA-Z가-힣_-]+", "", text)
    return text or "none"
