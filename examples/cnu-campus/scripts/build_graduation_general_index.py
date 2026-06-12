import json
from pathlib import Path

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
INPUT_NAME = "graduation-curated-source.json"
OUTPUT_NAME = "graduation-general-index.jsonl"


def main():
    input_path = PROCESSED_DIR / INPUT_NAME
    output_path = PROCESSED_DIR / OUTPUT_NAME

    with open(input_path, "r", encoding="utf-8") as f:
        source = json.load(f)

    default_provenance_status = source["default_provenance_status"]
    docs = source["docs"]

    with open(output_path, "w", encoding="utf-8") as out:
        for doc in docs:
            obj = {
                "id": doc["id"],
                "title": doc["title"],
                "text": doc["text"],
                "source_url": doc["source_url"],
                "source_name": doc["source_title"],
                "metadata": {
                    "domain": "graduation",
                    "department": doc["department"],
                    "aliases": doc["aliases"],
                    "section": doc["section"],
                    "source_type": doc["source_type"],
                    "source_id": doc["id"],
                    "source_url": doc["source_url"],
                    "source_title": doc["source_title"],
                    "provenance_status": doc.get("provenance_status", default_provenance_status),
                    "curated": True,
                },
            }
            out.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print(f"Wrote {len(docs)} docs to {output_path}")


if __name__ == "__main__":
    main()
