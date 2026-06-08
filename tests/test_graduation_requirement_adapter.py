from __future__ import annotations

from pathlib import Path

import pytest

from nlp_term.collect.base import PARSER_VERSION
from nlp_term.collect.source_inventory import iter_specs
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


def test_graduation_adapter_does_not_promote_prose_to_structured_rows() -> None:
    spec, raw, verification = _context()

    with pytest.raises(ValueError, match="graduation requirement rows not found"):
        GraduationRequirementAdapter().parse(spec=spec, raw=raw, verification=verification)


def test_graduation_adapter_keeps_empty_structured_doc_list_empty() -> None:
    adapter = GraduationRequirementAdapter()

    assert adapter.to_knowledge_docs([]) == []


def test_graduation_prose_must_remain_outside_structured_retrieval() -> None:
    spec, raw, verification = _context()

    with pytest.raises(ValueError, match="graduation requirement rows not found"):
        GraduationRequirementAdapter().parse(spec=spec, raw=raw, verification=verification)
