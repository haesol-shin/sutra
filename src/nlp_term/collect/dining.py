from __future__ import annotations

from nlp_term.collect.base import build_stub_source, verify_stub


MOBILE_MENU_URL = "https://mobileadmin.cnu.ac.kr/food/index.jsp"
COOP_URL = "https://www.cnucoop.co.kr/"


def collect():
    return [
        build_stub_source("cnu_mobile_food", 3, "dining", MOBILE_MENU_URL),
        build_stub_source("cnucoop_discovery", 3, "dining", COOP_URL),
    ]


def verify(raw):
    return verify_stub(raw, "dining_stub", "Dining official chain and date parameters are not verified yet.")
