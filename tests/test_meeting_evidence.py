from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="legacy doc gate superseded by Sutra direction (2026-06-11)")

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_goal_23_meeting_transitions_are_recorded() -> None:
    dashboard = (ROOT / "docs" / "meeting_room_dashboard.md").read_text(encoding="utf-8")

    for step in range(1, 7):
        meeting_id = f"goal-2.3-step-{step:02d}-to-{step + 1:02d}-2026-06-07"
        assert meeting_id in dashboard
        assert (ROOT / "docs" / "meetings" / f"goal-2.3-step-{step:02d}-evidence.md").exists()
        assert (ROOT / "docs" / "meetings" / f"goal-2.3-step-{step:02d}-meeting.md").exists()
        assert (ROOT / "docs" / "meetings" / f"goal-2.3-step-{step:02d}-handoff.md").exists()
