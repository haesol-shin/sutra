from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from nlp_term.chat.public_probe_experiment import run_public_probe_experiment


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_public_probe_experiment_records_trace_diagnosis(tmp_path: Path) -> None:
    probe_path = tmp_path / "probe.json"
    knowledge_path = tmp_path / "knowledge.json"
    output_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    _write_json(
        probe_path,
        [
            {
                "id": "public_probe_01",
                "question": "졸업까지 몇 학점 들어야 하나요?",
                "expected_label": 0,
                "expected_temporal_type": "none",
                "expected_behavior": "Answer generally.",
            },
            {
                "id": "public_probe_13",
                "question": "다음주 화요일 2학생회관 메뉴가 어떻게 되나요?",
                "expected_label": 3,
                "expected_temporal_type": "future_schedule",
                "expected_behavior": "Use same-date dining evidence.",
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
                "title": "졸업요건",
                "body": "졸업까지 필요한 학점은 학과와 입학연도에 따라 다를 수 있다.",
                "source_url": "https://biochemistry.cnu.ac.kr/biochemistry/info/requirements.do",
                "source_id": "graduation_biochemistry_requirements",
                "metadata": {"source_department": "생화학과"},
            },
            {
                "doc_id": "dining_doc",
                "label": 3,
                "domain": "dining",
                "title": "식단",
                "body": "다음주 화요일인 2026년 6월 16일 2학생회관 점심 메뉴는 공식 식단 페이지에서 확인한다.",
                "source_url": "https://mobileadmin.cnu.ac.kr/food/index.jsp",
                "source_id": "cnu_mobile_food",
                "metadata": {
                    "menu_date": "2026-06-16",
                    "location": "2학생회관",
                    "raw_fetched_at": "2026-06-08T00:00:00+09:00",
                },
            },
        ],
    )

    report = run_public_probe_experiment(
        probe_path=probe_path,
        knowledge_path=knowledge_path,
        output_path=output_path,
        markdown_path=markdown_path,
        reference_time=datetime(2026, 6, 8, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert report["evaluation_scope"] == "task2_public_probe_trace_diagnosis"
    assert report["question_count"] == 2
    assert output_path.exists()
    assert markdown_path.exists()
    rows = report["rows"]
    assert isinstance(rows, list)
    by_id = {row["id"]: row for row in rows}
    assert by_id["public_probe_13"]["actual_temporal_type"] == "future_schedule"
    assert by_id["public_probe_13"]["target_start"] == "2026-06-16"
    assert "bottleneck" in by_id["public_probe_13"]
