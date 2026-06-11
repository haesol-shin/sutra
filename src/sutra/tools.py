from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from typing import Callable
from urllib.parse import urlencode, urljoin
from zoneinfo import ZoneInfo

import requests

from sutra.config import Config, load_config
from sutra.dining_format import DiningMenuRecord, format_dining_day
from sutra.documents import load_documents
from sutra.models import Evidence
from sutra.retrieval import retrieve

logger = logging.getLogger(__name__)

FETCH_TIMEOUT = 15
USER_AGENT = "Sutra/1.0 (+https://github.com/local/sutra)"
MAX_TEXT_CHARS = 3000

UNIV_ACADEMIC_NOTICE_URL = (
    "https://plus.cnu.ac.kr/_prog/_board/"
    "?code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr"
)
UNIV_ACADEMIC_NOTICE_BASE = "https://plus.cnu.ac.kr/_prog/_board/"
CS_DEPT_NOTICE_URL = "https://computer.cnu.ac.kr/computer/notice/bachelor.do"
FOOD_URL = "https://mobileadmin.cnu.ac.kr/food/index.jsp"
ACADEMIC_CALENDAR_URL = (
    "https://plus.cnu.ac.kr/_prog/academic_calendar/"
    "?menu_dvs_cd=05020101&site_dvs_cd=kr"
)

CAFETERIAS = ["제1학생회관", "제2학생회관", "제3학생회관", "제4학생회관", "생활과학대학"]

SOURCE_REGISTRY = {
    "shuttle": {
        "url": "https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html",
        "desc": "충남대학교 학교셔틀버스 운행 안내",
    },
    # graduation_curriculum is omitted until a verified non-404 source URL is found.
    "course_registration_guide": {
        "url": "https://plus.cnu.ac.kr/html/kr/sub05/sub05_050203.html",
        "desc": "충남대학교 수강신청 안내",
    },
}

KNOWLEDGE_BASE_DOMAINS = ["academic_calendar", "calendar", "dining", "graduation", "shuttle"]

_HANDLERS: dict[str, Callable[..., list[Evidence]]] = {}
_WORKSPACE_CONTEXT: ContextVar[str | Config | None] = ContextVar("sutra_tool_workspace", default=None)


@dataclass
class NoticeItem:
    title: str
    author: str
    date: str
    url: str
    pinned: bool


def tool(name: str, description: str, parameters: dict | None = None):
    """Register a callable function as an LLM tool."""
    params = parameters or {"type": "object", "properties": {}}

    def decorator(fn: Callable[..., list[Evidence]]):
        _HANDLERS[name] = fn
        fn._tool_name = name
        fn._tool_description = description
        fn._tool_parameters = params
        return fn

    return decorator


