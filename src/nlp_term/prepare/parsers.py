from __future__ import annotations

from bs4 import BeautifulSoup
from bs4 import Tag

from nlp_term.prepare.normalize import clip_text, normalize_whitespace
from nlp_term.schemas import KnowledgeDoc, RawSource


def html_to_text(content: bytes | str, *, source_id: str | None = None) -> str:
    text = content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else content
    soup = BeautifulSoup(text, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    main_text = _source_specific_html_text(soup, source_id=source_id)
    if main_text:
        return main_text
    return normalize_whitespace(soup.get_text(" "))


def _source_specific_html_text(soup: BeautifulSoup, *, source_id: str | None) -> str | None:
    if source_id == "academic_notice_board":
        return _notice_board_text(soup)
    if source_id == "academic_calendar":
        return _selected_text(soup.select(".calen_box"))
    if source_id == "shuttle_bus":
        return _selected_text(soup.select("#contents .content #txt, #txt"))
    if source_id == "cnu_mobile_food":
        return _selected_text(soup.select(".menu-wr, .menu-tbl"))
    return _selected_text(soup.select("#contents .content #txt, #txt, .contents, main, article"))


def _notice_board_text(soup: BeautifulSoup) -> str | None:
    rows = soup.select(".board_list tbody tr")
    row_texts = []
    for row in rows:
        cells = [normalize_whitespace(cell.get_text(" ")) for cell in row.select("th, td")]
        cells = [cell for cell in cells if cell]
        if cells:
            row_texts.append(" ".join(cells))
    if row_texts:
        prefix = "학사정보게시판 목록 번호 제목 작성자 작성일 조회수"
        return normalize_whitespace(f"{prefix} {' '.join(row_texts)}")
    return _selected_text(soup.select("#contents .content #txt, #txt"))


def _selected_text(nodes: list[Tag]) -> str | None:
    texts: list[str] = []
    for node in nodes:
        _remove_local_chrome(node)
        text = normalize_whitespace(node.get_text(" "))
        if len(text) >= 80:
            texts.append(text)
    return normalize_whitespace(" ".join(texts)) if texts else None


def _remove_local_chrome(node: Tag) -> None:
    selectors = (
        ".location",
        "#path",
        ".path",
        ".sns",
        "#sns",
        ".satisfaction",
        "#satisfaction",
        "#department",
        ".board_search",
        ".paging",
        ".pagination",
        ".breadcrumb",
        ".ButtonCenterBox",
        ".sebox",
    )
    for selector in selectors:
        for child in node.select(selector):
            child.decompose()


def source_doc_from_text(
    raw: RawSource,
    *,
    title: str,
    body: str,
    section: str | None = None,
    parser_name: str,
    max_body_chars: int | None = 4000,
) -> KnowledgeDoc:
    return KnowledgeDoc(
        doc_id=f"{raw.source_id}_{section or 'main'}",
        label=raw.label,
        domain=raw.domain,
        title=clip_text(title, max_chars=160) or raw.source_id,
        body=clip_text(body, max_chars=max_body_chars),
        source_url=raw.url,
        source_id=raw.source_id,
        section=section,
        metadata={
            "parser": parser_name,
            "generation_method": "source_parse",
            "content_type": raw.content_type,
        },
    )
