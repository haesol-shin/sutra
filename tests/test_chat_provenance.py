from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from nlp_term.chat.batch import run_chat_file
from nlp_term.validators import validate_chat_provenance


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _knowledge_rows() -> list[dict[str, object]]:
    return [
        {
            "doc_id": "graduation_doc_1",
            "label": 0,
            "domain": "graduation",
            "title": "졸업요건 안내",
            "body": "졸업 전공 교양 학점 이수 기준을 확인하는 공식 안내입니다.",
            "source_url": "https://plus.cnu.ac.kr",
            "source_id": "graduation",
            "metadata": {
                "source_id": "graduation",
                "source_stage": "stage0",
                "source_parser_type": "html",
            },
        },
        {
            "doc_id": "notice_doc_1",
            "label": 1,
            "domain": "notices",
            "title": "학사 공지",
            "body": "수강신청 휴학 복학 신청 공지 안내입니다.",
            "source_url": "https://plus.cnu.ac.kr",
            "source_id": "notice",
            "metadata": {
                "source_id": "notice",
                "source_stage": "stage0",
                "source_parser_type": "html",
            },
        },
    ]


def test_chat_batch_writes_deterministic_provenance(tmp_path: Path) -> None:
    input_path = tmp_path / "test_chat.json"
    output_path = tmp_path / "chat_output.json"
    provenance_path = tmp_path / "chat_output.provenance.json"
    knowledge_path = tmp_path / "knowledge_seed.json"
    _write_json(input_path, [{"user": "졸업 전공 학점 기준 알려줘"}])
    _write_json(knowledge_path, _knowledge_rows())

    run_chat_file(
        input_path,
        output_path,
        knowledge_path=knowledge_path,
        backend="deterministic",
        provenance_output_path=provenance_path,
    )

    validate_chat_provenance(
        provenance_path,
        input_path=input_path,
        output_path=output_path,
        knowledge_path=knowledge_path,
        require_backend="deterministic",
        max_fallback_used=0,
        require_retrieved_docs=True,
    )
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert provenance["fallback_used"] is False
    assert provenance["rows"][0]["retrieved"]


def test_chat_provenance_rejects_silent_fallback(tmp_path: Path) -> None:
    input_path = tmp_path / "test_chat.json"
    output_path = tmp_path / "chat_output.json"
    knowledge_path = tmp_path / "knowledge_seed.json"
    provenance_path = tmp_path / "chat_output.provenance.json"
    _write_json(input_path, [{"user": "학사 공지 알려줘"}])
    _write_json(output_path, [{"user": "학사 공지 알려줘", "model": "답변"}])
    _write_json(knowledge_path, _knowledge_rows())
    _write_json(
        provenance_path,
            {
                "evaluation_scope": "task2_chat_batch_provenance",
                "input_checksum": sha256(input_path.read_bytes()).hexdigest(),
                "output_checksum": sha256(output_path.read_bytes()).hexdigest(),
                "knowledge_checksum": sha256(knowledge_path.read_bytes()).hexdigest(),
            "backend_used": "deterministic",
            "fallback_used": True,
            "fallback_reason": "auto backend selected deterministic because llama backend is unavailable",
            "row_count": 1,
            "rows": [{"user": "학사 공지 알려줘", "retrieved": [{"doc_id": "notice_doc_1", "source_url": "https://plus.cnu.ac.kr"}]}],
        },
    )

    with pytest.raises(ValueError, match="fallback_used exceeds threshold"):
        validate_chat_provenance(
            provenance_path,
            input_path=input_path,
            output_path=output_path,
            knowledge_path=knowledge_path,
            max_fallback_used=0,
            require_retrieved_docs=True,
        )


def test_chat_provenance_rejects_output_checksum_mismatch(tmp_path: Path) -> None:
    input_path = tmp_path / "test_chat.json"
    output_path = tmp_path / "chat_output.json"
    provenance_path = tmp_path / "chat_output.provenance.json"
    knowledge_path = tmp_path / "knowledge_seed.json"
    _write_json(input_path, [{"user": "졸업 전공 학점 기준 알려줘"}])
    _write_json(knowledge_path, _knowledge_rows())
    run_chat_file(
        input_path,
        output_path,
        knowledge_path=knowledge_path,
        backend="deterministic",
        provenance_output_path=provenance_path,
    )
    _write_json(output_path, [{"user": "졸업 전공 학점 기준 알려줘", "model": "변조된 답변"}])

    with pytest.raises(ValueError, match="output_checksum does not match output file"):
        validate_chat_provenance(
            provenance_path,
            input_path=input_path,
            output_path=output_path,
            knowledge_path=knowledge_path,
        )
