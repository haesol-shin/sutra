import sys
import re
import json
from pathlib import Path
import pytest

# Resolve paths to allow importing examples/cnu-campus/scripts modules
tests_dir = Path(__file__).resolve().parent
project_root = tests_dir.parent.parent.parent
scripts_dir = project_root / "examples" / "cnu-campus" / "scripts"
sys.path.insert(0, str(scripts_dir))

from cnu_dining import parse_dining_file, normalize_menu_text, should_skip_record, MenuRecord
from build_dining_index import is_standalone_eligible, build_markdown_body, check_date_mismatches

def test_normalize_menu_text():
    text = "  참치김치찌개 \n\n   고추마요떡갈비   "
    assert normalize_menu_text(text) == "참치김치찌개\n고추마요떡갈비"
    assert normalize_menu_text("") == ""
    assert normalize_menu_text(None) == ""

def test_should_skip_record():
    assert should_skip_record("메뉴는 운영중입니다") is True
    assert should_skip_record("메뉴운영내역") is True
    assert should_skip_record("메뉴는준비중입니다") is True
    assert should_skip_record("") is True
    assert should_skip_record("운영안함") is False
    assert should_skip_record("참치김치찌개") is False

def test_weekly_view_parsing():
    weekly_html_path = project_root / "data" / "raw" / "dining" / "cnu_mobile_food_week_2026_06_08_2nd.html"
    assert weekly_html_path.exists()
    
    result = parse_dining_file(str(weekly_html_path))
    assert result.status == "success"
    assert len(result.records) > 0
    
    for record in result.records:
        assert record.cafeteria == "제2학생회관"
        assert record.date.startswith("2026-06-")
        assert record.meal in ["조식", "중식", "석식"]
        assert record.audience in ["직원", "학생"]
        assert "운영중입니다" not in record.menu_text
        assert "운영내역" not in record.menu_text

def test_daily_view_parsing():
    daily_html_path = project_root / "data" / "raw" / "dining" / "cnu_mobile_food.html"
    assert daily_html_path.exists()
    
    result = parse_dining_file(str(daily_html_path))
    assert result.status == "success"
    assert len(result.records) > 0
    
    for record in result.records:
        assert record.date == "2026-06-08"
        assert record.cafeteria in ["제1학생회관", "제2학생회관", "제3학생회관", "제4학생회관", "생활과학대학"]
        assert record.meal in ["조식", "중식", "석식"]
        assert record.audience in ["직원", "학생"]

def test_skip_notice_file():
    notice_html_path = project_root / "data" / "raw" / "dining" / "dining_operation_notice_2507684.html"
    assert notice_html_path.exists()
    
    result = parse_dining_file(str(notice_html_path))
    assert result.status == "skipped"
    assert len(result.records) == 0

def test_standalone_chunk_eligibility():
    rec_active = MenuRecord(
        date="2026-06-08", cafeteria="제2학생회관", meal="중식", audience="학생",
        menu_text="김치찌개\n계란말이"
    )
    rec_inactive = MenuRecord(
        date="2026-06-08", cafeteria="제2학생회관", meal="조식", audience="직원",
        menu_text="운영안함"
    )
    
    assert is_standalone_eligible([rec_active, rec_inactive]) is True
    assert is_standalone_eligible([rec_inactive]) is False

def test_markdown_body_generation():
    records = [
        MenuRecord(
            date="2026-06-08", cafeteria="제2학생회관", meal="중식", audience="학생",
            menu_text="김치찌개\n계란말이"
        ),
        MenuRecord(
            date="2026-06-08", cafeteria="제2학생회관", meal="조식", audience="학생",
            menu_text="참치야채죽"
        ),
        MenuRecord(
            date="2026-06-08", cafeteria="제2학생회관", meal="조식", audience="직원",
            menu_text="운영안함"
        )
    ]
    
    body = build_markdown_body(records)
    
    assert "### 조식" in body
    assert "### 중식" in body
    assert "- 직원: 운영안함" in body
    assert "- 학생: 참치야채죽" in body
    assert "- 학생: 김치찌개\n  계란말이" in body

def test_check_date_mismatches_helper():
    # 1. Match case: date hint matches parsed dates
    res = check_date_mismatches(
        "data/raw/dining/cnu_mobile_food_week_2026_06_08_2nd.html",
        "https://mobileadmin.cnu.ac.kr/food/index.jsp?searchYmd=2026.06.08",
        ["2026-06-08", "2026-06-09"]
    )
    assert res is None
    
    # 2. Mismatch case: date hint (2026-06-15) is not in parsed dates
    res2 = check_date_mismatches(
        "data/raw/dining/cnu_mobile_food_week_2026_06_15_2nd.html",
        "https://mobileadmin.cnu.ac.kr/food/index.jsp?searchYmd=2026.06.15",
        ["2026-06-08", "2026-06-09"]
    )
    assert res2 is not None
    assert res2["file"] == "data/raw/dining/cnu_mobile_food_week_2026_06_15_2nd.html"
    assert "2026-06-15" in res2["hinted_dates"]
    assert res2["parsed_dates"] == ["2026-06-08", "2026-06-09"]
    assert res2["reason"] == "filename_or_url_date_not_in_parsed_dates"

def test_report_schema_and_contents():
    report_path = project_root / "examples" / "cnu-campus" / "data" / "reports" / "dining-build-report.json"
    
    # If the report does not exist yet, trigger build first
    if not report_path.exists():
        from build_dining_index import main as build_main
        build_main()
        
    assert report_path.exists()
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    assert "date_mismatches" in report
    assert "missing_source_meta" in report
    assert "dates" in report
    assert "cafeterias" in report
    
    # Verify missing metadata format
    assert isinstance(report["missing_source_meta"], list)
    for meta in report["missing_source_meta"]:
        assert "file" in meta
        assert meta["reason"] == "source_probe_metadata_not_found"
        
    # Verify date mismatches format
    assert isinstance(report["date_mismatches"], list)
    for mismatch in report["date_mismatches"]:
        assert "file" in mismatch
        assert "hinted_dates" in mismatch
        assert "parsed_dates" in mismatch
        assert mismatch["reason"] == "filename_or_url_date_not_in_parsed_dates"
