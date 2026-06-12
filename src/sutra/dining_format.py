from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


MEAL_LABELS = {"조식": "아침", "중식": "점심", "석식": "저녁"}
MEAL_ORDER = {"조식": 0, "중식": 1, "석식": 2}
AUDIENCE_ORDER = {"직원": 0, "학생": 1}
CAFETERIA_ORDER = ["제2학생회관", "제3학생회관", "제4학생회관", "생활과학대학"]
WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]


class DiningRecordLike(Protocol):
    date: str
    cafeteria: str
    meal: str
    audience: str
    menu_text: str
    menu_name: str | None
    price: str | None


@dataclass(frozen=True)
class DiningMenuRecord:
    date: str
    cafeteria: str
    meal: str
    audience: str
    menu_text: str
    menu_name: str | None = None
    price: str | None = None


def format_dining_day(records: list[DiningRecordLike], date: str) -> str:
    """Return the clean daily dining document text used by RAG and live tools."""
    date_records = [record for record in records if _include_daily_record(record, date)]
    if not date_records:
        return ""

    weekday = WEEKDAY_LABELS[datetime.strptime(date, "%Y-%m-%d").weekday()]
    title = f"{date} ({weekday}) 학생식당 식단"
    lines = [f"# {title}", "", f"{date} ({weekday}) 학식 메뉴입니다.", ""]

    by_cafeteria: dict[str, list[DiningRecordLike]] = defaultdict(list)
    for record in date_records:
        by_cafeteria[record.cafeteria].append(record)

    for cafeteria in CAFETERIA_ORDER:
        cafeteria_records = by_cafeteria.get(cafeteria, [])
        if not cafeteria_records:
            continue
        lines.append(f"## {cafeteria}")
        for record in sorted(cafeteria_records, key=lambda r: (MEAL_ORDER.get(r.meal, 99), AUDIENCE_ORDER.get(r.audience, 99))):
            lines.append(format_dining_line(record))
        lines.append("")

    return "\n".join(lines).strip()


def active_dining_cafeterias(records: list[DiningRecordLike], date: str) -> list[str]:
    cafeterias = {record.cafeteria for record in records if _include_daily_record(record, date)}
    return [cafeteria for cafeteria in CAFETERIA_ORDER if cafeteria in cafeterias]


def is_closed_record(record: DiningRecordLike) -> bool:
    return record.menu_text.replace(" ", "").strip() == "운영안함"


def format_dining_line(record: DiningRecordLike) -> str:
    meal = MEAL_LABELS.get(record.meal, record.meal)
    menu_label, items = split_menu_label_and_items(record)
    prefix = f"- {meal}({record.audience})"
    if menu_label and items:
        return f"{prefix} {menu_label}: {', '.join(items)}"
    if menu_label:
        return f"{prefix} {menu_label}"
    return f"{prefix}: {', '.join(items)}"


def split_menu_label_and_items(record: DiningRecordLike) -> tuple[str, list[str]]:
    lines = [line.strip() for line in record.menu_text.splitlines() if line.strip()]
    if not lines:
        return "", []

    first_line = record.menu_name or lines[0]
    remaining = lines[1:] if first_line == lines[0] or record.menu_name else lines
    label = first_line

    match = re.fullmatch(r"(.+?)\(([\d,]+)\)", first_line)
    if match:
        label = f"{match.group(1).strip()} {format_price(match.group(2))}"
    elif record.price:
        label = f"{first_line.strip()} {format_price(record.price)}"

    return label, remaining


def format_price(price: str | int) -> str:
    digits = re.sub(r"[^0-9]", "", str(price))
    if not digits:
        return str(price)
    return f"{int(digits):,}원"


def _include_daily_record(record: DiningRecordLike, date: str) -> bool:
    if record.date != date:
        return False
    if record.cafeteria not in CAFETERIA_ORDER:
        return False
    if not record.menu_text.strip():
        return False
    if is_closed_record(record):
        return False
    return True
