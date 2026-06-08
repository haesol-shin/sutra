from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import nlp_term.chat.qwen_public_probe_baseline as qwen_baseline
from nlp_term.chat.qwen_public_probe_baseline import run_qwen_public_probe_baseline


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_qwen_public_probe_baseline_records_writer_and_trace_fields(tmp_path: Path) -> None:
    probe_path = tmp_path / "probe.json"
    knowledge_path = tmp_path / "knowledge.json"
    output_path = tmp_path / "qwen.json"
    markdown_path = tmp_path / "qwen.md"
    _write_json(
        probe_path,
        [
            {
                "id": "public_probe_01",
                "question": "졸업까지 몇 학점 들어야 하나요?",
                "expected_label": 0,
                "expected_temporal_type": "none",
                "expected_behavior": "Answer generally.",
            }
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
                "metadata": {"source_department": "생화학과", "chunk_confidence": "medium"},
            }
        ],
    )

    report = run_qwen_public_probe_baseline(
        probe_path=probe_path,
        knowledge_path=knowledge_path,
        output_path=output_path,
        markdown_path=markdown_path,
        reference_time=datetime(2026, 6, 8, tzinfo=ZoneInfo("Asia/Seoul")),
        writer=lambda prompt: "졸업 학점은 학과와 입학연도에 따라 달라집니다.",
    )

    assert report["evaluation_scope"] == "task2_public_probe_qwen_baseline"
    assert report["writer_backend"] == "llama_server"
    assert report["max_tokens"] == 1024
    assert report["writer_called_count"] == 1
    assert output_path.exists()
    assert markdown_path.exists()
    row = report["rows"][0]
    assert row["qwen_writer_called"] is True
    assert row["trace_generation_backend"] == "injected"
    assert "prefilter_retrieved_candidates" in row
    assert row["postfilter_retrieved_doc_ids"] == row["retrieved_doc_ids"]


def test_qwen_public_probe_baseline_defaults_to_1024_max_tokens(monkeypatch, tmp_path: Path) -> None:
    probe_path = tmp_path / "probe.json"
    knowledge_path = tmp_path / "knowledge.json"
    output_path = tmp_path / "qwen.json"
    _write_json(
        probe_path,
        [
            {
                "id": "public_probe_01",
                "question": "졸업까지 몇 학점 들어야 하나요?",
                "expected_label": 0,
                "expected_temporal_type": "none",
                "expected_behavior": "Answer generally.",
            }
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
            }
        ],
    )
    seen: dict[str, int] = {}

    def fake_generate_with_llama_server(**kwargs):
        seen["max_tokens"] = kwargs["max_tokens"]
        return "졸업 학점은 학과와 입학연도에 따라 달라집니다."

    monkeypatch.setattr(qwen_baseline, "generate_with_llama_server", fake_generate_with_llama_server)

    run_qwen_public_probe_baseline(
        probe_path=probe_path,
        knowledge_path=knowledge_path,
        output_path=output_path,
        reference_time=datetime(2026, 6, 8, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert seen["max_tokens"] == 1024
