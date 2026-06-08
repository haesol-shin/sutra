from __future__ import annotations

from pathlib import Path

from nlp_term.collect.base import PARSER_VERSION
from nlp_term.collect.source_inventory import iter_specs
from nlp_term.schemas import RawSource, SourceVerification
from nlp_term.structured.dining import DiningAdapter


RAW_PATH = Path("data/raw/dining/cnu_mobile_food.html")


def _context(fetched_at: str = "2026-06-08T02:02:37+00:00"):
    spec = next(item for item in iter_specs(stage="stage0") if item.source_id == "cnu_mobile_food")
    raw = RawSource(
        source_id=spec.source_id,
        label=spec.label,
        domain=spec.domain,
        url=spec.url,
        fetched_at=fetched_at,
        content_type="text/html; charset=UTF-8",
        raw_path=str(RAW_PATH),
        status_code=200,
        checksum="dining-raw-checksum",
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


def test_dining_adapter_parses_table_rows_from_saved_raw() -> None:
    spec, raw, verification = _context()

    rows = DiningAdapter().parse(spec=spec, raw=raw, verification=verification)

    assert rows
    assert any(row.meal_date == "2026-06-08" for row in rows)
    assert {"제1학생회관", "제2학생회관"}.issubset({row.cafeteria for row in rows})
    assert {"조식", "중식", "석식"}.issubset({row.meal_type for row in rows})
    assert {"직원", "학생"}.issubset({row.user_type for row in rows})


def test_dining_adapter_keeps_closed_rows_and_prices() -> None:
    spec, raw, verification = _context()

    rows = DiningAdapter().parse(spec=spec, raw=raw, verification=verification)

    assert any(row.is_closed and row.closed_reason == "운영안함" for row in rows)
    student_lunch = next(
        row
        for row in rows
        if row.cafeteria == "제1학생회관" and row.meal_type == "중식" and row.user_type == "학생"
    )
    assert student_lunch.menu_name == "정식"
    assert student_lunch.price == 4500
    assert "김치볶음밥" in student_lunch.menu_items


def test_dining_adapter_row_ids_ignore_fetched_at() -> None:
    spec, raw, verification = _context(fetched_at="2026-06-08T02:02:37+00:00")
    newer_raw = raw.model_copy(update={"fetched_at": "2026-06-09T02:02:37+00:00"})

    first_ids = [row.row_id for row in DiningAdapter().parse(spec=spec, raw=raw, verification=verification)]
    second_ids = [row.row_id for row in DiningAdapter().parse(spec=spec, raw=newer_raw, verification=verification)]

    assert first_ids == second_ids


def test_dining_adapter_knowledge_docs_preserve_safety_metadata() -> None:
    spec, raw, verification = _context()
    adapter = DiningAdapter()
    rows = adapter.parse(spec=spec, raw=raw, verification=verification)

    docs = adapter.to_knowledge_docs(rows)

    assert docs
    first = docs[0]
    assert first.metadata["structured"]
    assert first.metadata["menu_date"]
    assert first.metadata["cafeteria"]
    assert first.metadata["structured_fields"]
    assert first.metadata["verification_official_chain_ok"] is False
    assert first.metadata["source_freshness_policy"] == "short_ttl"
