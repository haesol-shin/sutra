from __future__ import annotations

from nlp_term.collect.base import build_stub_source, verify_stub


URL = "https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr"


def collect():
    return [build_stub_source("academic_notice_board", 1, "notices", URL)]


def verify(raw):
    return verify_stub(raw, "notices_board_stub", "Notice board pagination is not implemented yet.")
