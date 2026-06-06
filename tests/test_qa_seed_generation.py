from __future__ import annotations

from nlp_term.prepare.qa_data import build_qa_seed
from nlp_term.schemas import KnowledgeDoc


def _doc(doc_id: str, *, metadata: dict[str, object]) -> KnowledgeDoc:
    return KnowledgeDoc(
        doc_id=doc_id,
        label=0,
        domain="graduation",
        title="graduation source",
        body="졸업 전공 교양 학점 이수 기준을 확인하는 검증용 본문 문장입니다. "
        "교육과정에 따라 졸업요건과 이수학점 기준이 달라질 수 있습니다.",
        source_url="https://plus.cnu.ac.kr",
        source_id=doc_id,
        section="chunk_1",
        metadata=metadata,
    )


def test_qa_seed_uses_graduation_context_and_diverse_docs() -> None:
    rows = build_qa_seed(
        [
            _doc("graduation_biochemistry_requirements_chunk_1", metadata={"source_department": "생화학과"}),
            _doc("graduation_curriculum_pdf_chunk_1", metadata={"source_curriculum_year": "2025"}),
        ]
    )

    users = [row.user for row in rows]
    source_doc_ids = {row.source_doc_id for row in rows}
    assert any(user.startswith("생화학과 졸업요건") for user in users)
    assert any(user.startswith("2025 충남대학교 교육과정 졸업요건") for user in users)
    assert not any("chunk_" in user for user in users)
    assert source_doc_ids == {
        "graduation_biochemistry_requirements_chunk_1",
        "graduation_curriculum_pdf_chunk_1",
    }
