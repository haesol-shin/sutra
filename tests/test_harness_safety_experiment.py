from __future__ import annotations

import json
from pathlib import Path

from nlp_term.chat.harness_experiment import run_harness_safety_experiment


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_harness_safety_experiment_reports_coverage_and_safety_metrics(tmp_path: Path) -> None:
    questions_path = tmp_path / "harness_safety_questions.json"
    knowledge_path = tmp_path / "knowledge_seed.json"
    output_path = tmp_path / "harness_safety_experiment.json"
    _write_json(
        questions_path,
        [
            {
                "case_id": "grad_static",
                "question": "생화학과 졸업요건은 어디서 봐?",
                "expected_label": 0,
                "expected_domain": "graduation",
                "expected_answer_kind": "source_navigation",
                "scenario": "source_navigation",
            },
            {
                "case_id": "dining_current_guard",
                "question": "오늘 점심 메뉴 뭐야?",
                "expected_label": 3,
                "expected_domain": "dining",
                "expected_answer_kind": "current_fact",
                "scenario": "current_fact_guard",
                "must_not_contain": ["김치찌개"],
            },
            {
                "case_id": "wrong_domain_guard",
                "question": "식단은 셔틀 시간표 페이지에서 보면 돼?",
                "expected_label": 3,
                "expected_domain": "dining",
                "expected_answer_kind": "unsupported",
                "scenario": "wrong_domain_guard",
            },
        ],
    )
    _write_json(
        knowledge_path,
        [
            {
                "doc_id": "grad_doc",
                "label": 0,
                "domain": "graduation",
                "title": "생화학과 졸업요건",
                "body": "생화학과 졸업요건은 생화학과 공식 졸업요건 페이지에서 확인한다.",
                "source_url": "https://biochemistry.cnu.ac.kr/biochemistry/info/requirements.do",
                "source_id": "graduation_biochemistry_requirements",
                "metadata": {"source_department": "생화학과"},
            },
            {
                "doc_id": "shuttle_doc",
                "label": 4,
                "domain": "shuttle",
                "title": "셔틀 안내",
                "body": "셔틀버스 시간표는 충남대학교 공식 셔틀 안내 페이지에서 확인한다.",
                "source_url": "https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html",
                "source_id": "shuttle_bus",
                "metadata": {},
            },
            {
                "doc_id": "dining_doc",
                "label": 3,
                "domain": "dining",
                "title": "식단",
                "body": "식단은 모바일 식단 페이지에서 확인한다.",
                "source_url": "https://mobileadmin.cnu.ac.kr/food/index.jsp",
                "source_id": "cnu_mobile_food",
                "metadata": {"raw_fetched_at": "2026-06-07T00:00:00+00:00"},
            },
        ],
    )

    report = run_harness_safety_experiment(
        questions_path=questions_path,
        knowledge_path=knowledge_path,
        output_path=output_path,
    )

    assert report["evaluation_scope"] == "task2_task3_phase_a_harness_safety"
    assert report["question_count"] == 3
    assert report["domain_coverage"] == ["dining", "graduation"]
    assert report["wrong_domain_pass_count"] == 0
    assert report["current_fact_hallucination_count"] == 0
    assert report["answered_count"] >= 1
    assert report["fail_close_count"] >= 1
    assert "data" in report["bottleneck_counts"]
    assert output_path.exists()


def test_repository_harness_safety_fixture_covers_required_shape() -> None:
    payload = json.loads(Path("data/harness_safety_questions.json").read_text(encoding="utf-8"))

    assert len(payload) >= 30
    assert {row["expected_label"] for row in payload} == {0, 1, 2, 3, 4}
    assert {row["expected_domain"] for row in payload} == {
        "academic_calendar",
        "dining",
        "graduation",
        "notices",
        "shuttle",
    }
    assert {
        "source_navigation",
        "static_fact",
        "procedural",
        "current_fact",
        "unsupported",
        "wrong_domain_guard",
    }.issubset({row["scenario"] for row in payload})
