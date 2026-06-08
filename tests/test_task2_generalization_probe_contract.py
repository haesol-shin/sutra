from __future__ import annotations

import json
from pathlib import Path


PROBE_PATH = Path("data/gold/task2_generalization_probe.json")
REQUIRED_GROUPS = {
    "graduation_general_requirements",
    "graduation_department_requirements",
    "graduation_requirement_notices",
    "department_academic_notices",
    "scholarship_and_student_notices",
    "academic_calendar_dates",
    "academic_calendar_changes",
    "dining_current_future",
    "shuttle_status_schedule",
    "source_navigation_and_scope",
}
EXPECTED_FIELDS = {
    "id",
    "group",
    "question",
    "expected_label",
    "expected_domain",
    "expected_temporal_type",
}
ALLOWED_LABELS = {0, 1, 2, 3, 4}
ALLOWED_DOMAINS = {
    "graduation",
    "notices",
    "academic_calendar",
    "dining",
    "shuttle",
}
ALLOWED_TEMPORAL_TYPES = {
    "none",
    "latest_item",
    "changed_since",
    "current_snapshot",
    "future_schedule",
    "ongoing_status",
    "period_summary",
    "date_lookup",
}


def test_generalization_probe_has_required_intent_groups() -> None:
    rows = json.loads(PROBE_PATH.read_text(encoding="utf-8"))

    groups = {row["group"] for row in rows}

    assert groups == REQUIRED_GROUPS
    assert len(rows) == 60
    assert all(EXPECTED_FIELDS <= row.keys() for row in rows)


def test_generalization_probe_has_six_rows_per_group() -> None:
    rows = json.loads(PROBE_PATH.read_text(encoding="utf-8"))

    counts = {group: 0 for group in REQUIRED_GROUPS}
    for row in rows:
        if row["group"] in counts:
            counts[row["group"]] += 1

    assert all(count == 6 for count in counts.values())


def test_generalization_probe_ids_are_unique() -> None:
    rows = json.loads(PROBE_PATH.read_text(encoding="utf-8"))
    ids = [row["id"] for row in rows]

    assert len(ids) == len(set(ids))


def test_generalization_probe_expected_values_are_known() -> None:
    rows = json.loads(PROBE_PATH.read_text(encoding="utf-8"))

    for row in rows:
        assert row["expected_label"] in ALLOWED_LABELS
        assert row["expected_domain"] in ALLOWED_DOMAINS
        assert row["expected_temporal_type"] in ALLOWED_TEMPORAL_TYPES
