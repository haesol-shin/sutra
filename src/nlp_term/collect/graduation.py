from __future__ import annotations

from nlp_term.collect.base import build_stub_source, fetch_source, verify_stub


URL = "https://plus.cnu.ac.kr/html/kr/25file/2025_book.pdf"


def collect(*, fetch: bool = False):
    if fetch:
        return [fetch_source("graduation_curriculum_pdf", 0, "graduation", URL, raw_suffix="pdf")]
    return [
        build_stub_source(
            "graduation_curriculum_pdf",
            0,
            "graduation",
            URL,
            content_type="application/pdf",
            raw_suffix="pdf",
        )
    ]


def verify(raw):
    return verify_stub(raw, "graduation_pdf_stub", "PDF extraction is not implemented yet.")
