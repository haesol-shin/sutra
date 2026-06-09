import sys
import json
from pathlib import Path

tests_dir = Path(__file__).resolve().parent
project_root = tests_dir.parent.parent.parent
scripts_dir = project_root / "examples" / "cnu-campus" / "scripts"
sys.path.insert(0, str(scripts_dir))

from cnu_shuttle import (  # noqa: E402
    parse_shuttle_file, normalize_text, RouteRecord, NoticeRecord
)

def test_bus_page_parsing():
    bus_path = project_root / "data" / "raw" / "shuttle" / "shuttle_bus.html"
    assert bus_path.exists()
    result = parse_shuttle_file(str(bus_path))
    assert result.status == "success"
    route_records = [r for r in result.records if r[0] == "route"]
    assert len(route_records) >= 1
    for rec in route_records:
        assert len(rec) == 3
        rec_type, rec_data, src_info = rec
        assert rec_type == "route"
        assert isinstance(rec_data, RouteRecord)
        assert rec_data.route_name
        assert rec_data.time_table_text
        assert rec_data.route_stops_text

def test_geo_notice_parsing():
    geo_path = project_root / "data" / "raw" / "shuttle" / "shuttle_geo_notice_2026.html"
    assert geo_path.exists()
    result = parse_shuttle_file(str(geo_path))
    if result.status == "success":
        notice_records = [r for r in result.records if r[0] == "notice"]
        assert len(notice_records) >= 1
        for rec in notice_records:
            assert len(rec) == 3
            _, rec_data, _ = rec
            assert isinstance(rec_data, NoticeRecord)
            assert rec_data.body_text
            assert any(kw in rec_data.body_text for kw in ["2026. 3. 3.", "셔틀버스", "운행"])
    else:
        assert result.status == "skipped"

def test_normalize_text():
    assert normalize_text("  안녕 \n\n  하세요  ") == "안녕\n하세요"
    assert normalize_text("") == ""
    assert normalize_text(None) == ""

def test_source_meta_passthrough():
    bus_path = project_root / "data" / "raw" / "shuttle" / "shuttle_bus.html"
    meta = {
        "url": "https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html",
        "fetched_at": "2026-06-09T00:48:17.109477+09:00"
    }
    result = parse_shuttle_file(str(bus_path), meta)
    if result.status == "success":
        for rec in result.records:
            rec_type, rec_data, src_info = rec
            if isinstance(rec_data, RouteRecord):
                assert rec_data.source_url == meta["url"]
                assert rec_data.fetched_at == meta["fetched_at"]

def test_route_names_found():
    bus_path = project_root / "data" / "raw" / "shuttle" / "shuttle_bus.html"
    result = parse_shuttle_file(str(bus_path))
    assert result.status == "success"
    route_names = set()
    for rec in result.records:
        rec_type, rec_data, _ = rec
        if isinstance(rec_data, RouteRecord):
            route_names.add(rec_data.route_name)
    assert any("순환" in name for name in route_names)
    assert len(route_names) >= 1

def test_generated_index_schema():
    index_path = project_root / "examples" / "cnu-campus" / "data" / "processed" / "shuttle-index.jsonl"
    if not index_path.exists():
        from build_shuttle_index import main as build_main
        build_main()
    assert index_path.exists()
    rows = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    for row in rows:
        assert "id" in row
        assert "title" in row
        assert "text" in row
        assert "body" not in row
        assert row.get("source_url")
        assert row.get("source_name")
        assert row.get("metadata") is not None

def test_generated_report():
    report_path = project_root / "examples" / "cnu-campus" / "data" / "reports" / "shuttle-build-report.json"
    if not report_path.exists():
        from build_shuttle_index import main as build_main
        build_main()
    assert report_path.exists()
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    assert "parsed_files" in report
    assert "skipped_files" in report
    assert "unique_chunk_count" in report
    assert "route_names_found" in report
    assert "known_limitations" in report
