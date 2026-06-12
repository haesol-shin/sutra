import sys
import json
from pathlib import Path

import pytest

# Resolve paths to allow importing examples/cnu-campus/scripts modules
tests_dir = Path(__file__).resolve().parent
project_root = tests_dir.parent.parent.parent
scripts_dir = project_root / "examples" / "cnu-campus" / "scripts"
sys.path.insert(0, str(scripts_dir))

from cnu_dining import parse_dining_file, normalize_menu_text, should_skip_record, MenuRecord  # noqa: E402
from build_dining_index import (  # noqa: E402
    build_daily_menu_docs,
    build_food_court_docs,
    build_markdown_body,
    build_operating_info_doc,
    check_date_mismatches,
    is_standalone_eligible,
)

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
    if not weekly_html_path.exists():
        pytest.skip("raw dining HTML is git-ignored and unavailable in this worktree")
    
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
    if not daily_html_path.exists():
        pytest.skip("raw dining HTML is git-ignored and unavailable in this worktree")
    
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
    if not notice_html_path.exists():
        pytest.skip("raw dining HTML is git-ignored and unavailable in this worktree")
    
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


def test_daily_menu_docs_merge_cafeterias_and_drop_closed_slots():
    records = [
        MenuRecord(
            date="2026-06-11", cafeteria="제1학생회관", meal="중식", audience="학생",
            menu_text="정식(4500)\n김치볶음밥"
        ),
        MenuRecord(
            date="2026-06-11", cafeteria="제2학생회관", meal="조식", audience="직원",
            menu_text="운영안함"
        ),
        MenuRecord(
            date="2026-06-11", cafeteria="제2학생회관", meal="조식", audience="학생",
            menu_text="정식(1000)\n육개장(beef included)\n연두부&양념장\n깍두기"
        ),
        MenuRecord(
            date="2026-06-11", cafeteria="제2학생회관", meal="중식", audience="직원",
            menu_text="정식(6000)\n순두부육개장(beef included)\n바싹불고기육전(pork included)"
        ),
        MenuRecord(
            date="2026-06-11", cafeteria="제3학생회관", meal="석식", audience="직원",
            menu_text="정식(6000)\n마파두부덮밥"
        ),
    ]

    docs = build_daily_menu_docs(records)

    assert len(docs) == 1
    doc = docs[0]
    assert doc["id"] == "dining_2026-06-11"
    assert doc["title"] == "2026-06-11 (목) 학생식당 식단"
    assert doc["metadata"]["date"] == "2026-06-11"
    assert doc["metadata"]["domain"] == "dining"
    assert "# 2026-06-11 (목) 학생식당 식단" in doc["text"]
    assert "이번주 학식" in doc["text"]
    assert "## 제1학생회관" not in doc["text"]
    assert "운영안함" not in doc["text"]
    assert "- 아침(학생) 정식 1,000원: 육개장(beef included), 연두부&양념장, 깍두기" in doc["text"]
    assert "- 점심(직원) 정식 6,000원: 순두부육개장(beef included), 바싹불고기육전(pork included)" in doc["text"]
    assert "- 저녁(직원) 정식 6,000원: 마파두부덮밥" in doc["text"]


def test_operating_info_doc_derives_weekday_schedule_from_records():
    records = [
        MenuRecord(
            date="2026-06-09", cafeteria="제2학생회관", meal="조식", audience="학생",
            menu_text="정식(1000)\n참치야채죽"
        ),
        MenuRecord(
            date="2026-06-09", cafeteria="제2학생회관", meal="중식", audience="직원",
            menu_text="정식(6000)\n불고기뚝배기(beef included)"
        ),
        MenuRecord(
            date="2026-06-09", cafeteria="제2학생회관", meal="중식", audience="학생",
            menu_text="정식(4500)\n치즈닭갈비덮밥(chicken included)"
        ),
        MenuRecord(
            date="2026-06-09", cafeteria="제2학생회관", meal="석식", audience="직원",
            menu_text="운영안함"
        ),
        MenuRecord(
            date="2026-06-09", cafeteria="제2학생회관", meal="석식", audience="학생",
            menu_text="정식(1000)\n소고기해장국(beef included)"
        ),
        MenuRecord(
            date="2026-06-09", cafeteria="제4학생회관", meal="중식", audience="학생",
            menu_text="정식(6000)\n비빔밥"
        ),
    ]

    doc = build_operating_info_doc(records)

    assert doc["id"] == "dining_operating_info"
    assert doc["title"] == "학생식당 운영 안내"
    assert doc["metadata"]["domain"] == "dining"
    assert "| 제2학생회관 | 학생 | 직원, 학생 | 학생 |" in doc["text"]
    assert "| 제4학생회관 | - | 학생 | - |" in doc["text"]
    assert "주말·공휴일 미운영" in doc["text"]
    assert "| 라면&간식 | 10:00~14:00 | 2,500~4,000원 |" in doc["text"]
    assert "운영안함" not in doc["text"]


def test_food_court_docs_cover_six_corners():
    docs = build_food_court_docs()

    assert len(docs) == 6
    assert {doc["metadata"]["corner"] for doc in docs} == {"라면&간식", "양식", "스낵(퓨전)", "한식", "일식", "중식"}
    japanese = next(doc for doc in docs if doc["metadata"]["corner"] == "일식")
    assert japanese["id"] == "dining_food_court_제1학생회관_일식"
    assert japanese["source_name"] == "충남대학교 제1학생회관 푸드코트"
    assert "운영시간: 11:00~19:00" in japanese["text"]
    assert "- 마제소바: 6,000원" in japanese["text"]
    chinese = next(doc for doc in docs if doc["metadata"]["corner"] == "중식")
    assert "소고기 미국산" in chinese["text"]

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


def test_generated_dining_index_uses_sutra_document_text_schema():
    index_path = project_root / "examples" / "cnu-campus" / "data" / "processed" / "dining-index.jsonl"

    if not index_path.exists():
        from build_dining_index import main as build_main
        build_main()

    rows = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    for row in rows:
        assert "id" in row
        assert "title" in row
        assert "text" in row
        assert "body" not in row
        assert row["domain"] == "dining"
        assert row["source_name"]
        assert row["source_url"]
        assert row["metadata"]["domain"] == "dining"
        assert "운영안함" not in row["text"]

    daily_rows = [row for row in rows if row["id"].startswith("dining_2026-")]
    operating_rows = [row for row in rows if row["id"] == "dining_operating_info"]
    food_court_rows = [row for row in rows if row["id"].startswith("dining_food_court_")]

    assert len(daily_rows) == 5
    assert len(operating_rows) == 1
    assert len(food_court_rows) == 6
    for row in daily_rows:
        assert row["metadata"]["date"]
        assert row["metadata"]["cafeterias"]