def get_tool_definitions(*, include_knowledge_base: bool = False) -> list[dict]:
    """All registered tools as OpenAI-compatible function definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": h._tool_name,
                "description": h._tool_description,
                "parameters": h._tool_parameters,
            },
        }
        for h in _HANDLERS.values()
        if include_knowledge_base or h._tool_name != "search_knowledge_base"
    ]


def dispatch(
    name: str,
    arguments: str | dict | None = None,
    *,
    workspace: str | Config | None = None,
) -> list[Evidence]:
    """Invoke a registered tool by name and return Evidence objects."""
    handler = _HANDLERS.get(name)
    if handler is None:
        logger.warning("Unknown tool requested: %s", name)
        return []
    token = _WORKSPACE_CONTEXT.set(workspace) if workspace is not None else None
    try:
        parsed = _parse_tool_arguments(arguments)
        return handler(**parsed)
    except Exception:
        logger.warning("Tool %s execution failed", name, exc_info=True)
        return []
    finally:
        if token is not None:
            _WORKSPACE_CONTEXT.reset(token)


# Helpers


def _parse_tool_arguments(arguments: str | dict | None) -> dict:
    if arguments is None or arguments == "":
        return {}
    if isinstance(arguments, dict):
        return arguments
    data = json.loads(arguments)
    return data if isinstance(data, dict) else {}


def _get(url: str, *, params: dict[str, str] | None = None) -> str:
    response = requests.get(
        url,
        params=params,
        timeout=FETCH_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    if "charset" not in response.headers.get("Content-Type", "").lower():
        response.encoding = "utf-8"
    return response.text


def _clean_html(raw: str) -> str:
    text = re.sub(r"(?is)<script\b.*?</script>", " ", raw)
    text = re.sub(r"(?is)<style\b.*?</style>", " ", text)
    text = re.sub(r"(?is)<nav\b.*?</nav>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _html_lines(raw: str) -> list[str]:
    text = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    text = re.sub(r"</(?:p|h3|li|td|tr)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def _rows(html: str) -> list[str]:
    body_match = re.search(r"(?is)<tbody[^>]*>(.*?)</tbody>", html)
    body = body_match.group(1) if body_match else html
    return re.findall(r"(?is)<tr\b[^>]*>(.*?)</tr>", body)


def _cells(row_html: str, tag: str = "td") -> list[str]:
    return re.findall(rf"(?is)<{tag}\b[^>]*>(.*?)</{tag}>", row_html)


def _cell_entries(row_html: str, tag: str = "td") -> list[tuple[str, str]]:
    return re.findall(rf"(?is)<{tag}\b([^>]*)>(.*?)</{tag}>", row_html)


def _span_attr(attrs: str, name: str) -> int:
    match = re.search(rf"""\b{name}\s*=\s*(?:"(\d+)"|'(\d+)'|(\d+))""", attrs, re.I)
    if not match:
        return 1
    value = next(group for group in match.groups() if group is not None)
    return max(1, int(value))


def _expanded_table_rows(html: str) -> list[list[str]]:
    active_rowspans: dict[int, tuple[str, int]] = {}
    expanded: list[list[str]] = []

    for row in _rows(html):
        grid: dict[int, str] = {}
        next_rowspans: dict[int, tuple[str, int]] = {}
        column = 0

        def place_active_spans() -> None:
            nonlocal column
            while column in active_rowspans:
                cell, remaining = active_rowspans[column]
                grid[column] = cell
                if remaining > 1:
                    next_rowspans[column] = (cell, remaining - 1)
                column += 1

        for attrs, cell in _cell_entries(row):
            place_active_spans()
            rowspan = _span_attr(attrs, "rowspan")
            colspan = _span_attr(attrs, "colspan")
            for offset in range(colspan):
                target_column = column + offset
                grid[target_column] = cell
                if rowspan > 1:
                    next_rowspans[target_column] = (cell, rowspan - 1)
            column += colspan

        while any(active_column >= column for active_column in active_rowspans):
            place_active_spans()
            if any(active_column >= column for active_column in active_rowspans):
                column = min(active_column for active_column in active_rowspans if active_column >= column)

        active_rowspans = next_rowspans
        if grid:
            expanded.append([grid.get(index, "") for index in range(max(grid) + 1)])

    return expanded


def _first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.I | re.S)
    return match.group(1).strip() if match else ""


def _notice_text(regular: list[NoticeItem], pinned: list[NoticeItem]) -> str:
    lines = ["최신 공지"]
    lines.extend(_format_notice(item) for item in regular)
    if pinned:
        lines.append("")
        lines.append("고정 공지")
        lines.extend(_format_notice(item) for item in pinned)
    return "\n".join(lines).strip()


def _format_notice(item: NoticeItem) -> str:
    return f"[{item.date}] {item.title} ({item.author}) — {item.url}"


def _normalize_short_date(value: str) -> str:
    value = _clean_html(value)
    match = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{2})", value)
    if match:
        year, month, day = match.groups()
        return f"20{year}-{month}-{day}"
    return value


def _today_kst() -> datetime:
    return datetime.now(ZoneInfo("Asia/Seoul"))


def _source_url_with_params(url: str, params: dict[str, str]) -> str:
    return f"{url}?{urlencode(params)}"


# Tool handlers


@tool(
    name="search_knowledge_base",
    description="워크스페이스에 저장된 지식 베이스 문서를 검색해 관련 근거를 반환한다.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "검색할 질문 또는 키워드",
            },
            "domain": {
                "type": ["string", "null"],
                "enum": [*KNOWLEDGE_BASE_DOMAINS, None],
                "description": "선택적 문서 도메인 필터",
            },
        },
        "required": ["query"],
    },
)
def search_knowledge_base(query: str, domain: str | None = None) -> list[Evidence]:
    workspace = _WORKSPACE_CONTEXT.get()
    if workspace is None or not query.strip():
        return []

    config = workspace if isinstance(workspace, Config) else load_config(workspace)
    documents = load_documents(config)
    if domain:
        documents = [doc for doc in documents if _matches_domain(doc.id, doc.metadata, domain)]
    pack = retrieve(query, documents, config)
    return [
        item.model_copy(
            update={
                "metadata": {
                    **item.metadata,
                    "tool": "search_knowledge_base",
                    "domain": domain,
                }
            }
        )
        for item in pack.items
    ]


def _matches_domain(document_id: str, metadata: dict, domain: str) -> bool:
    expected = domain.lower()
    normalized_id = document_id.lower()
    candidates = {
        str(metadata.get("domain", "")).lower(),
        str(metadata.get("label", "")).lower(),
    }
    return (
        expected in candidates
        or normalized_id.startswith(f"{expected}_")
        or normalized_id.startswith(f"{expected}-")
    )


@tool(
    name="fetch_recent_notices",
    description="충남대학교 본부 또는 컴퓨터융합학부 게시판의 최신 공지를 가져와 최신 공지와 고정 공지를 분리한다.",
    parameters={
        "type": "object",
        "properties": {
            "board": {
                "type": "string",
                "enum": ["univ_academic", "cs_dept"],
                "default": "univ_academic",
                "description": "조회할 공지 게시판",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "default": 10,
                "description": "최신 일반 공지 개수",
            },
        },
    },
)
def fetch_recent_notices(board: str = "univ_academic", limit: int = 10) -> list[Evidence]:
    try:
        limit = max(1, min(int(limit), 20))
        if board == "cs_dept":
            html = _get(CS_DEPT_NOTICE_URL)
            items = _parse_cs_notices(html)
            title = "컴퓨터융합학부 학사공지"
            source_url = CS_DEPT_NOTICE_URL
        else:
            html = _get(UNIV_ACADEMIC_NOTICE_URL)
            items = _parse_univ_notices(html)
            title = "충남대학교 학사공지"
            source_url = UNIV_ACADEMIC_NOTICE_URL
    except Exception:
        logger.warning("Failed to fetch notices", exc_info=True)
        return []

    regular = sorted((item for item in items if not item.pinned), key=lambda item: item.date, reverse=True)[:limit]
    pinned = sorted((item for item in items if item.pinned), key=lambda item: item.date, reverse=True)[:limit]
    if not regular and not pinned:
        return []
    return [
        Evidence(
            id=f"live_notices_{board}",
            title=title,
            text=_notice_text(regular, pinned),
            source_url=source_url,
            source_name=title,
            metadata={"tool": "fetch_recent_notices", "board": board},
        )
    ]


def _parse_univ_notices(html: str) -> list[NoticeItem]:
    items: list[NoticeItem] = []
    for row in _rows(html):
        cells = _cells(row)
        if len(cells) < 4:
            continue
        num = _clean_html(cells[0])
        href = _first_match(r"<a\b[^>]*href=[\"']([^\"']+)[\"']", cells[1]).replace("&amp;", "&")
        title = _clean_html(cells[1])
        author = _clean_html(cells[2])
        date = _clean_html(cells[3])
        if not title or not date:
            continue
        items.append(
            NoticeItem(
                title=title,
                author=author,
                date=date,
                url=urljoin(UNIV_ACADEMIC_NOTICE_BASE, href),
                pinned=num == "공지",
            )
        )
    return items


def _parse_cs_notices(html: str) -> list[NoticeItem]:
    items: list[NoticeItem] = []
    for row in _rows(html):
        cells = _cells(row)
        if len(cells) < 2:
            continue
        num = _clean_html(cells[0])
        title_cell = cells[1]
        href = _first_match(r"<a\b[^>]*href=[\"']([^\"']+)[\"']", title_cell).replace("&amp;", "&")
        title = _clean_html(_first_match(r"(?is)<div\b[^>]*class=[\"'][^\"']*b-title-box[^\"']*[\"'][^>]*>.*?<a\b[^>]*>(.*?)</a>", row))
        if not title:
            title = _clean_html(title_cell)
        author = _clean_html(_first_match(r"<span\b[^>]*class=[\"'][^\"']*b-writer[^\"']*[\"'][^>]*>(.*?)</span>", row))
        date = _normalize_short_date(_first_match(r"<span\b[^>]*class=[\"'][^\"']*b-date[^\"']*[\"'][^>]*>(.*?)</span>", row))
        if not author and len(cells) >= 3:
            author = _clean_html(cells[-3])
        if not date and len(cells) >= 2:
            date = _normalize_short_date(_clean_html(cells[-2]))
        if not title or not date:
            continue
        items.append(
            NoticeItem(
                title=title,
                author=author,
                date=date,
                url=urljoin(CS_DEPT_NOTICE_URL, href),
                pinned=num == "공지",
            )
        )
    return items


@tool(
    name="fetch_cafeteria_menu",
    description="충남대학교 학생회관 식단을 날짜와 식당별로 구조화해 가져온다.",
    parameters={
        "type": "object",
        "properties": {
            "date": {
                "type": ["string", "null"],
                "description": "조회 날짜. YYYY-MM-DD 형식이며 생략하면 KST 오늘",
            },
            "cafeteria": {
                "type": ["string", "null"],
                "enum": [*CAFETERIAS, None],
                "description": "조회할 식당. 생략하면 전체",
            },
        },
    },
)
def fetch_cafeteria_menu(date: str | None = None, cafeteria: str | None = None) -> list[Evidence]:
    try:
        target_date = date or _today_kst().strftime("%Y-%m-%d")
        params = {
            "searchYmd": target_date.replace("-", "."),
            "searchLang": "OCL04.10",
            "searchView": "",
            "searchCafeteria": "OCL03.02",
        }
        html = _get(FOOD_URL, params=params)
        records = _parse_cafeteria_menu(html, target_date, cafeteria)
        text = format_dining_day(records, target_date)
    except Exception:
        logger.warning("Failed to fetch cafeteria menu", exc_info=True)
        return []
    if not text:
        return []
    return [
        Evidence(
            id="live_cafeteria_menu",
            title="충남대학교 식단",
            text=text,
            source_url=_source_url_with_params(FOOD_URL, params),
            source_name="충남대학교 식단",
            metadata={"tool": "fetch_cafeteria_menu", "date": target_date, "cafeteria": cafeteria},
        )
    ]


def _parse_cafeteria_menu(html: str, target_date: str, cafeteria: str | None) -> list[DiningMenuRecord]:
    wanted = CAFETERIAS if cafeteria is None else [cafeteria]
    records: list[DiningMenuRecord] = []
    current_meal = ""
    for cells in _expanded_table_rows(html):
        if len(cells) < 2:
            continue
        first = _clean_html(cells[0])
        if first in {"조식", "중식", "석식"}:
            current_meal = first
        if not current_meal:
            continue
        audience = _clean_html(cells[1])
        if audience not in {"직원", "학생"}:
            continue
        for offset, name in enumerate(CAFETERIAS):
            if name not in wanted:
                continue
            menu_column = offset + 2
            if menu_column >= len(cells):
                continue
            cell = cells[menu_column]
            parsed = _parse_menu_cell(cell)
            if parsed is None:
                continue
            menu_text, menu_name, price = parsed
            records.append(
                DiningMenuRecord(
                    date=target_date,
                    cafeteria=name,
                    meal=current_meal,
                    audience=audience,
                    menu_text=menu_text,
                    menu_name=menu_name,
                    price=price,
                )
            )
    return records


def _parse_menu_cell(cell: str) -> tuple[str, str | None, str | None] | None:
    cleaned = _clean_html(cell)
    if not cleaned:
        return None
    normalized = cleaned.replace(" ", "")
    if "메뉴운영내역" in normalized or "메뉴는운영중입니다" in normalized or "메뉴는준비중입니다" in normalized:
        return None
    if "운영안함" in cleaned:
        return "운영안함", None, None
    title = _clean_html(_first_match(r"<h3\b[^>]*>(.*?)</h3>", cell))
    body = _first_match(r"<p\b[^>]*>(.*?)</p>", cell)
    items = [item for item in _html_lines(body) if item]
    if title:
        price_match = re.search(r"\(([\d,]+)\)", title)
        menu_text = "\n".join([title, *items]) if items else title
        return menu_text, title, price_match.group(1) if price_match else None
    return cleaned, None, None


@tool(
    name="fetch_academic_calendar",
    description="충남대학교 학사일정을 월 단위로 조회한다. 월을 생략하면 KST 현재월과 다음월을 반환한다.",
    parameters={
        "type": "object",
        "properties": {
            "month": {
                "type": ["integer", "null"],
                "minimum": 1,
                "maximum": 12,
                "description": "조회할 월. 생략하면 현재월과 다음월",
            },
        },
    },
)
def fetch_academic_calendar(month: int | None = None) -> list[Evidence]:
    today = _today_kst()
    months = [int(month)] if month else [today.month, 1 if today.month == 12 else today.month + 1]
    try:
        html = _get(ACADEMIC_CALENDAR_URL)
        lines = _parse_academic_calendar(html, months)
    except Exception:
        logger.warning("Failed to fetch academic calendar", exc_info=True)
        return []
    if not lines:
        return []
    header = f"오늘: {today.strftime('%Y-%m-%d')} (KST)"
    return [
        Evidence(
            id="live_academic_calendar",
            title="충남대학교 학사일정",
            text="\n".join([header, *lines]),
            source_url=ACADEMIC_CALENDAR_URL,
            source_name="충남대학교 학사일정",
            metadata={"tool": "fetch_academic_calendar", "months": months},
        )
    ]


def _parse_academic_calendar(html: str, months: list[int]) -> list[str]:
    lines: list[str] = []
    for block in re.findall(r"(?is)<div\b[^>]*class=[\"'][^\"']*calen_box[^\"']*[\"'][^>]*>(.*?)(?=<div\b[^>]*class=[\"'][^\"']*calen_box|</body>|$)", html):
        month_text = _first_match(r"<div\b[^>]*class=[\"'][^\"']*fl_month[^\"']*[\"'][^>]*>.*?<strong>(\d{2})월</strong>", block)
        if month_text and int(month_text) not in months:
            continue
        for date_text, event in re.findall(r"(?is)<li>\s*<strong>(.*?)</strong>\s*<span\b[^>]*class=[\"']list[\"'][^>]*>(.*?)</span>", block):
            normalized = _normalize_calendar_date(_clean_html(date_text))
            if not _calendar_date_intersects(normalized, months):
                continue
            lines.append(f"[{normalized}] {_clean_html(event)}")
    return lines


def _normalize_calendar_date(value: str) -> str:
    compact = re.sub(r"\([^)]+\)", "", value)
    compact = re.sub(r"\s+", "", compact)
    compact = compact.replace("~", "~")
    parts = compact.split("~", 1)
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]}~{parts[1]}"


def _calendar_date_intersects(date_text: str, months: list[int]) -> bool:
    found = [int(match) for match in re.findall(r"(\d{2})\.\d{2}", date_text)]
    return any(month in months for month in found)


@tool(
    name="fetch_page_text",
    description="허용된 CNU 정보원(source_id)의 본문 텍스트를 추출한다.",
    parameters={
        "type": "object",
        "properties": {
            "source_id": {
                "type": "string",
                "enum": list(SOURCE_REGISTRY.keys()),
                "description": "조회할 허용 정보원 ID",
            },
        },
        "required": ["source_id"],
    },
)
def fetch_page_text(source_id: str) -> list[Evidence]:
    source = SOURCE_REGISTRY.get(source_id)
    if source is None:
        return []
    try:
        html = _get(source["url"])
        text = _extract_page_text(html, source["desc"])[:MAX_TEXT_CHARS].rstrip()
    except Exception:
        logger.warning("Failed to fetch registry source %s", source_id, exc_info=True)
        return []
    if not text:
        return []
    return [
        Evidence(
            id=f"live_page_{source_id}",
            title=source["desc"],
            text=text,
            source_url=source["url"],
            source_name=source["desc"],
            metadata={"tool": "fetch_page_text", "source_id": source_id},
        )
    ]


def _extract_page_text(html: str, desc: str = "") -> str:
    main = _first_match(r"(?is)<main\b[^>]*>(.*?)</main>", html)
    if not main:
        main = _first_match(r"(?is)<div\b[^>]*id=[\"']content[\"'][^>]*>(.*?)</div>", html)
    return _strip_leading_page_chrome(_clean_html(main or html), desc)


def _strip_leading_page_chrome(text: str, desc: str = "") -> str:
    nav_tokens = ("사이트맵", "본문 바로가기", "사이드메뉴", "통합검색")
    token_positions = [(text.rfind(token), token) for token in nav_tokens]
    position, token = max(token_positions, key=lambda item: item[0])
    if position >= 0:
        text = text[position + len(token) :].lstrip()

    for keyword in _content_keywords(desc):
        index = text.find(keyword)
        if index <= 0:
            continue
        prefix = text[max(0, index - 20) : index]
        year_match = re.search(r"\d{4}학년도\s*$", prefix)
        if year_match:
            text = text[max(0, index - 20) + year_match.start() :].lstrip()
        else:
            text = text[index:].lstrip()
        break

    footer_tokens = ("만족도조사", "자료관리 담당부서", "Copyright 2024 CNU", "Copyright 2025 CNU")
    for footer in footer_tokens:
        idx = text.find(footer)
        if idx > 0:
            text = text[:idx].rstrip()
            break

    return text


def _content_keywords(desc: str) -> list[str]:
    return [word for word in re.split(r"\s+", desc) if len(word) >= 4]
