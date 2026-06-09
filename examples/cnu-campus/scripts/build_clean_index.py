import json
from pathlib import Path

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUTPUT_NAME = "knowledge-index.jsonl"
DOMAIN_INDEXES = ["dining-index.jsonl", "shuttle-index.jsonl", "calendar-index.jsonl", "graduation-index.jsonl"]
SUPPORTED_FIELDS = {"id", "text", "title", "source_url", "source_name", "metadata"}

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
    with open(output_path, "w", encoding="utf-8") as out:
        for dp in domain_paths:
            with open(dp, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    total_lines += 1
                    if validate_line(line):
                        out.write(line + "\n")
                        valid_lines += 1
                    else:
                        failed_lines += 1
    print(f"Merged {valid_lines} valid lines from {len(domain_paths)} domain indexes into {output_path}")
    if failed_lines:
        print(f"  ({failed_lines} invalid lines skipped)")
    if valid_lines == 0:
        print("Warning: no valid lines found")

if __name__ == "__main__":
    main()
