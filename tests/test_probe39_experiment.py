from __future__ import annotations

from collections import Counter
from pathlib import Path

from nlp_term.chat.probe39_experiment import build_probe39_cases


PUBLIC_PROBE_PATH = Path("data/gold/task2_public_probe_eval.json")
GENERALIZATION_PROBE_PATH = Path("data/gold/task2_generalization_probe.json")


def test_probe39_cases_include_public_14_and_five_per_domain() -> None:
    cases = build_probe39_cases(
        public_probe_path=PUBLIC_PROBE_PATH,
        generalization_probe_path=GENERALIZATION_PROBE_PATH,
    )

    source_counts = Counter(str(case["source_set"]) for case in cases)
    domain_counts = Counter(str(case["expected_domain"]) for case in cases)

    assert len(cases) == 39
    assert source_counts == {"public_probe": 14, "generalization_sample": 25}
    assert domain_counts == {
        "graduation": 7,
        "notices": 8,
        "academic_calendar": 9,
        "dining": 8,
        "shuttle": 7,
    }


def test_probe39_generalization_sample_selection_is_stable() -> None:
    cases = build_probe39_cases(
        public_probe_path=PUBLIC_PROBE_PATH,
        generalization_probe_path=GENERALIZATION_PROBE_PATH,
    )

    sampled_ids = [str(case["id"]) for case in cases if case["source_set"] == "generalization_sample"]

    assert sampled_ids == [
        "gp001",
        "gp002",
        "gp003",
        "gp004",
        "gp005",
        "gp013",
        "gp014",
        "gp015",
        "gp016",
        "gp017",
        "gp031",
        "gp032",
        "gp033",
        "gp034",
        "gp035",
        "gp043",
        "gp044",
        "gp045",
        "gp046",
        "gp047",
        "gp049",
        "gp050",
        "gp051",
        "gp052",
        "gp053",
    ]
