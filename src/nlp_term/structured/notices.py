from __future__ import annotations

from urllib.parse import urljoin
import re

from bs4 import BeautifulSoup

from nlp_term.collect.source_inventory import SourceSpec
from nlp_term.paths import PROJECT_ROOT
from nlp_term.schemas import KnowledgeDoc, RawSource, SourceVerification
from nlp_term.structured.rows import NoticeRow, notice_row_id


DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")
HIGH_VALUE_KEYWORDS = (
    "졸업",
    "학사",
    "수강",
    "장학",
    "셔틀",
    "식단",
    "일정",
    "휴학",
    "복학",
    "등록",
    "계절학기",
)


class NoticeAdapter:
    source_id = "academic_notice_board"
    max_rows_per_board = 12
    min_high_value_score = 3

    def parse(
        self,
        *,
        spec: SourceSpec,
        raw: RawSource,
        verification: SourceVerification,
    ) -> list[NoticeRow]:
        raw_path = PROJECT_ROOT / raw.raw_path
        soup = BeautifulSoup(raw_path.read_bytes(), "lxml")
        rows: list[NoticeRow] = []
        seen: set[tuple[str, str, str]] = set()
        for tr in soup.select(".board_list tbody tr"):
            if len(rows) >= self.max_rows_per_board:
                break
            cells = tr.select("td")
            if len(cells) < 5:
                continue
            link = cells[1].select_one("a[href]")
            if link is None:
                continue
            title = _cell_text(link)
            posted_date = _cell_text(cells[3])
            if not title or not DATE_RE.fullmatch(posted_date):
                continue
            notice_no = _cell_text(cells[0])
            author = _cell_text(cells[2])
            hits = _parse_int(_cell_text(cells[4]))
            detail_url = urljoin(raw.url, link.get("href", ""))
            has_attachment = bool(cells[-1].select_one("img")) or "파일" in _cell_text(cells[-1])
            duplicate_key = (detail_url, posted_date, title)
            if duplicate_key in seen:
                continue
            seen.add(duplicate_key)
            high_value_score = _high_value_score(
                title=title,
                author=author,
                has_attachment=has_attachment,
                verification=verification,
            )
            if high_value_score < self.min_high_value_score:
                continue
            row_id = notice_row_id(
                source_id=spec.source_id,
                notice_no=notice_no,
                posted_date=posted_date,
                title=title,
            )
            evidence_text = f"{notice_no} {title} {author} {posted_date} {_cell_text(cells[4])}".strip()
            rows.append(
                NoticeRow.from_source_context(
                    spec=spec,
                    raw=raw,
                    verification=verification,
                    row_id=row_id,
                    evidence_text=evidence_text,
                    notice_no=notice_no,
                    title=title,
                    posted_date=posted_date,
                    author=author,
                    detail_url=detail_url,
                    is_pinned=notice_no == "공지",
                    hits=hits,
                    has_attachment=has_attachment,
                    high_value_score=high_value_score,
                )
            )
        if not rows:
            raise ValueError("notice board rows not found")
        return rows

    def to_knowledge_docs(self, rows: list[NoticeRow]) -> list[KnowledgeDoc]:
        return [row.to_knowledge_doc() for row in rows]


def _cell_text(cell) -> str:
    return " ".join(cell.get_text(" ").split())


def _parse_int(value: str) -> int | None:
    try:
        return int(value.replace(",", ""))
    except ValueError:
        return None


def _high_value_score(
    *,
    title: str,
    author: str,
    has_attachment: bool,
    verification: SourceVerification,
) -> int:
    score = 0
    if any(keyword in title for keyword in HIGH_VALUE_KEYWORDS):
        score += 1
    if has_attachment:
        score += 1
    if len(title) >= 20:
        score += 1
    if author:
        score += 1
    if verification.official_chain_ok:
        score += 1
    return score
