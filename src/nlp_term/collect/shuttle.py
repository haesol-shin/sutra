from __future__ import annotations

from nlp_term.collect.base import build_stub_source, fetch_source, verify_stub


URL = "https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html"


def collect(*, fetch: bool = False):
    if fetch:
        return [fetch_source("shuttle_bus", 4, "shuttle", URL)]
    return [build_stub_source("shuttle_bus", 4, "shuttle", URL)]


def verify(raw):
    return verify_stub(raw, "shuttle_stub", "Shuttle timetable parser is not implemented yet.")
