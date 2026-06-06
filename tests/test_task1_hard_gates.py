from __future__ import annotations

import json
from pathlib import Path

import pytest

from nlp_term.validators import validate_task1_hard_gates


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _minimal_docs() -> list[dict[str, object]]:
    return [
        {
            "doc_id": f"doc_{label}_{source}",
            "label": label,
            "domain": "graduation",
            "title": f"label {label} source {source}",
            "body": "검증용 본문입니다.",
            "source_url": "https://plus.cnu.ac.kr",
            "source_id": f"source_{label}_{source}",
        }
        for label in range(5)
        for source in range(2)
    ]


def _minimal_rows(question_for: dict[tuple[int, int], str] | None = None) -> list[dict[str, object]]:
    question_for = question_for or {}
    rows = []
    for label in range(5):
        for source in range(2):
            rows.append(
                {
                    "question": question_for.get((label, source), f"label {label} source {source} 질문"),
                    "label": label,
                    "source_doc_id": f"doc_{label}_{source}",
                    "generation_method": "template",
                    "validated": True,
                }
            )
    return rows


def _write_dataset(data_dir: Path, rows: list[dict[str, object]]) -> None:
    _write_json(data_dir / "knowledge_seed.json", _minimal_docs())
    _write_json(data_dir / "cls_train_seed.json", rows)


def test_task1_hard_gates_pass_on_clean_dataset(tmp_path: Path) -> None:
    _write_dataset(tmp_path, _minimal_rows())
    report_path = tmp_path / "task1_hard_gates.json"

    validate_task1_hard_gates(
        tmp_path,
        report_output=report_path,
        require_cls_source_docs=True,
        max_normalized_duplicate_count=0,
        max_conflicting_duplicate_count=0,
        min_source_docs_per_label=2,
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["normalized_duplicate_count"] == 0
    assert report["source_docs_per_label"] == {str(label): 2 for label in range(5)}


def test_task1_hard_gates_reject_conflicting_duplicate(tmp_path: Path) -> None:
    rows = _minimal_rows({(0, 0): "같은 질문", (1, 0): "같은 질문"})
    _write_dataset(tmp_path, rows)

    with pytest.raises(ValueError, match="conflicting duplicate"):
        validate_task1_hard_gates(
            tmp_path,
            max_normalized_duplicate_count=0,
            max_conflicting_duplicate_count=0,
        )


def test_task1_hard_gates_reject_source_label_mismatch(tmp_path: Path) -> None:
    rows = _minimal_rows()
    rows[0]["source_doc_id"] = "doc_1_0"
    _write_dataset(tmp_path, rows)

    with pytest.raises(ValueError, match="mismatched source labels"):
        validate_task1_hard_gates(tmp_path, require_cls_source_docs=True)


def test_task1_hard_gates_reject_source_concentration(tmp_path: Path) -> None:
    rows = _minimal_rows()
    rows = [row for row in rows if not (row["label"] == 4 and row["source_doc_id"] == "doc_4_1")]
    _write_dataset(tmp_path, rows)

    with pytest.raises(ValueError, match="label 4 source docs below threshold"):
        validate_task1_hard_gates(tmp_path, min_source_docs_per_label=2)
