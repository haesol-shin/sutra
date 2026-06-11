import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import List, Optional
from cnu_dining import MenuRecord, parse_dining_file
from sutra.dining_format import (
    AUDIENCE_ORDER,
    CAFETERIA_ORDER,
    MEAL_LABELS,
    active_dining_cafeterias,
    format_dining_day,
    format_price,
    is_closed_record,
)

SOURCE_NAME = "충남대학교 생활협동조합 식단"
FOOD_COURT_SOURCE_NAME = "충남대학교 제1학생회관 푸드코트"
DEFAULT_DINING_URL = "https://mobileadmin.cnu.ac.kr/food/index.jsp"
FOOD_COURT_SIDE_ITEM_EXACT = {"공기밥", "치즈추가", "구운계란2개", "마라맛", "½우동", "주먹밥2개"}

FOOD_COURT_CORNERS = [
    {
        "corner": "라면&간식",
        "hours": "10:00~14:00",
        "price_range": "2,500~4,000원",
        "notes": "저녁 미운영, 주말 미운영",
        "items": [
            ("라면", 2500), ("떡만두라면", 3000), ("해장라면", 3000), ("치즈라면", 3000),
            ("부대라면", 4000), ("김밥", 3000), ("공기밥", 500),
        ],
        "origins": "쌀 국내산, 배추김치(국내산), 김밥햄 닭·돼지(국산), 런천미트 돼지(외국산)·돈지방(국산), 후랑크 닭·돼지(국산).",
    },
    {
        "corner": "양식",
        "hours": "11:00~14:00",
        "price_range": "5,500~6,500원",
        "notes": "저녁 미운영, 주말 미운영",
        "items": [
            ("등심왕돈까스", 5500), ("눈꽃치즈돈까스", 6000), ("파채돈까스", 6000),
            ("돈까스&파스타", 6500), ("닭다리살스테이크", 6000), ("파닭스테이크", 6500),
            ("베이컨로제파스타", 5800),
        ],
        "origins": "쌀 국내산, 닭다리살 브라질산, 돈까스 돼지(국내산), 베이컨 돼지(외국산).",
    },
    {
        "corner": "스낵(퓨전)",
        "hours": "11:00~14:30",
        "price_range": "500~6,500원",
        "notes": "저녁 미운영, 주말 미운영",
        "items": [
            ("버터김치별달알밥", 5600), ("버터김치치즈알밥", 6500), ("치즈토핑", 1000),
            ("소불고기토핑", 2000), ("떡갈비토핑", 1000), ("감자고로케토핑", 1000),
            ("날치알토핑", 1000), ("구운계란토핑", 500), ("컵버터감자칩", 2000),
        ],
        "origins": "쌀 국내산, 배추김치 중국산, 소고기 미국·호주산, 닭고기 국내산, 돼지고기 국내산, 스팸 외국산, 부대햄 국산·미국산, 떡갈비 국산, 두부 콩 외국산.",
    },
    {
        "corner": "한식",
        "hours": "11:00~14:00, 17:00~19:00",
        "price_range": "500~7,000원",
        "notes": "주말 미운영",
        "items": [
            ("비빔밥", 7000), ("묵은지김치찌개", 5800), ("부대햄플러스김치찌개", 6800),
            ("우삼겹된장찌개", 6600), ("별달소고기국밥", 7000), ("뚝배기닭갈비덮밥", 5800),
            ("치즈추가", 1500), ("구운계란2개", 1000), ("공기밥", 500),
        ],
        "origins": "쌀 국내산, 배추김치 중국산, 소고기 미국·호주산, 닭고기 국내산, 돼지고기 국내산, 스팸 외국산, 부대햄 국산·미국산, 떡갈비 국산, 두부 콩 외국산.",
    },
    {
        "corner": "일식",
        "hours": "11:00~19:00",
        "price_range": "1,500~7,500원",
        "notes": "주말 미운영",
        "items": [
            ("얼큰순두부우동국밥", 6300), ("매운부타동고기덮밥", 7500), ("고소한카레덮밥", 5800),
            ("부타동고기덮밥", 5800), ("치킨가라아게마요", 6500), ("세곱배기생우동", 6500),
            ("매운속풀이해장우동", 5300), ("가쓰오부시생우동", 5000), ("마제소바", 6000),
            ("1L치킨포케샐러드", 6800), ("½우동+주먹밥+가라아게4p", 7500),
            ("꼬치어묵2p+생우동", 6500), ("컵가라아게4p", 2000), ("½우동", 3500), ("주먹밥2개", 1500),
        ],
        "origins": "쌀 국내산, 배추김치 중국산, 소고기 미국·호주산, 닭고기 국내산, 돼지고기 국내산, 스팸 외국산, 부대햄 국산·미국산, 떡갈비 국산, 두부 콩 외국산.",
    },
    {
        "corner": "중식",
        "hours": "11:00~14:00, 16:00~19:00",
        "price_range": "500~6,500원",
        "notes": "주말 미운영",
        "items": [
            ("차돌온면", 6500), ("매운차돌온면", 6500), ("온국밥", 6500), ("매운온국밥", 6500),
            ("비빔면", 5800), ("냉면", 5800), ("마라맛", 500), ("공기밥", 500),
        ],
        "origins": "쌀 국내산, 배추김치(중국산), 소고기 미국산, 돼지고기 국내산.",
    },
]

