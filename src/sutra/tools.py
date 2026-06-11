from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
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
NOTICE_REQUEST_TIMEOUT = 8
NOTICE_SEARCH_STAGE_TIMEOUT = 20
NOTICE_BODY_STAGE_TIMEOUT = 10
NOTICE_PER_BOARD_FETCH_LIMIT = 5
NOTICE_INTEGRATED_REGULAR_LIMIT = 10
NOTICE_INTEGRATED_PINNED_LIMIT = 5
USER_AGENT = "Sutra/1.0 (+https://github.com/local/sutra)"
MAX_TEXT_CHARS = 3000

UNIV_ACADEMIC_NOTICE_URL = (
    "https://plus.cnu.ac.kr/_prog/_board/"
    "?code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr"
)
UNIV_NEWS_NOTICE_URL = (
    "https://plus.cnu.ac.kr/_prog/_board/"
    "?code=sub07_0701&menu_dvs_cd=0701&site_dvs_cd=kr"
)
UNIV_ACADEMIC_NOTICE_BASE = "https://plus.cnu.ac.kr/_prog/_board/"
CS_BACHELOR_NOTICE_URL = "https://computer.cnu.ac.kr/computer/notice/bachelor.do"
CS_NEWS_NOTICE_URL = "https://computer.cnu.ac.kr/computer/notice/notice.do"
CS_PROJECT_NOTICE_URL = "https://computer.cnu.ac.kr/computer/notice/project.do"
FOOD_URL = "https://mobileadmin.cnu.ac.kr/food/index.jsp"
ACADEMIC_CALENDAR_URL = (
    "https://plus.cnu.ac.kr/_prog/academic_calendar/"
    "?menu_dvs_cd=05020101&site_dvs_cd=kr"
)

CAFETERIAS = ["제1학생회관", "제2학생회관", "제3학생회관", "제4학생회관", "생활과학대학"]
CAFETERIA_MENU_CHOICES = ["제2학생회관", "제3학생회관", "제4학생회관", "생활과학대학"]

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
DISPLAY_TO_INTERNAL = {
    "fetch_recent_notices.board": {
        "학교 학사공지": "univ_academic",
        "학교 새소식": "univ_news",
        "학부 학사공지": "cs_bachelor",
        "학부 소식": "cs_news",
        "학부 사업단 소식": "cs_project",
    },
    "fetch_page_text.source_id": {
        "셔틀버스 안내": "shuttle",
        "수강신청 안내": "course_registration_guide",
    },
}
_HANDLERS: dict[str, Callable[..., list[Evidence]]] = {}
_WORKSPACE_CONTEXT: ContextVar[str | Config | None] = ContextVar("sutra_tool_workspace", default=None)


@dataclass
class NoticeItem:
    title: str
    author: str
    date: str
    url: str
    pinned: bool
    board_label: str = ""
    excerpt: str = ""


@dataclass(frozen=True)
class NoticeBoard:
    internal: str
    display: str
    title: str
    url: str
    parser: str


