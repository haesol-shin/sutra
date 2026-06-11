from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from sutra.tools import (
    fetch_academic_calendar,
    fetch_cafeteria_menu,
    fetch_page_text,
    fetch_recent_notices,
)


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("SUTRA_RUN_LIVE_TOOLS") != "1",
        reason="set SUTRA_RUN_LIVE_TOOLS=1 to run live CNU site checks",
    ),
]


def test_live_recent_notices_have_recent_regular_dates() -> None:
    evidence = fetch_recent_notices(board="univ_academic", limit=10)

    assert evidence
    dates = [
        datetime.strptime(match, "%Y-%m-%d").date()
        for match in re.findall(r"\[(\d{4}-\d{2}-\d{2})\]", evidence[0].text)
    ]
    assert len(dates) >= 5
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    assert any(today - date <= timedelta(days=60) for date in dates)


def test_live_cafeteria_menu_contains_menu_or_closed_marker() -> None:
    evidence = fetch_cafeteria_menu()

    assert evidence
    assert "정식" in evidence[0].text or "운영안함" in evidence[0].text


def test_live_academic_calendar_contains_current_month_entry() -> None:
    month = datetime.now(ZoneInfo("Asia/Seoul")).month
    evidence = fetch_academic_calendar(month=month)

    assert evidence
    assert f"[{month:02d}." in evidence[0].text


def test_live_registry_page_text_fetches_shuttle_source() -> None:
    evidence = fetch_page_text(source_id="shuttle")

    assert evidence
    assert "셔틀버스" in evidence[0].text
