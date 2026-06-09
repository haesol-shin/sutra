import json
import sys
from pathlib import Path

from sutra.pdf import extract_pdf, PdfExtraction


def build_graduation_documents(metadata: dict, extraction: PdfExtraction) -> list[dict]:
    docs = []
    source_id = metadata["id"]
    dept = metadata["canonical_department"]
    year = metadata["curriculum_year"]
    source_url = metadata["source_url"]
    source_title = metadata["source_title"]

    for page in extraction.pages:
        page_no = page.page_no
        doc_id = f"cnu-graduation-computer-ai-2026-page-{page_no:03d}"
        title = f"{dept} {year}학년도 졸업요건 - 페이지 {page_no}"

        text_parts = [
            f"출처: {source_title}",
            f"학과: {dept}",
            f"교육과정적용연도: {year}",
            f"페이지: {page_no}",
        ]

        if page.text.strip():
            text_parts.append("")
            text_parts.append(page.text.strip())

        for table in page.tables:
            text_parts.append("")
            text_parts.append("[표]")
            for row in table.rows:
                text_parts.append(" | ".join(row))

        if page.needs_ocr:
            text_parts.append("")
            text_parts.append("이 페이지는 이미지 기반 내용이 있어 OCR 후 보강이 필요합니다.")

        text = "\n".join(text_parts)

        doc = {
            "id": doc_id,
            "title": title,
            "text": text,
            "source_url": source_url,
            "source_name": source_title,
            "metadata": {
                "domain": "graduation",
                "department": dept,
                "aliases": metadata["aliases"],
                "curriculum_year": year,
                "source_type": metadata["source_type"],
                "source_id": source_id,
                "source_url": source_url,
                "source_title": source_title,
                "article_no": metadata["article_no"],
                "attachment_no": metadata["attachment_no"],
                "posted_date": metadata["posted_date"],
                "revision_date": metadata["revision_date"],
                "page_no": page_no,
                "page_count": extraction.page_count,
                "needs_ocr": page.needs_ocr,
                "sha256": extraction.sha256,
                "provenance_status": metadata["provenance_status"],
            },
        }
        docs.append(doc)

    return docs


def main():
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent

    meta_path = (
        project_root
        / "data"
        / "raw"
        / "graduation"
        / "computer_ai_2026_graduation_requirements.meta.json"
    )

    processed_dir = project_root / "examples" / "cnu-campus" / "data" / "processed"
    reports_dir = project_root / "examples" / "cnu-campus" / "data" / "reports"
    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    output_index_path = processed_dir / "graduation-index.jsonl"
    output_report_path = reports_dir / "graduation-build-report.json"

    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    pdf_path = project_root / metadata["local_path"]

    if not pdf_path.exists():
        print(f"Error: PDF not found at {pdf_path}")
        sys.exit(1)

    extraction = extract_pdf(str(pdf_path), source_id=metadata["id"])

    sha256_match = extraction.sha256 == metadata["sha256"]
    if not sha256_match:
        print(
            f"Error: SHA256 mismatch."
            f" Expected {metadata['sha256']}, got {extraction.sha256}"
        )
        sys.exit(1)

    docs = build_graduation_documents(metadata, extraction)

    with open(output_index_path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"Successfully wrote {len(docs)} docs to {output_index_path}")

    pages_needing_ocr = [p.page_no for p in extraction.pages if p.needs_ocr]
    tables_by_page = {}
    text_chars_by_page = {}
    for p in extraction.pages:
        tables_by_page[p.page_no] = len(p.tables)
        text_chars_by_page[p.page_no] = len(p.text)

    report = {
        "source_id": metadata["id"],
        "department": metadata["canonical_department"],
        "curriculum_year": metadata["curriculum_year"],
        "pdf_path": str(pdf_path.relative_to(project_root)),
        "page_count": extraction.page_count,
        "docs_written": len(docs),
        "sha256_match": sha256_match,
        "pages_needing_ocr": pages_needing_ocr,
        "warnings": [w.model_dump() for w in extraction.warnings],
        "tables_by_page": tables_by_page,
        "text_chars_by_page": text_chars_by_page,
        "known_limitations": [
            "pdfplumber not available; table extraction disabled.",
            "Page 3 is likely image/table-heavy and may require OCR or manual transcription.",
            "This first slice is page-level, not semantic credit parsing.",
        ],
    }

    with open(output_report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Successfully wrote build report to {output_report_path}")


if __name__ == "__main__":
    main()
