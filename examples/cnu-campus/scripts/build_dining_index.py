import json
import re
from pathlib import Path
from collections import defaultdict
from typing import List, Optional
from cnu_dining import parse_dining_file

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
    else:
        print(f"Error: Raw dining directory not found at {raw_dining_dir}")
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
    
    # 5. Group by (date, cafeteria) for RAG Chunks
    chunk_groups = defaultdict(list)
    for record in unique_records:
        group_key = (record.date, record.cafeteria)
        chunk_groups[group_key].append(record)
        
    chunks = []
    for (date, cafeteria), records in chunk_groups.items():
        if not is_standalone_eligible(records):
            continue
            
        body = build_markdown_body(records)
        
        source_paths = sorted(list(set(r.source_path for r in records if r.source_path)))
        source_urls = sorted(list(set(r.source_url for r in records if r.source_url)))
        fetched_ats = sorted(list(set(r.fetched_at for r in records if r.fetched_at)))
        
        rel_source_paths = []
        for p in source_paths:
            try:
                rel_p = Path(p).relative_to(project_root).as_posix()
                rel_source_paths.append(rel_p)
            except ValueError:
                rel_source_paths.append(p)
                
        derived_from = []
        for p in source_paths:
            try:
                rel_p = Path(p).relative_to(project_root).as_posix().lower()
                if rel_p in meta_map and meta_map[rel_p].get("source_id"):
                    derived_from.append(meta_map[rel_p]["source_id"])
            except ValueError:
                pass
                
        cafeteria_clean = re.sub(r'[^a-zA-Z0-9가-힣]', '', cafeteria)
        chunk_id = f"dining_{date}_{cafeteria_clean}"
        
        chunk = {
            "id": chunk_id,
            "domain": "dining",
            "title": f"{date} {cafeteria} 식단",
            "text": body,
            "source_url": source_urls[0] if source_urls else "https://mobileadmin.cnu.ac.kr/food/index.jsp",
            "source_name": "충남대학교 생활협동조합 식단",
            "source_path": rel_source_paths[0] if rel_source_paths else None,
            "fetched_at": fetched_ats[0] if fetched_ats else None,
            "derived_from": derived_from,
            "generation_method": "structured_aggregate",
            "metadata": {
                "date": date,
                "cafeteria": cafeteria,
                "record_count": len(records),
                "source_count": len(source_paths)
            }
        }
        chunks.append(chunk)
        
    # Gather summary dates and cafeterias
    generated_dates = sorted(list(set(chunk["metadata"]["date"] for chunk in chunks)))
    generated_cafeterias = sorted(list(set(chunk["metadata"]["cafeteria"] for chunk in chunks)))
    
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
        "date_mismatches": date_mismatches,
        "missing_source_meta": missing_source_meta,
        "dates": generated_dates,
        "cafeterias": generated_cafeterias
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
