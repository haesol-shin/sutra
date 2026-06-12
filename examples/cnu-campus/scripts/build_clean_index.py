import json
import re
from datetime import date, timedelta
from pathlib import Path

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUTPUT_NAME = "knowledge-index.jsonl"
# dining-index.jsonl is included for STABLE reference docs only (operating_info,
# food_court_corner): hours, food-court menus and prices are date-invariant and
# belong in RAG. Volatile daily-menu docs stay tool-only (fetch_cafeteria_menu is
# the canonical source); they are dropped by _dining_stable_ok below.
DOMAIN_INDEXES = ["shuttle-index.jsonl", "calendar-index.jsonl", "graduation-index.jsonl", "graduation-general-index.jsonl", "notices-index.jsonl", "dining-index.jsonl"]
SUPPORTED_FIELDS = {"id", "text", "title", "source_url", "source_name", "metadata"}
# Academic-calendar month docs exist for many years with near-identical recurring
# events (수강신청/개강 등). Undated "언제" questions have no year signal, so stale past
# years tie with the current year in BM25. Keep only the current academic year onward
# to remove the temporal-duplication noise at the source.
CALENDAR_MIN_YEAR = 2026


def _calendar_year_ok(obj: dict) -> bool:
    """Drop academic-calendar month docs older than CALENDAR_MIN_YEAR."""
    metadata = obj.get("metadata") or {}
    if metadata.get("domain") != "academic_calendar":
        return True
    year = metadata.get("year")
    if not isinstance(year, int):
        return True
    return year >= CALENDAR_MIN_YEAR


DINING_STABLE_TYPES = {"operating_info", "food_court_corner"}


def _dining_stable_ok(obj: dict) -> bool:
    """Keep only stable dining reference docs; drop volatile daily menus.

    Allowlist on metadata.document_type: only operating_info and
    food_court_corner enter the corpus. Daily-menu docs have no document_type
    and are excluded by construction (fail-closed), staying tool-only.
    """
    metadata = obj.get("metadata") or {}
    if metadata.get("domain") != "dining":
        return True
    return metadata.get("document_type") in DINING_STABLE_TYPES


# Source academic calendars list 방학(vacation) start but no explicit 종강(end of
# semester). The semester ends the last weekday before vacation, so derive it
# deterministically so the model reads the date instead of guessing (it confused
# 종강 with the 계절학기 종료/성적발표 dates).
_VACATION_TO_SEMESTER = {"하기방학": "제1학기", "동기방학": "제2학기"}
_VACATION_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2}):\s*(하기방학|동기방학)")


def _jonggang_additions(obj: dict) -> list[str]:
    """Derived 종강 line(s) for a calendar month doc, last weekday before 방학."""
    metadata = obj.get("metadata") or {}
    if metadata.get("domain") != "academic_calendar":
        return []
    text = obj.get("text", "")
    additions: list[str] = []
    for match in _VACATION_RE.finditer(text):
        year, month, day, vacation = (
            int(match.group(1)), int(match.group(2)), int(match.group(3)), match.group(4),
        )
        semester = _VACATION_TO_SEMESTER[vacation]
        jonggang = date(year, month, day) - timedelta(days=1)
        while jonggang.weekday() >= 5:  # roll back Sat/Sun to Friday
            jonggang -= timedelta(days=1)
        line = f"- {jonggang.isoformat()}: {semester} 종강({vacation} 직전, 추정)"
        if line not in text and line not in additions:
            additions.append(line)
    return additions


def validate_line(line: str) -> bool:
    try:
        obj = json.loads(line)
        if not isinstance(obj, dict):
            return False
        if "id" not in obj or "text" not in obj:
            return False
        if not obj.get("id") or not obj.get("text"):
            return False
        if obj.get("metadata") is not None and not isinstance(obj["metadata"], dict):
            return False
        return True
    except (json.JSONDecodeError, ValueError):
        return False

def main():
    domain_paths = []
    for name in DOMAIN_INDEXES:
        p = PROCESSED_DIR / name
        if p.exists() and p.stat().st_size > 0:
            domain_paths.append(p)
        else:
            print(f"Warning: {name} not found or empty, skipping")
    if not domain_paths:
        print("Error: no valid domain indexes found")
        return
    output_path = PROCESSED_DIR / OUTPUT_NAME
    total_lines = 0
    valid_lines = 0
    failed_lines = 0
    trimmed_lines = 0
    dining_skipped = 0
    jonggang_added = 0
    with open(output_path, "w", encoding="utf-8") as out:
        for dp in domain_paths:
            with open(dp, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    total_lines += 1
                    if not validate_line(line):
                        failed_lines += 1
                        continue
                    obj = json.loads(line)
                    if not _calendar_year_ok(obj):
                        trimmed_lines += 1
                        continue
                    if not _dining_stable_ok(obj):
                        dining_skipped += 1
                        continue
                    additions = _jonggang_additions(obj)
                    if additions:
                        obj["text"] = obj["text"].rstrip() + "\n" + "\n".join(additions)
                        out.write(json.dumps(obj, ensure_ascii=False) + "\n")
                        jonggang_added += len(additions)
                    else:
                        out.write(line + "\n")
                    valid_lines += 1
    print(f"Merged {valid_lines} valid lines from {len(domain_paths)} domain indexes into {output_path}")
    if failed_lines:
        print(f"  ({failed_lines} invalid lines skipped)")
    if trimmed_lines:
        print(f"  ({trimmed_lines} calendar lines older than {CALENDAR_MIN_YEAR} trimmed)")
    if dining_skipped:
        print(f"  ({dining_skipped} volatile dining daily-menu lines dropped, tool-only)")
    if jonggang_added:
        print(f"  ({jonggang_added} derived 종강 line(s) added to calendar months)")
    if valid_lines == 0:
        print("Warning: no valid lines found")

if __name__ == "__main__":
    main()
