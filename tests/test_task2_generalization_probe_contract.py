from __future__ import annotations

import json
from pathlib import Path


PROBE_PATH = Path("data/gold/task2_generalization_probe.json")
REQUIRED_GROUPS = {
    "latest_notice",
    "changed_since_notice",
    "future_dining",
    "current_dining",
    "shuttle_status",
    "graduation_versioned",
}
EXPECTED_FIELDS = {
    "id",
    "group",
    "question",
    "expected_label",
    "expected_domain",
    "expected_temporal_type",
}


def test_generalization_probe_has_required_intent_groups() -> None:
    rows = json.loads(PROBE_PATH.read_text(encoding="utf-8"))

    groups = {row["group"] for row in rows}

    assert REQUIRED_GROUPS <= groups
    assert len(rows) >= 60
    assert all(EXPECTED_FIELDS <= row.keys() for row in rows)


def test_generalization_probe_has_ten_rows_per_group() -> None:
    rows = json.loads(PROBE_PATH.read_text(encoding="utf-8"))

    counts = {group: 0 for group in REQUIRED_GROUPS}
    for row in rows:
        if row["group"] in counts:
            counts[row["group"]] += 1

    assert all(count >= 10 for count in counts.values())


def test_generalization_probe_ids_are_unique() -> None:
    rows = json.loads(PROBE_PATH.read_text(encoding="utf-8"))
    ids = [row["id"] for row in rows]

    assert len(ids) == len(set(ids))
