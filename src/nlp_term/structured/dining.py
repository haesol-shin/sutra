from __future__ import annotations

import re

from bs4 import BeautifulSoup

from nlp_term.collect.source_inventory import SourceSpec
from nlp_term.paths import PROJECT_ROOT
from nlp_term.schemas import KnowledgeDoc, RawSource, SourceVerification
from nlp_term.structured.rows import DiningRow, dining_row_id


DATE_RE = re.compile(r"20\d{2}\.\d{2}\.\d{2}")
PRICE_RE = re.compile(r"^(?P<name>[^()\s]+)\((?P<price>\d+)\)")


class DiningAdapter:
    source_id = "cnu_mobile_food"

    def parse(
        self,
        *,
        spec: SourceSpec,
        raw: RawSource,
        verification: SourceVerification,
    ) -> list[DiningRow]:
        raw_path = PROJECT_ROOT / raw.raw_path
        soup = BeautifulSoup(raw_path.read_bytes(), "lxml")
        table = _menu_table(soup)
        if _is_weekly_table(table):
            return _weekly_rows(spec=spec, raw=raw, verification=verification, soup=soup, table=table)
        meal_date = _extract_active_date(soup)
        cafeterias = _cafeterias(table)
        rows: list[DiningRow] = []
        current_meal_type = ""
        ordinal = 0
        for tr in table.select("tr")[1:]:
            cells = [_cell_text(cell) for cell in tr.select("th, td")]
            if not cells:
                continue
            meal_type, user_type, menu_cells = _split_menu_row(cells, current_meal_type)
            if meal_type:
                current_meal_type = meal_type
            if not current_meal_type or not user_type:
                continue
            for cafeteria, menu_text in zip(cafeterias, menu_cells):
                ordinal += 1
                rows.append(
                    _dining_row(
                        spec=spec,
                        raw=raw,
                        verification=verification,
                        meal_date=meal_date,
                        cafeteria=cafeteria,
                        meal_type=current_meal_type,
                        user_type=user_type,
                        menu_text=menu_text,
                        ordinal=ordinal,
                    )
                )
        return rows

    def to_knowledge_docs(self, rows: list[DiningRow]) -> list[KnowledgeDoc]:
        return [row.to_knowledge_doc() for row in rows]


def _weekly_rows(
    *,
    spec: SourceSpec,
    raw: RawSource,
    verification: SourceVerification,
    soup: BeautifulSoup,
    table,
) -> list[DiningRow]:
    dates = _week_dates(table)
    cafeteria = _selected_cafeteria(soup)
    rows: list[DiningRow] = []
    current_meal_type = ""
    ordinal = 0
    for tr in table.select("tr")[1:]:
        cells = [_cell_text(cell) for cell in tr.select("th, td")]
        if not cells:
            continue
        meal_type, user_type, menu_cells = _split_menu_row(cells, current_meal_type)
        if meal_type:
            current_meal_type = meal_type
        if not current_meal_type or not user_type:
            continue
        for meal_date, menu_text in zip(dates, menu_cells):
            ordinal += 1
            rows.append(
                _dining_row(
                    spec=spec,
                    raw=raw,
                    verification=verification,
                    meal_date=meal_date,
                    cafeteria=cafeteria,
                    meal_type=current_meal_type,
                    user_type=user_type,
                    menu_text=menu_text,
                    ordinal=ordinal,
                )
            )
    return rows


def _extract_active_date(soup: BeautifulSoup) -> str:
    text = " ".join(soup.get_text(" ").split())
    matches = DATE_RE.findall(text)
    if not matches:
        raise ValueError("dining page does not contain a menu date")
    # The selected day appears again after the weekday tabs; use the first repeated date if present.
    for match in matches:
        if matches.count(match) > 1:
            return match.replace(".", "-")
    return matches[0].replace(".", "-")


def _menu_table(soup: BeautifulSoup):
    for table in soup.select("table"):
        header = [_cell_text(cell) for cell in table.select("tr:first-child th, tr:first-child td")]
        if "구분" in header and any("학생회관" in cell for cell in header):
            return table
        if "구분" in header and any(DATE_RE.search(cell) for cell in header):
            return table
    raise ValueError("dining menu table not found")


def _is_weekly_table(table) -> bool:
    header = [_cell_text(cell) for cell in table.select("tr:first-child th, tr:first-child td")]
    return any(DATE_RE.search(cell) for cell in header)


def _week_dates(table) -> list[str]:
    header = [_cell_text(cell) for cell in table.select("tr:first-child th, tr:first-child td")]
    dates = []
    for cell in header:
        match = DATE_RE.search(cell)
        if match:
            dates.append(match.group(0).replace(".", "-"))
    if not dates:
        raise ValueError("weekly dining table does not contain dates")
    return dates


def _selected_cafeteria(soup: BeautifulSoup) -> str:
    selected = soup.select_one("li.over")
    if selected is not None:
        text = _cell_text(selected)
        if text:
            return text
    raise ValueError("weekly dining table does not identify selected cafeteria")


def _cafeterias(table) -> list[str]:
    header = [_cell_text(cell) for cell in table.select("tr:first-child th, tr:first-child td")]
    return [cell for cell in header if cell != "구분"]


def _split_menu_row(cells: list[str], current_meal_type: str) -> tuple[str, str, list[str]]:
    first = cells[0]
    if first in {"조식", "중식", "석식"}:
        if len(cells) < 2:
            return first, "", []
        return first, cells[1], cells[2:]
    if current_meal_type:
        return "", first, cells[1:]
    return "", "", []


def _dining_row(
    *,
    spec: SourceSpec,
    raw: RawSource,
    verification: SourceVerification,
    meal_date: str,
    cafeteria: str,
    meal_type: str,
    user_type: str,
    menu_text: str,
    ordinal: int,
) -> DiningRow:
    menu_name, price, items, is_closed, closed_reason = _parse_menu(menu_text)
    row_id = dining_row_id(
        source_id=spec.source_id,
        meal_date=meal_date,
        cafeteria=cafeteria,
        meal_type=meal_type,
        user_type=user_type,
        ordinal_or_menu_key=str(ordinal),
    )
    evidence_text = f"{meal_date} {cafeteria} {meal_type} {user_type} {menu_text}".strip()
    return DiningRow.from_source_context(
        spec=spec,
        raw=raw,
        verification=verification,
        row_id=row_id,
        evidence_text=evidence_text,
        meal_date=meal_date,
        cafeteria=cafeteria,
        meal_type=meal_type,
        user_type=user_type,
        menu_name=menu_name,
        price=price,
        menu_items=items,
        is_closed=is_closed,
        closed_reason=closed_reason,
    )


def _parse_menu(menu_text: str) -> tuple[str | None, int | None, list[str], bool, str | None]:
    if not menu_text or menu_text == "운영안함":
        return None, None, [], True, "운영안함"
    clean_text = re.sub(r"\([^)]*included\)", "", menu_text)
    tokens = clean_text.split()
    menu_name = None
    price = None
    if tokens:
        match = PRICE_RE.match(tokens[0])
        if match:
            menu_name = match.group("name")
            price = int(match.group("price"))
            tokens = tokens[1:]
    return menu_name, price, tokens, False, None


def _cell_text(cell) -> str:
    return " ".join(cell.get_text(" ").split())
