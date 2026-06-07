from __future__ import annotations

import json
from pathlib import Path


PROBE_PATH = Path("data/gold/task2_public_probe_eval.json")


def test_task2_public_probe_fixture_has_14_discussion_questions() -> None:
    rows = json.loads(PROBE_PATH.read_text(encoding="utf-8"))

    assert len(rows) == 14
    assert {row["id"] for row in rows} == {f"public_probe_{index:02d}" for index in range(1, 15)}
    assert all("question" in row for row in rows)
    assert all("expected_label" in row for row in rows)
    assert all("expected_temporal_type" in row for row in rows)
    assert all("expected_behavior" in row for row in rows)


def test_task2_public_probe_temporal_expectations_cover_current_failures() -> None:
    rows = json.loads(PROBE_PATH.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in rows}

    assert by_id["public_probe_07"]["expected_temporal_type"] == "changed_since"
    assert by_id["public_probe_08"]["expected_temporal_type"] == "period_summary"
    assert by_id["public_probe_11"]["expected_temporal_type"] == "date_lookup"
    assert by_id["public_probe_13"]["expected_temporal_type"] == "future_schedule"
