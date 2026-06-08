from __future__ import annotations

from pathlib import Path

from nlp_term.collect.base import PARSER_VERSION
from nlp_term.collect.source_inventory import iter_specs
from nlp_term.retrieve.rank import rank_docs
from nlp_term.schemas import RawSource, SourceVerification
from nlp_term.structured.graduation import GraduationRequirementAdapter


RAW_PATH = Path("data/raw/graduation/graduation_english_requirements.html")


def _context():
    spec = next(item for item in iter_specs(stage="stage0") if item.source_id == "graduation_english_requirements")
    raw = RawSource(
        source_id=spec.source_id,
        label=spec.label,
        domain=spec.domain,
        url=spec.url,
        fetched_at="2026-06-08T00:00:00+09:00",
        content_type="text/html",
        raw_path=str(RAW_PATH),
        status_code=200,
        checksum="english-requirements-checksum",
    )
    verification = SourceVerification(
        source_id=spec.source_id,
        official_chain_ok=spec.official_chain_ok,
        parser_name="html_stage_inventory",
        parser_version=PARSER_VERSION,
        evidence=[spec.url],
        warnings=[],
        verified_at="2026-06-08T00:00:00+09:00",
    )
    return spec, raw, verification


def test_graduation_adapter_extracts_requirement_rows() -> None:
    spec, raw, verification = _context()

    rows = GraduationRequirementAdapter().parse(spec=spec, raw=raw, verification=verification)

    assert len(rows) >= 3
    assert all(row.row_type == "graduation_requirement" for row in rows)
    assert any(row.requirement_name == "졸업소요학점" and row.required_value == "130" for row in rows)
    assert all(row.department == "영어영문학과" for row in rows)


def test_graduation_knowledge_doc_metadata_contract() -> None:
    spec, raw, verification = _context()
    adapter = GraduationRequirementAdapter()
    rows = adapter.parse(spec=spec, raw=raw, verification=verification)

    doc = next(doc for doc in adapter.to_knowledge_docs(rows) if doc.metadata["requirement_name"] == "졸업소요학점")

    assert doc.metadata["row_type"] == "graduation_requirement"
    assert doc.metadata["structured"]["department"] == "영어영문학과"
    assert doc.metadata["structured"]["required_value"] == "130"
    assert doc.metadata["structured_fields"] == [
        "department",
        "curriculum_year",
        "admission_year",
        "requirement_category",
        "requirement_name",
        "required_value",
        "unit",
        "applies_to",
        "effective_year",
        "source_section",
        "confidence",
    ]
    assert "원문 문장" in doc.body


def test_graduation_rows_improve_credit_question_retrieval() -> None:
    spec, raw, verification = _context()
    adapter = GraduationRequirementAdapter()
    docs = adapter.to_knowledge_docs(adapter.parse(spec=spec, raw=raw, verification=verification))
    docs_by_id = {doc.doc_id: doc for doc in docs}

    top = docs_by_id[rank_docs("영어영문학과 졸업까지 몇 학점 들어야 하나요?", docs=docs, top_k=1)[0].doc_id]

    assert top.metadata["requirement_name"] == "졸업소요학점"
