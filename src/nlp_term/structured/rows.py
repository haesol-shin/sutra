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
        metadata = {
            "structured": self.structured_payload(),
            "event_name": self.event_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "date_span": date_span,
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
        if self.start_date == self.end_date:
            return f"{self.academic_year}학년도 학사일정: {self.start_date} {self.event_name}."
        return (
            f"{self.academic_year}학년도 학사일정: {self.event_name}은 "
            f"{self.start_date}부터 {self.end_date}까지입니다."
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
