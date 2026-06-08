from __future__ import annotations

from collections import Counter
from pathlib import Path

from nlp_term.chat.probe39_experiment import build_probe39_cases
from nlp_term.chat.probe39_experiment import evidence_duplicate_diagnostics
from nlp_term.schemas import KnowledgeDoc


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


def test_evidence_duplicate_diagnostics_counts_fact_and_scope_duplicates() -> None:
    docs = [
        KnowledgeDoc(
            doc_id="calendar-atomic",
            label=2,
            domain="academic_calendar",
            title="하기방학",
            body="2026-06-22 하기방학",
            source_url="https://plus.cnu.ac.kr/calendar",
            source_id="academic_calendar",
            metadata={
                "row_type": "academic_calendar_event",
                "start_date": "2026-06-22",
                "end_date": "2026-06-22",
                "event_name": "하기방학",
            },
        ),
        KnowledgeDoc(
            doc_id="calendar-atomic-copy",
            label=2,
            domain="academic_calendar",
            title="하기방학 copy",
            body="2026학년도 학사일정: 하기방학은 2026-06-22입니다.",
            source_url="https://plus.cnu.ac.kr/calendar",
            source_id="academic_calendar",
            metadata={
                "row_type": "academic_calendar_event",
                "start_date": "2026-06-22",
                "end_date": "2026-06-22",
                "event_name": "하기방학",
            },
        ),
        KnowledgeDoc(
            doc_id="calendar-month",
            label=2,
            domain="academic_calendar",
            title="6월 학사일정",
            body="2026년 6월 학사일정 요약",
            source_url="https://plus.cnu.ac.kr/calendar",
            source_id="academic_calendar",
            metadata={
                "row_type": "academic_calendar_monthly",
                "academic_year": 2026,
                "month": 6,
            },
        ),
        KnowledgeDoc(
            doc_id="calendar-month-copy",
            label=2,
            domain="academic_calendar",
            title="6월 학사일정 copy",
            body="2026학년도 6월 학사일정",
            source_url="https://plus.cnu.ac.kr/calendar",
            source_id="academic_calendar",
            metadata={
                "row_type": "academic_calendar_monthly",
                "academic_year": 2026,
                "month": 6,
            },
        ),
    ]

    diagnostics = evidence_duplicate_diagnostics(
        selected_doc_ids=[doc.doc_id for doc in docs],
        docs_by_id={doc.doc_id: doc for doc in docs},
    )

    assert diagnostics["selected_doc_count"] == 4
    assert diagnostics["fact_duplicate_count"] == 1
    assert diagnostics["scope_duplicate_count"] == 1
    assert diagnostics["duplicate_doc_count"] == 2
    assert diagnostics["duplicate_doc_rate"] == 0.5
