from __future__ import annotations

import pytest

from nlp_term.collect.base import PARSER_VERSION
from nlp_term.collect.source_inventory import iter_specs
from nlp_term.schemas import RawSource, SourceVerification
from nlp_term.structured.rows import DiningRow, dining_row_id


def _dining_context(fetched_at: str = "2026-06-08T02:02:37+00:00"):
    spec = next(item for item in iter_specs(stage="stage0") if item.source_id == "cnu_mobile_food")
    raw = RawSource(
        source_id=spec.source_id,
        label=spec.label,
        domain=spec.domain,
        url=spec.url,
        fetched_at=fetched_at,
        content_type="text/html; charset=UTF-8",
        raw_path="data/raw/dining/cnu_mobile_food.html",
        status_code=200,
        checksum="raw-checksum",
    )
    verification = SourceVerification(
        source_id=spec.source_id,
        official_chain_ok=spec.official_chain_ok,
        parser_name="dining_stage_inventory",
        parser_version=PARSER_VERSION,
        evidence=[spec.url],
        warnings=["source is not official-chain verified", "freshness policy: short_ttl"],
        verified_at="2026-06-08T02:02:38+00:00",
    )
    return spec, raw, verification


def _sample_row(fetched_at: str = "2026-06-08T02:02:37+00:00") -> DiningRow:
    spec, raw, verification = _dining_context(fetched_at=fetched_at)
    return DiningRow.from_source_context(
        spec=spec,
        raw=raw,
        verification=verification,
        row_id=dining_row_id(
            source_id=spec.source_id,
            meal_date="2026-06-08",
            cafeteria="제1학생회관",
            meal_type="중식",
            user_type="학생",
            ordinal_or_menu_key="1",
        ),
        evidence_text="2026-06-08 제1학생회관 중식 학생 정식(4500)",
        meal_date="2026-06-08",
        cafeteria="제1학생회관",
        meal_type="중식",
        user_type="학생",
        menu_name="정식",
        price=4500,
        menu_items=["김치볶음밥", "단무지"],
        is_closed=False,
        closed_reason=None,
    )


def test_dining_row_derives_provenance_from_source_context() -> None:
    spec, raw, verification = _dining_context()

    row = _sample_row()

    assert row.source_id == spec.source_id
    assert row.source_url == raw.url
    assert row.label == spec.label
    assert row.domain == spec.domain
    assert row.raw_path == raw.raw_path
    assert row.raw_checksum == raw.checksum
    assert row.raw_fetched_at == raw.fetched_at
    assert row.parser_name == verification.parser_name
    assert row.parser_version == verification.parser_version
    assert row.verification_official_chain_ok is False
    assert row.freshness_policy == spec.freshness_policy


def test_dining_row_rejects_mismatched_source_context() -> None:
    spec, raw, verification = _dining_context()
    wrong_raw = raw.model_copy(update={"source_id": "other_source"})

    with pytest.raises(ValueError, match="source_id"):
        DiningRow.from_source_context(
            spec=spec,
            raw=wrong_raw,
            verification=verification,
            row_id="bad",
            evidence_text="bad",
            meal_date="2026-06-08",
            cafeteria="제1학생회관",
            meal_type="중식",
            user_type="학생",
            menu_name=None,
            price=None,
            menu_items=[],
            is_closed=True,
            closed_reason="운영안함",
        )


def test_dining_row_id_is_stable_when_fetched_at_changes() -> None:
    first = _sample_row(fetched_at="2026-06-08T02:02:37+00:00")
    second = _sample_row(fetched_at="2026-06-09T02:02:37+00:00")

    assert first.row_id == second.row_id
    assert first.raw_fetched_at != second.raw_fetched_at


def test_dining_knowledge_doc_metadata_contract() -> None:
    row = _sample_row()

    doc = row.to_knowledge_doc()

    assert doc.source_id == row.source_id
    assert doc.source_url == row.source_url
    assert doc.metadata["structured"]["meal_date"] == "2026-06-08"
    assert doc.metadata["menu_date"] == "2026-06-08"
    assert doc.metadata["location"] == "제1학생회관"
    assert doc.metadata["cafeteria"] == "제1학생회관"
    assert doc.metadata["meal_type"] == "중식"
    assert doc.metadata["user_type"] == "학생"
    assert doc.metadata["structured_fields"] == [
        "meal_date",
        "cafeteria",
        "meal_type",
        "user_type",
        "menu_name",
        "price",
        "menu_items",
        "is_closed",
        "closed_reason",
    ]
    assert doc.metadata["raw_path"] == row.raw_path
    assert doc.metadata["raw_checksum"] == row.raw_checksum
    assert doc.metadata["raw_fetched_at"] == row.raw_fetched_at
    assert doc.metadata["verification_official_chain_ok"] is False
    assert doc.metadata["verification_parser_name"] == row.parser_name
    assert doc.metadata["verification_parser_version"] == row.parser_version
    assert doc.metadata["source_freshness_policy"] == row.freshness_policy
