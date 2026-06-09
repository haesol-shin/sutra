import json
import re
from pathlib import Path
from cnu_shuttle import (
    parse_shuttle_file, RouteRecord, NoticeRecord, normalize_text
)

SHUTTLE_SOURCE_NAME = "충남대학교 학교셔틀버스"
SHUTTLE_SOURCE_URL = "https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html"

def make_chunk_id(domain_part: str, unique_str: str) -> str:
    safe = re.sub(r'[^a-zA-Z0-9가-힣]', '', unique_str)
    safe = re.sub(r'\s+', '_', safe)
    return f"shuttle_{domain_part}_{safe}"

def main():
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent
    raw_shuttle_dir = project_root / "data" / "raw" / "shuttle"
    probe_path = project_root / "data" / "sources" / "source_probe.json"
    processed_dir = project_root / "examples" / "cnu-campus" / "data" / "processed"
    reports_dir = project_root / "examples" / "cnu-campus" / "data" / "reports"
    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_index_path = processed_dir / "shuttle-index.jsonl"
    output_report_path = reports_dir / "shuttle-build-report.json"
    meta_map = {}
    if probe_path.exists():
        try:
            with open(probe_path, "r", encoding="utf-8") as f:
                probe_data = json.load(f)
                for item in probe_data:
                    raw_info = item.get("raw", {})
                    raw_p = raw_info.get("raw_path")
                    if raw_p:
                        key = Path(raw_p).as_posix().lower()
                        meta_map[key] = {
                            "url": raw_info.get("url"),
                            "fetched_at": raw_info.get("fetched_at"),
                            "source_id": raw_info.get("source_id")
                        }
        except Exception as e:
            print(f"Warning: Failed to load source_probe.json: {e}")
    dedup_count = 0
    raw_records_map = {}
    parsed_files = []
    skipped_files = []
    missing_source_meta = []
    if raw_shuttle_dir.exists():
        html_files = sorted(list(raw_shuttle_dir.glob("*.html")))
        for filepath in html_files:
            rel_path = filepath.relative_to(project_root)
            rel_path_str = rel_path.as_posix()
            key = rel_path.as_posix().lower()
            meta = meta_map.get(key)
            if not meta:
                missing_source_meta.append({
                    "file": rel_path_str,
                    "reason": "source_probe_metadata_not_found"
                })
            result = parse_shuttle_file(str(filepath), meta)
            if result.status == "success":
                parsed_files.append(rel_path_str)
                for rec in result.records:
                    rec_type = rec[0]
                    rec_data = rec[1]
                    dedup_key = None
                    if isinstance(rec_data, str):
                        dedup_key = f"summary_{normalize_text(rec_data)}"
                    elif isinstance(rec_data, RouteRecord):
                        dedup_key = f"route_{rec_data.route_name}"
                    elif isinstance(rec_data, NoticeRecord):
                        dedup_key = f"notice_{normalize_text(rec_data.body_text[:100])}"
                    if dedup_key:
                        if dedup_key not in raw_records_map:
                            raw_records_map[dedup_key] = (rel_path_str, rec_type, rec_data)
                        else:
                            dedup_count += 1
            else:
                skipped_files.append({
                    "file": rel_path_str,
                    "reason": result.error_msg or "Unknown skip reason"
                })
    else:
        print(f"Error: Raw shuttle directory not found at {raw_shuttle_dir}")
        return
    raw_records = list(raw_records_map.values())
    chunks = []
    route_names_found = set()
    dates_found = set()
    missing_url_count = 0
    missing_name_count = 0
    for rel_src, rec_type, rec_data in raw_records:
        if isinstance(rec_data, str):
            source_url = SHUTTLE_SOURCE_URL
            source_name = SHUTTLE_SOURCE_NAME
            chunk_id = f"shuttle_summary_{Path(rel_src).stem}"
            chunk = {
                "id": chunk_id,
                "domain": "shuttle",
                "title": "2026학년도 학교셔틀버스 운영 안내 요약",
                "text": rec_data,
                "source_url": source_url,
                "source_name": source_name,
                "source_path": rel_src,
                "generation_method": "structured_aggregate",
                "metadata": {
                    "domain_type": "operating_summary",
                    "effective_year": "2026"
                }
            }
            chunks.append(chunk)
        elif isinstance(rec_data, RouteRecord):
            source_url = rec_data.source_url or SHUTTLE_SOURCE_URL
            source_name = SHUTTLE_SOURCE_NAME
            clean_name = rec_data.route_name.replace('\n', ' ')
            route_names_found.add(clean_name)
            body_lines = []
            body_lines.append(f"노선: {clean_name}")
            if rec_data.time_table_text:
                body_lines.append(f"운행 시간: {rec_data.time_table_text}")
            if rec_data.first_bus and rec_data.last_bus:
                body_lines.append(f"첫차: {rec_data.first_bus}, 막차: {rec_data.last_bus}")
            if rec_data.trips_per_day:
                body_lines.append(f"운행 횟수: {rec_data.trips_per_day}")
            if rec_data.route_stops_text:
                body_lines.append(f"운행 노선: {rec_data.route_stops_text}")
            if rec_data.operating_note:
                body_lines.append(f"참고: {rec_data.operating_note}")
            route_safe = re.sub(r'[^a-zA-Z0-9가-힣]', '', clean_name)[:20]
            chunk_id = f"shuttle_route_{route_safe}"
            chunk = {
                "id": chunk_id,
                "domain": "shuttle",
                "title": f"셔틀버스 {clean_name} 운행 정보",
                "text": "\n".join(body_lines),
                "source_url": source_url,
                "source_name": source_name,
                "source_path": rel_src,
                "generation_method": "structured_aggregate",
                "metadata": {
                    "domain_type": "route",
                    "route_name": clean_name,
                    "route_type": rec_data.route_type,
                    "first_bus": rec_data.first_bus,
                    "last_bus": rec_data.last_bus,
                    "trips_per_day": rec_data.trips_per_day
                }
            }
            chunks.append(chunk)
        elif isinstance(rec_data, NoticeRecord):
            source_url = rec_data.source_url or "https://geo.cnu.ac.kr/notice/?vid=956"
            source_name = "충남대학교 지질환경과학과 공지사항"
            if rec_data.posted_date:
                dates_found.add(rec_data.posted_date)
            chunk_id = "shuttle_notice_2026_operation"
            body = rec_data.body_text
            if rec_data.posted_date:
                body = f"[공지일: {rec_data.posted_date}]\n" + body
            chunk = {
                "id": chunk_id,
                "domain": "shuttle",
                "title": rec_data.title or "2026학년도 충남대학교 셔틀버스 운영 안내",
                "text": body,
                "source_url": source_url,
                "source_name": source_name,
                "source_path": rel_src,
                "generation_method": "source_parse",
                "metadata": {
                    "domain_type": "notice",
                    "posted_date": rec_data.posted_date,
                    "effective_year": "2026"
                }
            }
            chunks.append(chunk)
    report = {
        "parsed_files": parsed_files,
        "skipped_files": skipped_files,
        "raw_records_count": len(raw_records),
        "unique_chunk_count": len(chunks),
        "duplicate_count": dedup_count,
        "missing_source_url_count": missing_url_count,
        "missing_source_name_count": missing_name_count,
        "route_names_found": sorted(list(route_names_found)),
        "dates_found": sorted(list(dates_found)),
        "missing_source_meta": missing_source_meta,
        "known_limitations": [
            "셔틀버스 운영 시간표는 학기 중 평일 기준이며 방학/주말/공휴일은 미운영",
            "shuttle_geo_notice_2026.html 내용은 한글(HWP) 문서가 첨부된 WordPress 공지로, HTML 본문에서 추출 가능한 텍스트만 포함",
            "운행 시간은 교통 상황 등으로 5분 내외 오차 가능",
            "2026학년도 기준(2026.3.3~12.18) 스냅샷이며 이후 변경 가능"
        ]
    }
    try:
        with open(output_index_path, "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
        print(f"Successfully wrote {len(chunks)} chunks to {output_index_path}")
    except Exception as e:
        print(f"Error writing index JSONL: {e}")
    try:
        with open(output_report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Successfully wrote build report to {output_report_path}")
    except Exception as e:
        print(f"Error writing build report: {e}")

if __name__ == "__main__":
    main()
