from __future__ import annotations

from nlp_term.collect.base import build_stub_source, verify_stub


URL = "https://plus.cnu.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&site_dvs_cd=kr"


def collect():
    return [build_stub_source("academic_calendar", 2, "academic_calendar", URL)]


def verify(raw):
    return verify_stub(raw, "academic_calendar_stub", "Calendar parser is not implemented yet.")