def check_date_mismatches(file_path_str: str, source_url: Optional[str], parsed_dates: List[str]) -> Optional[dict]:
    # Extract hinted dates from filename and URL
    hinted_dates = set()
    for source in [file_path_str, source_url or ""]:
        # Find YYYY-MM-DD, YYYY.MM.DD, YYYY_MM_DD
        matches = re.findall(r'(\d{4})[._-](\d{2})[._-](\d{2})', source)
        for m in matches:
            hinted_dates.add(f"{m[0]}-{m[1]}-{m[2]}")
            
    hinted_dates_list = sorted(list(hinted_dates))
    
    # Check mismatch: if we have hints, and any hinted date is NOT in parsed_dates
    if hinted_dates_list:
        for h_date in hinted_dates_list:
            if h_date not in parsed_dates:
                return {
                    "file": file_path_str,
                    "hinted_dates": hinted_dates_list,
                    "parsed_dates": parsed_dates,
                    "reason": "filename_or_url_date_not_in_parsed_dates"
                }
    return None

def main():
    # 1. Path Resolution
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent
    
    raw_dining_dir = project_root / "data" / "raw" / "dining"
    probe_path = project_root / "data" / "sources" / "source_probe.json"
    
    processed_dir = project_root / "examples" / "cnu-campus" / "data" / "processed"
    reports_dir = project_root / "examples" / "cnu-campus" / "data" / "reports"
    
    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    output_index_path = processed_dir / "dining-index.jsonl"
    output_report_path = reports_dir / "dining-build-report.json"
    
    # 2. Load Source Probe Metadata
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
            
    # 3. Iterate through raw dining HTML files
    raw_records = []
    parsed_files = []
    skipped_files = []
    date_mismatches = []
    missing_source_meta = []
    source_mode = "raw_html"
    
    if raw_dining_dir.exists():
        html_files = sorted(list(raw_dining_dir.glob("*.html")))
        for filepath in html_files:
            rel_path = filepath.relative_to(project_root)
            rel_path_str = rel_path.as_posix()
            key = rel_path.as_posix().lower()
            
            meta = meta_map.get(key)
            
            # Check for missing source metadata
            # We only track missing metadata for files that are not skipped as notice files
            filename = filepath.name.lower()
            is_notice = "notice" in filename or "dining_operation" in filename
            
            if not meta and not is_notice:
                missing_source_meta.append({
                    "file": rel_path_str,
                    "reason": "source_probe_metadata_not_found"
                })
                
            result = parse_dining_file(str(filepath), meta)
            
            if result.status == "success":
                raw_records.extend(result.records)
                parsed_files.append(rel_path_str)
                
                # Check for date mismatch
                file_parsed_dates = sorted(list(set(r.date for r in result.records)))
                url_hint = meta.get("url") if meta else None
                mismatch_info = check_date_mismatches(rel_path_str, url_hint, file_parsed_dates)
                if mismatch_info:
                    date_mismatches.append(mismatch_info)
            else:
                skipped_files.append({
                    "file": rel_path_str,
                    "reason": result.error_msg or "Unknown skip reason"
                })
    if not raw_records:
        fallback_records, source_mode = load_fallback_records(output_report_path, output_index_path, project_root)
        if fallback_records:
            raw_records = fallback_records
            skipped_files.append({
                "file": raw_dining_dir.relative_to(project_root).as_posix() if raw_dining_dir.exists() else "data/raw/dining",
                "reason": f"raw dining HTML unavailable; rebuilt from {source_mode}"
            })
        else:
            print(f"Error: no raw dining records found and no fallback records available at {raw_dining_dir}")
            return
        
    # 4. Dedup & Conflict Check
    unique_records_map = {}
    duplicate_records_count = 0
    conflicts = []
    
    for record in raw_records:
        key = (record.date, record.cafeteria, record.meal, record.audience)
        norm_menu = record.menu_text.replace(" ", "").replace("\n", "")
        
        if key not in unique_records_map:
            unique_records_map[key] = record
        else:
            existing_record = unique_records_map[key]
            norm_existing = existing_record.menu_text.replace(" ", "").replace("\n", "")
            
            if norm_menu == norm_existing:
                duplicate_records_count += 1
            else:
                rel_existing_src = Path(existing_record.source_path).relative_to(project_root).as_posix() if existing_record.source_path else "unknown"
                rel_new_src = Path(record.source_path).relative_to(project_root).as_posix() if record.source_path else "unknown"
                
                conflicts.append({
                    "key": f"{record.date} {record.cafeteria} {record.meal} {record.audience}",
                    "existing": existing_record.menu_text,
                    "new": record.menu_text,
                    "existing_source": rel_existing_src,
                    "new_source": rel_new_src
                })
                # Keep the first parsed value, discard the new one
                
    unique_records = list(unique_records_map.values())
    
    # 5. Build requested dining corpus:
    #    A) one daily menu doc per date, B) one operating guide, C) food-court corner docs.
    daily_docs = build_daily_menu_docs(unique_records, project_root=project_root, meta_map=meta_map)
    operating_info_doc = build_operating_info_doc(unique_records)
    food_court_docs = build_food_court_docs()
    chunks = daily_docs + [operating_info_doc] + food_court_docs
        
    # Gather summary dates and cafeterias
    generated_dates = sorted(list(set(chunk["metadata"].get("date") for chunk in daily_docs if chunk["metadata"].get("date"))))
    generated_cafeterias = sorted(list(set(r.cafeteria for r in unique_records if r.cafeteria != "제1학생회관")))
    
    # 6. Write JSONL index
    try:
        with open(output_index_path, "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
        print(f"Successfully wrote {len(chunks)} chunks to {output_index_path}")
    except Exception as e:
        print(f"Error writing index JSONL: {e}")
        
    # 7. Write build report JSON
    report = {
        "parsed_files": parsed_files,
        "skipped_files": skipped_files,
        "raw_records": len(raw_records),
        "unique_records": len(unique_records),
        "duplicate_records": duplicate_records_count,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "chunk_count": len(chunks),
        "daily_doc_count": len(daily_docs),
        "operating_info_count": 1,
        "food_court_doc_count": len(food_court_docs),
        "closed_record_count": sum(1 for r in unique_records if is_closed_record(r)),
        "source_mode": source_mode,
        "operating_schedule": derive_operating_schedule(unique_records),
        "date_mismatches": date_mismatches,
        "missing_source_meta": missing_source_meta,
        "dates": generated_dates,
        "cafeterias": generated_cafeterias,
        "source_records": [record_to_json(r, project_root) for r in unique_records],
    }
    
    try:
        with open(output_report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Successfully wrote build report to {output_report_path}")
    except Exception as e:
        print(f"Error writing build report: {e}")
        
def is_standalone_eligible(records) -> bool:
    for r in records:
        text_clean = r.menu_text.replace(" ", "").strip()
        if text_clean and text_clean != "운영안함":
            return True
    return False

def build_daily_menu_docs(records, project_root: Optional[Path] = None, meta_map: Optional[dict] = None) -> list[dict]:
    daily_groups = defaultdict(list)
    for record in records:
        if record.cafeteria == "제1학생회관" or record.cafeteria not in CAFETERIA_ORDER:
            continue
        if is_closed_record(record):
            continue
        daily_groups[record.date].append(record)

    docs = []
    for date in sorted(daily_groups):
        date_records = daily_groups[date]
        weekday = weekday_ko(date)
        title = f"{date} ({weekday}) 학생식당 식단"
        text = format_dining_day(date_records, date)
        active_cafeterias = active_dining_cafeterias(date_records, date)

        source_paths = sorted({r.source_path for r in date_records if r.source_path})
        source_urls = sorted({r.source_url for r in date_records if r.source_url})
        fetched_ats = sorted({r.fetched_at for r in date_records if r.fetched_at})
        rel_source_paths = [relative_source_path(p, project_root) for p in source_paths]

        doc = {
            "id": f"dining_{date}",
            "domain": "dining",
            "title": title,
            "text": text,
            "source_url": source_urls[0] if source_urls else DEFAULT_DINING_URL,
            "source_name": SOURCE_NAME,
            "source_path": rel_source_paths[0] if rel_source_paths else None,
            "fetched_at": fetched_ats[0] if fetched_ats else None,
            "derived_from": derive_source_ids(source_paths, project_root, meta_map or {}),
            "generation_method": "daily_structured_aggregate",
            "metadata": {
                "date": date,
                "domain": "dining",
                "cafeterias": active_cafeterias,
                "record_count": len(date_records),
                "source_count": len(source_paths),
            },
        }
        docs.append(doc)

    return docs

def weekday_ko(date: str) -> str:
    return ["월", "화", "수", "목", "금", "토", "일"][datetime.strptime(date, "%Y-%m-%d").weekday()]

def build_operating_info_doc(records) -> dict:
    schedule = derive_operating_schedule(records)
    lines = [
        "# 학생식당 운영 안내",
        "",
        "## 학생식당 주중 운영표",
        "raw 식단 데이터에서 실제 제공 메뉴가 확인된 끼니와 대상을 집계했습니다.",
        "",
        "| 식당 | 아침 | 점심 | 저녁 |",
        "| --- | --- | --- | --- |",
    ]

    for cafeteria in CAFETERIA_ORDER:
        cafeteria_schedule = schedule.get(cafeteria, {})
        cells = []
        for meal in ["아침", "점심", "저녁"]:
            audiences = cafeteria_schedule.get(meal, [])
            cells.append(", ".join(audiences) if audiences else "-")
        lines.append(f"| {cafeteria} | {cells[0]} | {cells[1]} | {cells[2]} |")

    lines.extend(["", "## 주말 운영 여부", weekend_operating_text(records), "", "## 제1학생회관 푸드코트 개요"])
    lines.extend(food_court_overview_lines())

    return {
        "id": "dining_operating_info",
        "domain": "dining",
        "title": "학생식당 운영 안내",
        "text": "\n".join(lines).strip(),
        "source_url": DEFAULT_DINING_URL,
        "source_name": SOURCE_NAME,
        "metadata": {
            "domain": "dining",
            "document_type": "operating_info",
            "derived_from": "dining_menu_records",
        },
    }

def derive_operating_schedule(records) -> dict[str, dict[str, list[str]]]:
    schedule = defaultdict(lambda: defaultdict(set))
    for record in records:
        if record.cafeteria == "제1학생회관" or record.cafeteria not in CAFETERIA_ORDER:
            continue
        if is_closed_record(record) or not is_weekday(record.date):
            continue
        meal = MEAL_LABELS.get(record.meal, record.meal)
        schedule[record.cafeteria][meal].add(record.audience)

    result = {}
    for cafeteria in CAFETERIA_ORDER:
        result[cafeteria] = {}
        for meal in ["아침", "점심", "저녁"]:
            audiences = sorted(schedule[cafeteria].get(meal, set()), key=lambda a: AUDIENCE_ORDER.get(a, 99))
            result[cafeteria][meal] = audiences
    return result

def is_weekday(date_text: str) -> bool:
    return datetime.strptime(date_text, "%Y-%m-%d").weekday() < 5

def weekend_operating_text(records) -> str:
    return "주말·공휴일 미운영"

def is_food_court_main_menu(name: str) -> bool:
    compact_name = name.replace(" ", "")
    if compact_name in FOOD_COURT_SIDE_ITEM_EXACT:
        return False
    if "토핑" in compact_name:
        return False
    if compact_name.startswith("컵"):
        return False
    return True

def food_court_price_range(corner: dict) -> str:
    prices = [price for name, price in corner["items"] if is_food_court_main_menu(name)]
    if not prices:
        return corner["price_range"]
    return f"{min(prices):,}~{max(prices):,}원"

def food_court_overview_lines() -> list[str]:
    lines = [
        "| 코너 | 운영시간 | 가격대 |",
        "| --- | --- | --- |",
    ]
    for corner in FOOD_COURT_CORNERS:
        lines.append(f"| {corner['corner']} | {corner['hours']} | {food_court_price_range(corner)} |")
    lines.append("")
    lines.append("공통: 주말 미운영.")
    return lines

def build_food_court_docs() -> list[dict]:
    docs = []
    for corner in FOOD_COURT_CORNERS:
        corner_name = corner["corner"]
        safe_corner = re.sub(r"[^0-9A-Za-z가-힣&()]", "", corner_name)
        lines = [
            f"# 제1학생회관 푸드코트 {corner_name}",
            "",
            f"운영시간: {corner['hours']}",
            f"가격대: {food_court_price_range(corner)}",
            f"운영 참고: {corner['notes']}",
            "",
            "## 메뉴",
        ]
        for name, price in corner["items"]:
            lines.append(f"- {name}: {format_price(price)}")
        lines.extend(["", "## 원산지", corner["origins"]])
        docs.append({
            "id": f"dining_food_court_제1학생회관_{safe_corner}",
            "domain": "dining",
            "title": f"제1학생회관 푸드코트 {corner_name}",
            "text": "\n".join(lines).strip(),
            "source_url": DEFAULT_DINING_URL,
            "source_name": FOOD_COURT_SOURCE_NAME,
            "metadata": {
                "domain": "dining",
                "document_type": "food_court_corner",
                "cafeteria": "제1학생회관",
                "corner": corner_name,
            },
        })
    return docs

def relative_source_path(path: str, project_root: Optional[Path]) -> str:
    if not project_root:
        return path
    try:
        return Path(path).relative_to(project_root).as_posix()
    except ValueError:
        return path

def derive_source_ids(source_paths: list[str], project_root: Optional[Path], meta_map: dict) -> list[str]:
    derived_from = []
    for path in source_paths:
        rel_path = relative_source_path(path, project_root).lower()
        if rel_path in meta_map and meta_map[rel_path].get("source_id"):
            derived_from.append(meta_map[rel_path]["source_id"])
    return sorted(set(derived_from))

def record_to_json(record: MenuRecord, project_root: Optional[Path] = None) -> dict:
    return {
        "date": record.date,
        "cafeteria": record.cafeteria,
        "meal": record.meal,
        "audience": record.audience,
        "menu_text": record.menu_text,
        "menu_name": record.menu_name,
        "price": record.price,
        "source_path": relative_source_path(record.source_path, project_root) if record.source_path else None,
        "source_url": record.source_url,
        "fetched_at": record.fetched_at,
    }

def record_from_json(data: dict, project_root: Optional[Path] = None) -> MenuRecord:
    source_path = data.get("source_path")
    if source_path and project_root and not Path(source_path).is_absolute():
        source_path = str(project_root / source_path)
    return MenuRecord(
        date=data["date"],
        cafeteria=data["cafeteria"],
        meal=data["meal"],
        audience=data["audience"],
        menu_text=data["menu_text"],
        menu_name=data.get("menu_name"),
        price=data.get("price"),
        source_path=source_path,
        source_url=data.get("source_url"),
        fetched_at=data.get("fetched_at"),
    )

def load_fallback_records(report_path: Path, index_path: Path, project_root: Path) -> tuple[list[MenuRecord], str]:
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if report.get("source_records"):
                return [record_from_json(row, project_root) for row in report["source_records"]], "previous_build_report_records"
        except Exception as exc:
            print(f"Warning: failed to load fallback report records: {exc}")

    if index_path.exists():
        records = load_records_from_legacy_index(index_path, project_root)
        if records:
            return records, "existing_processed_dining_index"

    return [], "none"

def load_records_from_legacy_index(index_path: Path, project_root: Path) -> list[MenuRecord]:
    records = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        metadata = row.get("metadata") or {}
        date = metadata.get("date")
        cafeteria = metadata.get("cafeteria")
        if not date or not cafeteria:
            continue
        records.extend(parse_legacy_chunk_records(row, date, cafeteria, project_root))
    return records

def parse_legacy_chunk_records(row: dict, date: str, cafeteria: str, project_root: Path) -> list[MenuRecord]:
    records = []
    current_meal = None
    current_audience = None
    current_lines = []

    def flush():
        if current_meal and current_audience and current_lines:
            source_path = row.get("source_path")
            if source_path and not Path(source_path).is_absolute():
                source_path_abs = str(project_root / source_path)
            else:
                source_path_abs = source_path
            records.append(MenuRecord(
                date=date,
                cafeteria=cafeteria,
                meal=current_meal,
                audience=current_audience,
                menu_text="\n".join(current_lines),
                source_path=source_path_abs,
                source_url=row.get("source_url"),
                fetched_at=row.get("fetched_at"),
            ))

    for raw_line in row.get("text", "").splitlines():
        line = raw_line.rstrip()
        if line.startswith("### "):
            flush()
            current_meal = line[4:].strip()
            current_audience = None
            current_lines = []
        elif line.startswith("- ") and current_meal:
            flush()
            payload = line[2:]
            if ":" not in payload:
                current_audience = None
                current_lines = []
                continue
            audience, first_line = payload.split(":", 1)
            current_audience = audience.strip()
            current_lines = [first_line.strip()]
        elif line.startswith("  ") and current_meal and current_audience:
            current_lines.append(line.strip())
    flush()
    return records

def build_markdown_body(records) -> str:
    meal_order = {"조식": 0, "중식": 1, "석식": 2}
    aud_order = {"직원": 0, "학생": 1}
    
    sorted_records = sorted(
        records, 
        key=lambda r: (meal_order.get(r.meal, 99), aud_order.get(r.audience, 99))
    )
    
    meal_groups = defaultdict(list)
    for r in sorted_records:
        meal_groups[r.meal].append(r)
        
    lines = []
    for meal in sorted(meal_groups.keys(), key=lambda m: meal_order.get(m, 99)):
        lines.append(f"### {meal}")
        for r in meal_groups[meal]:
            menu_lines = r.menu_text.split('\n')
            if len(menu_lines) == 1:
                lines.append(f"- {r.audience}: {r.menu_text}")
            else:
                first_line = menu_lines[0]
                rest_lines = "\n  ".join(menu_lines[1:])
                lines.append(f"- {r.audience}: {first_line}\n  {rest_lines}")
        lines.append("") # empty line after meal block
        
    return "\n".join(lines).strip()

if __name__ == "__main__":
    main()