NOTICE_BOARDS: dict[str, NoticeBoard] = {
    "univ_academic": NoticeBoard(
        internal="univ_academic",
        display="학교 학사공지",
        title="충남대학교 학사공지",
        url=UNIV_ACADEMIC_NOTICE_URL,
        parser="plus",
    ),
    "univ_news": NoticeBoard(
        internal="univ_news",
        display="학교 새소식",
        title="충남대학교 새소식",
        url=UNIV_NEWS_NOTICE_URL,
        parser="plus",
    ),
    "cs_bachelor": NoticeBoard(
        internal="cs_bachelor",
        display="학부 학사공지",
        title="컴퓨터인공지능학부 학사공지",
        url=CS_BACHELOR_NOTICE_URL,
        parser="computer",
    ),
    "cs_news": NoticeBoard(
        internal="cs_news",
        display="학부 소식",
        title="컴퓨터인공지능학부 소식",
        url=CS_NEWS_NOTICE_URL,
        parser="computer",
    ),
    "cs_project": NoticeBoard(
        internal="cs_project",
        display="학부 사업단 소식",
        title="컴퓨터인공지능학부 사업단 소식",
        url=CS_PROJECT_NOTICE_URL,
        parser="computer",
    ),
}
NOTICE_BOARD_ORDER = ["univ_academic", "univ_news", "cs_bachelor", "cs_news", "cs_project"]
NOTICE_BOARD_ALIASES = {
    "학사공지": "univ_academic",
    "컴퓨터융합학부 공지": "cs_bachelor",
    "컴퓨터인공지능학부 공지": "cs_bachelor",
    "cs_dept": "cs_bachelor",
}
INTERNAL_TO_DISPLAY = {
    internal: display
    for mapping in DISPLAY_TO_INTERNAL.values()
    for display, internal in mapping.items()
}
INTERNAL_TO_DISPLAY["cs_dept"] = NOTICE_BOARDS["cs_bachelor"].display


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


def _get(url: str, *, params: dict[str, str] | None = None, timeout: float = FETCH_TIMEOUT) -> str:
    response = requests.get(
        url,
        params=params,
        timeout=timeout,
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
    board = f"[{item.board_label}]" if item.board_label else ""
    line = f"[{item.date}]{board} {item.title} ({item.author}) — {item.url}"
    if item.excerpt:
        line = f"{line}\n본문 발췌: {item.excerpt}"
    return line


def _normalize_short_date(value: str) -> str:
    value = _clean_html(value)
    match = re.fullmatch(r"(\d{4})[.-](\d{2})[.-](\d{2})", value)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"
    match = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{2})", value)
    if match:
        year, month, day = match.groups()
        return f"20{year}-{month}-{day}"
    return value


def _today_kst() -> datetime:
    return datetime.now(ZoneInfo("Asia/Seoul"))


def _source_url_with_params(url: str, params: dict[str, str]) -> str:
    return f"{url}?{urlencode(params)}"


def _display_choices(key: str) -> list[str]:
    return list(DISPLAY_TO_INTERNAL[key].keys())


def _normalize_display_argument(key: str, value: str) -> str:
    mapping = DISPLAY_TO_INTERNAL[key]
    if value in mapping:
        return mapping[value]
    if value in mapping.values():
        return value
    return value


def _normalize_notice_board(value: str | None) -> tuple[str | None, str | None]:
    if value is None or str(value).strip() == "":
        return None, None
    normalized = _normalize_display_argument("fetch_recent_notices.board", str(value).strip())
    alias = normalized if normalized in NOTICE_BOARD_ALIASES else None
    normalized = NOTICE_BOARD_ALIASES.get(normalized, normalized)
    return normalized, alias


def _with_board_label(items: list[NoticeItem], board: NoticeBoard, *, include_label: bool) -> list[NoticeItem]:
    return [
        NoticeItem(
            title=item.title,
            author=item.author,
            date=item.date,
            url=item.url,
            pinned=item.pinned,
            board_label=board.display if include_label else "",
            excerpt=item.excerpt,
        )
        for item in items
    ]


def _normalize_keywords(keywords: list[str] | tuple[str, ...] | str | None) -> list[str]:
    if keywords is None:
        return []
    raw_values = [keywords] if isinstance(keywords, str) else list(keywords)
    normalized: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        keyword = str(value).strip()
        if not keyword or keyword in seen:
            continue
        normalized.append(keyword)
        seen.add(keyword)
        if len(normalized) == 3:
            break
    return normalized


