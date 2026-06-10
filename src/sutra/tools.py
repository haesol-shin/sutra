from __future__ import annotations

import logging
import re
from typing import Callable
from urllib.parse import urljoin

import requests

from sutra.models import Evidence

logger = logging.getLogger(__name__)

CNU_NOTICE_BOARD_URL = (
    "https://plus.cnu.ac.kr/_prog/_board/"
    "?code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr"
)
CNU_BOARD_BASE = "https://plus.cnu.ac.kr/_prog/_board/"
FETCH_TIMEOUT = 15
MAX_ITEMS = 10

_HANDLERS: dict[str, Callable] = {}


def tool(name: str, description: str, parameters: dict | None = None):
    """Register a callable function as an LLM tool."""
    params = parameters or {"type": "object", "properties": {}}

    def decorator(fn: Callable):
        _HANDLERS[name] = fn
        fn._tool_name = name
        fn._tool_description = description
        fn._tool_parameters = params
        return fn

    return decorator


def get_tool_definitions() -> list[dict]:
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
    ]


def dispatch(name: str) -> list[Evidence]:
    """Invoke a registered tool by name and return Evidence objects."""
    handler = _HANDLERS.get(name)
    if handler is None:
        logger.warning("Unknown tool requested: %s", name)
        return []
    try:
        return handler()
    except Exception:
        logger.warning("Tool %s execution failed", name, exc_info=True)
        return []


# ── Helpers ────────────────────────────────────────────────────────


def _clean_html(raw: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", raw)
    cleaned = re.sub(r"&[a-z]+;", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _td_regex(class_name: str, capture: str) -> str:
    return (
        r'<td[^>]*class=["\'](?:[^"\']*\s)?'
        + class_name
        + r'(?:\s[^"\']*)?["\'][^>]*>'
        + capture
        + r"</td>"
    )


# ── Tool handlers ──────────────────────────────────────────────────


@tool(
    name="fetch_live_notices",
    description=(
        "Fetch the latest notices from the CNU academic information board. "
        "Use when RAG evidence appears outdated or the user asks for recent/current information."
    ),
)
def _fetch_cnu_notices() -> list[Evidence]:
    results: list[Evidence] = []
    try:
        response = requests.get(
            CNU_NOTICE_BOARD_URL,
            timeout=FETCH_TIMEOUT,
            headers={"User-Agent": "Sutra/1.0"},
        )
        response.raise_for_status()
    except Exception:
        logger.warning("Failed to fetch CNU notice board", exc_info=True)
        return results

    html = response.text
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", html, re.DOTALL)
    if not tbody_match:
        logger.warning("Could not find board table body in CNU notice page")
        return results

    tbody = tbody_match.group(1)
    rows = re.findall(r"<tr>(.*?)</tr>", tbody, re.DOTALL)

    items: list[str] = []
    for row_html in rows:
        if len(items) >= MAX_ITEMS:
            break
        title_match = re.search(
            r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>',
            row_html, re.DOTALL,
        )
        if not title_match:
            continue
        date_match = re.search(_td_regex("date", r"(.*?)"), row_html, re.DOTALL)
        href = title_match.group(1).strip().replace("&amp;", "&")
        title = _clean_html(title_match.group(2))
        date = _clean_html(date_match.group(1)) if date_match else ""
        items.append(f"[{date}] {title}\n    Link: {urljoin(CNU_BOARD_BASE, href)}")

    if items:
        results.append(Evidence(
            id="live_cnu_notices",
            title="CNU Academic Notices (Live)",
            text="[Live Fetched]\n" + "\n".join(items),
            source_url=CNU_NOTICE_BOARD_URL,
            source_name="CNU Academic Information Board",
        ))
    return results
