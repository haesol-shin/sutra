from __future__ import annotations

from bs4 import BeautifulSoup

from nlp_term.prepare.normalize import clip_text, normalize_whitespace
from nlp_term.schemas import KnowledgeDoc, RawSource


def html_to_text(content: bytes | str) -> str:
    text = content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else content
    soup = BeautifulSoup(text, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return normalize_whitespace(soup.get_text(" "))


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