def _normalize_notice_match_text(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _filter_notice_items_by_title_keywords(items: list[NoticeItem], keywords: list[str]) -> list[NoticeItem]:
    normalized_keywords = [_normalize_notice_match_text(keyword) for keyword in keywords]
    normalized_keywords = [keyword for keyword in normalized_keywords if keyword]
    if not normalized_keywords:
        return items
    return [
        item
        for item in items
        if any(keyword in _normalize_notice_match_text(item.title) for keyword in normalized_keywords)
    ]


def _notice_text_with_prefix(regular: list[NoticeItem], pinned: list[NoticeItem], prefix: str | None = None) -> str:
    text = _notice_text(regular, pinned)
    return f"{prefix}\n{text}" if prefix else text


def _fetch_notice_board(
    board: NoticeBoard,
    *,
    include_label: bool,
    params: dict[str, str] | None = None,
    timeout: float = FETCH_TIMEOUT,
) -> list[NoticeItem]:
    html = _get(board.url, params=params, timeout=timeout)
    if board.parser == "computer":
        items = _parse_cs_notices(html, base_url=board.url)
    else:
        items = _parse_univ_notices(html)
    return _with_board_label(items, board, include_label=include_label)


def _dedupe_notice_items(items: list[NoticeItem]) -> list[NoticeItem]:
    deduped: list[NoticeItem] = []
    seen_urls: set[str] = set()
    for item in items:
        if item.url in seen_urls:
            continue
        seen_urls.add(item.url)
        deduped.append(item)
    return deduped


def _remaining_budget(deadline: float) -> float:
    return max(0.0, deadline - time.monotonic())


def _fetch_notice_boards_parallel(
    requests_to_make: list[tuple[NoticeBoard, dict[str, str] | None]],
    *,
    include_label: bool,
    stage_timeout: float,
) -> list[NoticeItem]:
    if not requests_to_make or stage_timeout <= 0:
        return []
    executor = ThreadPoolExecutor(max_workers=len(requests_to_make))
    futures = [
        executor.submit(
            _fetch_notice_board,
            board,
            include_label=include_label,
            params=params,
            timeout=NOTICE_REQUEST_TIMEOUT,
        )
        for board, params in requests_to_make
    ]
    items: list[NoticeItem] = []
    try:
        for future in as_completed(futures, timeout=stage_timeout):
            try:
                items.extend(future.result())
            except Exception:
                logger.warning("Failed to fetch notice board", exc_info=True)
    except FuturesTimeoutError:
        logger.warning("Notice fetch stage exceeded %.1fs budget", stage_timeout)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    return items


def _limit_notice_items_per_board(items: list[NoticeItem], per_board_limit: int) -> list[NoticeItem]:
    regular_counts: dict[str, int] = {}
    pinned_counts: dict[str, int] = {}
    limited: list[NoticeItem] = []
    for item in items:
        key = item.board_label or item.url
        counts = pinned_counts if item.pinned else regular_counts
        if counts.get(key, 0) >= per_board_limit:
            continue
        counts[key] = counts.get(key, 0) + 1
        limited.append(item)
    return limited


def _select_regular_notices(
    items: list[NoticeItem],
    *,
    limit: int,
    selected_boards: list[NoticeBoard],
    ensure_each_board: bool,
) -> list[NoticeItem]:
    regular = sorted((item for item in items if not item.pinned), key=lambda item: item.date, reverse=True)
    if not ensure_each_board:
        return regular[:limit]

    selected: list[NoticeItem] = []
    seen_urls: set[str] = set()
    for board in selected_boards:
        if len(selected) >= limit:
            break
        board_item = next((item for item in regular if item.board_label == board.display), None)
        if board_item and board_item.url not in seen_urls:
            selected.append(board_item)
            seen_urls.add(board_item.url)

    for item in regular:
        if len(selected) >= limit:
            break
        if item.url in seen_urls:
            continue
        selected.append(item)
        seen_urls.add(item.url)
    return sorted(selected, key=lambda item: item.date, reverse=True)


PLUS_NOTICE_BODY_SELECTORS = (
    "board-view-content",
    "board_view_content",
    "view-content",
    "view-con",
    "view_cont",
    "content",
)
COMPUTER_NOTICE_BODY_SELECTORS = (
    "b-content",
    "view-content",
    "view-con",
    "board-view-content",
    "content",
)
NOTICE_CHROME_TOKENS = ("본문 바로가기", "로그인", "이전글", "다음글", "목록", "사이트맵")


def _extract_first_notice_selector(html: str, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        escaped = re.escape(selector)
        pattern = rf"""(?is)<(?:article|section|div)\b[^>]*(?:class|id)=["'][^"']*(?<![\w-]){escaped}(?![\w-])[^"']*["'][^>]*>(.*?)</(?:article|section|div)>"""
        body = _first_match(pattern, html)
        if body:
            return body
    return ""


def _notice_fallback_is_noisy(text: str) -> bool:
    if not text:
        return False
    hits = sum(text.count(token) for token in NOTICE_CHROME_TOKENS)
    chrome_chars = sum(text.count(token) * len(token) for token in NOTICE_CHROME_TOKENS)
    return hits >= 4 and chrome_chars / max(len(text), 1) >= 0.25


def _notice_parser_for_url(url: str) -> str:
    return "plus" if "plus.cnu.ac.kr" in url else "computer"


def _extract_notice_body(html: str, *, parser: str | None = None) -> str:
    if parser == "plus":
        selectors = PLUS_NOTICE_BODY_SELECTORS
    elif parser == "computer":
        selectors = COMPUTER_NOTICE_BODY_SELECTORS
    else:
        selectors = (*PLUS_NOTICE_BODY_SELECTORS, *COMPUTER_NOTICE_BODY_SELECTORS)
    body = _extract_first_notice_selector(html, selectors)
    if body:
        return _clean_html(body)
    fallback = _clean_html(html)
    return "" if _notice_fallback_is_noisy(fallback) else fallback


def _attach_notice_excerpts(items: list[NoticeItem], *, max_items: int = 2, max_chars: int = 800) -> None:
    targets = [item for item in items if item.url][:max_items]
    if not targets:
        return

    def fetch_excerpt(item: NoticeItem) -> tuple[NoticeItem, str]:
        html = _get(item.url, timeout=NOTICE_REQUEST_TIMEOUT)
        excerpt = _extract_notice_body(html, parser=_notice_parser_for_url(item.url))[:max_chars].rstrip()
        return item, excerpt

    executor = ThreadPoolExecutor(max_workers=len(targets))
    futures = [executor.submit(fetch_excerpt, item) for item in targets]
    try:
        for future in as_completed(futures, timeout=NOTICE_BODY_STAGE_TIMEOUT):
            try:
                item, excerpt = future.result()
            except Exception:
                logger.warning("Failed to fetch notice detail", exc_info=True)
                continue
            if excerpt:
                item.excerpt = excerpt
    except FuturesTimeoutError:
        logger.warning("Notice detail stage exceeded %ss budget", NOTICE_BODY_STAGE_TIMEOUT)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


# Tool handlers


@tool(
    name="search_knowledge_base",
    description=(
        "워크스페이스에 저장된 지식베이스 문서를 검색해 관련 근거를 반환한다. "
        "졸업요건, 셔틀 시간표, 학사일정, 식단 스냅샷, 공지 스냅샷처럼 이미 수집된 정보가 필요한 질문에 사용한다. "
        "반환값은 질문과 가까운 문서 조각과 출처 정보다. "
        "domain 필터는 특정 문서 영역으로 검색 범위를 좁히지만, 최신 실시간 정보 보장은 하지 않는다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "검색할 사용자 질문 또는 핵심 키워드 한 문장이다.",
            },
            "domain": {
                "type": ["string", "null"],
                "enum": [*KNOWLEDGE_BASE_DOMAINS, None],
                "description": "academic_calendar, calendar, dining, graduation, shuttle 중 검색을 제한할 선택적 도메인이다.",
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
    description=(
        "충남대학교 학교 학사공지, 학교 새소식, 컴퓨터인공지능학부 학사공지, 학부 소식, 학부 사업단 소식에서 "
        "최신 일반 공지와 고정 공지를 가져온다. "
        "최신 공지, 최근 안내, 학부 공지처럼 게시판의 현재 글 목록을 물을 때 사용한다. "
        "keywords가 있으면 최근 공지 중 해당 주제어가 제목에 포함된 항목을 찾는다. "
        "board를 생략하면 전체 보드 통합 조회를 수행하고, 지정하면 해당 게시판만 조회한다. "
        "사용 예시: 최신 공지 알려줘 → 인자 생략 / 장학금 공지 찾아줘 → keywords=[장학금, 장학] / "
        "사업단 공지 → board=학부 사업단 소식. "
        "반환값은 제목, 작성자, 날짜, URL이 포함된 공지 목록이며 게시판 HTML 구조 변경 시 빈 결과가 날 수 있다."
    ),
    parameters={
        "type": "object",
        "description": (
            "사용 예시: 최신 공지 알려줘 → 인자 생략 / "
            "장학금 공지 찾아줘 → keywords=[장학금, 장학] / "
            "사업단 공지 → board=학부 사업단 소식."
        ),
        "properties": {
            "board": {
                "type": "string",
                "enum": _display_choices("fetch_recent_notices.board"),
                "description": "조회할 게시판이다. 생략하면 학교/컴퓨터인공지능학부 5개 보드를 통합 조회한다.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "description": "반환할 최신 일반 공지의 최대 개수이며 1에서 20 사이로 제한된다. board 생략 시 보드당 기본 5개, 지정 시 기본 10개다.",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 3,
                "description": "찾을 주제어 변형들. 예: [장학금, 장학]. 최근 공지 중 해당 주제어가 제목에 포함된 것을 찾을 때 사용.",
            },
        },
    },
)
def fetch_recent_notices(
    board: str | None = None,
    limit: int | None = None,
    keywords: list[str] | tuple[str, ...] | str | None = None,
) -> list[Evidence]:
    internal_board, alias = _normalize_notice_board(board)
    if internal_board is not None and internal_board not in NOTICE_BOARDS:
        return []

    keyword_values = _normalize_keywords(keywords)
    if keyword_values:
        selected = (
            [NOTICE_BOARDS[internal_board]]
            if internal_board
            else [NOTICE_BOARDS["univ_academic"], NOTICE_BOARDS["cs_bachelor"]]
        )
    else:
        selected = [NOTICE_BOARDS[internal_board]] if internal_board else [NOTICE_BOARDS[key] for key in NOTICE_BOARD_ORDER]
    requested_limit = max(1, min(int(limit), 20)) if limit is not None else None
    if internal_board:
        regular_limit = requested_limit or 10
        pinned_limit = regular_limit
        per_board_limit = None
    else:
        regular_limit = min(requested_limit or NOTICE_INTEGRATED_REGULAR_LIMIT, NOTICE_INTEGRATED_REGULAR_LIMIT)
        pinned_limit = NOTICE_INTEGRATED_PINNED_LIMIT
        per_board_limit = NOTICE_PER_BOARD_FETCH_LIMIT

    items: list[NoticeItem] = []
    result_boards = selected
    if keyword_values:
        include_label = len(selected) > 1
        search_deadline = time.monotonic() + NOTICE_SEARCH_STAGE_TIMEOUT
        latest_items = _fetch_notice_boards_parallel(
            [(board_info, None) for board_info in selected],
            include_label=include_label,
            stage_timeout=_remaining_budget(search_deadline),
        )
        items = _dedupe_notice_items(_filter_notice_items_by_title_keywords(latest_items, keyword_values))
        if not items and not internal_board:
            fanout_boards = [
                NOTICE_BOARDS[key]
                for key in NOTICE_BOARD_ORDER
                if NOTICE_BOARDS[key].internal not in {board_info.internal for board_info in selected}
            ]
            fanout_latest_items = _fetch_notice_boards_parallel(
                [(board_info, None) for board_info in fanout_boards],
                include_label=True,
                stage_timeout=_remaining_budget(search_deadline),
            )
            items = _dedupe_notice_items(_filter_notice_items_by_title_keywords(fanout_latest_items, keyword_values))
            if items:
                result_boards = [*selected, *fanout_boards]
        if not items:
            items = latest_items
            fallback_prefix = f"'{', '.join(keyword_values)}' 관련 최근 공지를 찾지 못해 최신 공지를 표시합니다"
        else:
            fallback_prefix = None
    elif len(selected) == 1:
        try:
            items = _fetch_notice_board(selected[0], include_label=False, timeout=NOTICE_REQUEST_TIMEOUT)
        except Exception:
            logger.warning("Failed to fetch notices", exc_info=True)
            return []
        fallback_prefix = None
    else:
        items = _fetch_notice_boards_parallel(
            [(board_info, None) for board_info in selected],
            include_label=True,
            stage_timeout=NOTICE_SEARCH_STAGE_TIMEOUT,
        )
        fallback_prefix = None

    if per_board_limit is not None:
        items = _limit_notice_items_per_board(items, per_board_limit)

    title = result_boards[0].title if len(result_boards) == 1 else "충남대학교/컴퓨터인공지능학부 통합 공지"
    # Integrated evidence uses the university academic board as representative while item lines keep per-notice URLs.
    source_url = result_boards[0].url if len(result_boards) == 1 else UNIV_ACADEMIC_NOTICE_URL
    regular = _select_regular_notices(
        items,
        limit=regular_limit,
        selected_boards=result_boards,
        ensure_each_board=not internal_board and not keyword_values,
    )
    pinned = sorted((item for item in items if item.pinned), key=lambda item: item.date, reverse=True)[:pinned_limit]
    if not regular and not pinned:
        return []
    if keyword_values and fallback_prefix is None:
        _attach_notice_excerpts([*regular, *pinned])
    metadata = {"tool": "fetch_recent_notices"}
    if len(result_boards) == 1:
        metadata["board"] = result_boards[0].internal
        if alias:
            metadata["board_alias"] = alias
    else:
        metadata["boards"] = [item.internal for item in result_boards]
    if keyword_values:
        metadata["keywords"] = keyword_values
    return [
        Evidence(
            id=f"live_notices_{result_boards[0].internal}" if len(result_boards) == 1 else "live_notices_all",
            title=title,
            text=_notice_text_with_prefix(regular, pinned, fallback_prefix),
            source_url=source_url,
            source_name=title,
            metadata=metadata,
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
        date = _normalize_short_date(cells[3])
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


def _parse_cs_notices(html: str, *, base_url: str = CS_BACHELOR_NOTICE_URL) -> list[NoticeItem]:
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
                url=urljoin(base_url, href),
                pinned=num == "공지",
            )
        )
    return items


@tool(
    name="fetch_cafeteria_menu",
    description=(
        "충남대학교 학생회관의 일별 식단을 아침, 점심, 저녁 단위로 조회한다. "
        "오늘 또는 특정 날짜의 학식, 식당, 메뉴를 물을 때 사용한다. "
        "반환값은 식당, 식사 구분, 대상, 메뉴명, 가격을 포함한 식단 근거다. "
        "제1학생회관은 푸드코트라 일별 메뉴를 지원하지 않으며 코너 정보는 지식베이스에 있고, 다음 주 같은 미래 날짜 데이터는 신뢰하기 어렵다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "date": {
                "type": ["string", "null"],
                "description": "조회할 날짜로 YYYY-MM-DD 형식을 사용하며 생략하면 KST 기준 오늘을 조회한다.",
            },
            "cafeteria": {
                "type": ["string", "null"],
                "enum": [*CAFETERIA_MENU_CHOICES, None],
                "description": "조회할 일별 식단 지원 식당이며 생략하면 지원 식당 전체를 조회한다.",
            },
        },
    },
)
def fetch_cafeteria_menu(date: str | None = None, cafeteria: str | None = None) -> list[Evidence]:
    try:
        today = _today_kst().strftime("%Y-%m-%d")
        target_date = date or today
        text, params = _fetch_cafeteria_menu_text(target_date, cafeteria)
        if not text:
            return []
        if target_date != today:
            try:
                today_text, _ = _fetch_cafeteria_menu_text(today, cafeteria)
            except Exception:
                return [_unverified_cafeteria_evidence(target_date, cafeteria)]
            if _cafeteria_menu_body_text(text) == _cafeteria_menu_body_text(today_text):
                return [_unverified_cafeteria_evidence(target_date, cafeteria)]
    except Exception:
        logger.warning("Failed to fetch cafeteria menu", exc_info=True)
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


def _fetch_cafeteria_menu_text(target_date: str, cafeteria: str | None) -> tuple[str, dict[str, str]]:
    params = _cafeteria_menu_params(target_date)
    html = _get(FOOD_URL, params=params)
    records = _parse_cafeteria_menu(html, target_date, cafeteria)
    return format_dining_day(records, target_date), params


def _cafeteria_menu_params(target_date: str) -> dict[str, str]:
    return {
        "searchYmd": target_date.replace("-", "."),
        "searchLang": "OCL04.10",
        "searchView": "",
        "searchCafeteria": "OCL03.02",
    }


def _cafeteria_menu_body_text(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if line.startswith(("##", "- ")))


def _unverified_cafeteria_evidence(target_date: str, cafeteria: str | None) -> Evidence:
    text = f"{target_date}의 식단은 아직 신뢰 가능한 데이터가 제공되지 않습니다. 식단 사이트가 해당 날짜 정보를 갱신하지 않은 상태입니다."
    return Evidence(
        id="live_cafeteria_menu_unverified",
        title="충남대학교 식단",
        text=text,
        source_url=FOOD_URL,
        source_name="충남대학교 식단",
        metadata={
            "tool": "fetch_cafeteria_menu",
            "date": target_date,
            "cafeteria": cafeteria,
            "unverified_future_data": True,
        },
    )


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
    description=(
        "충남대학교 공식 학사일정을 월 단위로 조회한다. "
        "개강, 종강, 수강신청 기간, 시험 기간, 계절학기 일정처럼 학사일정 날짜를 물을 때 사용한다. "
        "반환값은 조회 월에 해당하는 일정 날짜와 일정명 목록이다. "
        "월을 생략하면 KST 기준 현재월과 다음월을 함께 조회하며, 연도 지정은 지원하지 않는다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "month": {
                "type": ["integer", "null"],
                "minimum": 1,
                "maximum": 12,
                "description": "조회할 월 번호이며 생략하면 현재월과 다음월을 조회한다.",
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
    description=(
        "허용된 CNU 안내 페이지의 본문 텍스트를 추출한다. "
        "셔틀버스 운행 정보 또는 수강신청 안내를 물을 때만 사용한다. "
        "반환값은 페이지 본문 일부와 공식 출처 URL이다. "
        "등록된 정보원 외의 임의 페이지나 졸업요건 문서는 조회하지 않는다."
    ),
    parameters={
        "type": "object",
        "properties": {
            "source_id": {
                "type": "string",
                "enum": _display_choices("fetch_page_text.source_id"),
                "description": "조회할 허용 정보원으로 셔틀버스 안내 또는 수강신청 안내 중 하나다.",
            },
        },
        "required": ["source_id"],
    },
)
def fetch_page_text(source_id: str) -> list[Evidence]:
    internal_source_id = _normalize_display_argument("fetch_page_text.source_id", source_id)
    source = SOURCE_REGISTRY.get(internal_source_id)
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
            id=f"live_page_{internal_source_id}",
            title=source["desc"],
            text=text,
            source_url=source["url"],
            source_name=source["desc"],
            metadata={"tool": "fetch_page_text", "source_id": internal_source_id},
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
