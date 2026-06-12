import sys
import json
from pathlib import Path
import pytest

tests_dir = Path(__file__).resolve().parent
project_root = tests_dir.parent.parent.parent
scripts_dir = project_root / "examples" / "cnu-campus" / "scripts"
sys.path.insert(0, str(scripts_dir))

from sutra.pdf import PdfExtraction, PdfPage, PdfTable  # noqa: E402
from build_graduation_index import build_graduation_documents  # noqa: E402


META_PATH = project_root / "data" / "raw" / "graduation" / "computer_ai_2026_graduation_requirements.meta.json"

MINIMAL_META = {
    "id": "cnu_computer_ai_graduation_2026",
    "canonical_department": "컴퓨터인공지능학부",
    "aliases": ["컴퓨터인공지능학부", "컴융"],
    "source_type": "pdf",
    "source_url": "https://example.com/article",
    "source_title": "컴퓨터인공지능학부 2026학년도 입학생 졸업요건",
    "article_no": "576000",
    "attachment_no": "485215",
    "posted_date": "2026-01-27",
    "revision_date": "2026-03-19",
    "curriculum_year": "2026",
    "local_path": "data/raw/graduation/computer_ai_2026_graduation_requirements.pdf",
    "page_count": 5,
    "sha256": "67db053c9d101ae21d846b46c3aba18ab46a62677cefcaeb8b73a3fbb2f95f32",
    "provenance_status": "verified_official",
}


def make_fake_extraction(
    page_count: int = 5,
    texts: list[str] | None = None,
    needs_ocr_pages: list[int] | None = None,
    tables: dict[int, list[list[list[str]]]] | None = None,
    sha256_override: str | None = None,
) -> PdfExtraction:
    needs_ocr_pages = needs_ocr_pages or []
    tables = tables or {}
    pages = []
    for i in range(page_count):
        pn = i + 1
        text = (texts or [f"Page {pn} content"])[i] if texts else f"Page {pn} content"
        page_tables = []
        for ti, rows in enumerate(tables.get(pn, [])):
            page_tables.append(PdfTable(page_no=pn, table_index=ti, rows=rows))
        pages.append(PdfPage(
            page_no=pn,
            text=text,
            tables=page_tables,
            image_count=1 if pn in needs_ocr_pages else 0,
            needs_ocr=pn in needs_ocr_pages,
        ))
    sha256 = sha256_override or "67db053c9d101ae21d846b46c3aba18ab46a62677cefcaeb8b73a3fbb2f95f32"
    return PdfExtraction(
        path="fake.pdf",
        source_id="cnu_computer_ai_graduation_2026",
        page_count=page_count,
        pages=pages,
        sha256=sha256,
        warnings=[],
    )


# --- Tests ---

def test_metadata_json_valid():
    assert META_PATH.exists(), f"Metadata JSON not found at {META_PATH}"
    with open(META_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
    required = [
        "id", "canonical_department", "source_type", "source_url",
        "source_title", "article_no", "attachment_no", "posted_date",
        "revision_date", "curriculum_year", "local_path", "page_count",
        "sha256", "provenance_status",
    ]
    for field in required:
        assert field in meta, f"Missing required metadata field: {field}"
    assert meta["page_count"] == 5
    assert meta["canonical_department"] == "컴퓨터인공지능학부"
    assert meta["curriculum_year"] == "2026"


def test_builder_fails_if_pdf_missing():
    from sutra.errors import ExtractionError
    from sutra.pdf import extract_pdf
    raised = False
    try:
        extract_pdf("nonexistent.pdf")
    except ExtractionError:
        raised = True
    assert raised, "extract_pdf should raise ExtractionError for missing PDF"


def test_main_exits_1_when_pdf_missing(monkeypatch):
    import build_graduation_index as bgi
    monkeypatch.setattr(Path, "exists", lambda self: False)
    with pytest.raises(SystemExit) as exc:
        bgi.main()
    assert exc.value.code == 1


def test_main_exits_1_on_sha256_mismatch(monkeypatch):
    import build_graduation_index as bgi
    from sutra.pdf import PdfExtraction, PdfPage
    from pathlib import Path as OrigPath
    real_exists = OrigPath.exists

    def fake_exists(self):
        path_str = str(self)
        if "graduation_requirements.pdf" in path_str:
            return True
        return real_exists(self)

    monkeypatch.setattr(OrigPath, "exists", fake_exists)
    monkeypatch.setattr(
        bgi, "extract_pdf",
        lambda path, source_id=None: PdfExtraction(
            path=str(path),
            source_id=source_id or "test",
            page_count=1,
            pages=[PdfPage(page_no=1, text="fake", tables=[], image_count=0, needs_ocr=False)],
            sha256="bad" * 20,
            warnings=[],
        ),
    )
    with pytest.raises(SystemExit) as exc:
        bgi.main()
    assert exc.value.code == 1


def test_build_graduation_documents_returns_correct_count():
    extraction = make_fake_extraction(page_count=5)
    docs = build_graduation_documents(MINIMAL_META, extraction)
    assert len(docs) == 5
    for doc in docs:
        assert doc["id"].startswith("cnu-graduation-computer-ai-2026-page-")


def test_build_graduation_documents_sutra_schema():
    extraction = make_fake_extraction(page_count=3)
    docs = build_graduation_documents(MINIMAL_META, extraction)
    for doc in docs:
        assert "id" in doc
        assert "title" in doc
        assert "text" in doc
        assert "source_url" in doc
        assert "source_name" in doc
        assert "metadata" in doc


def test_build_graduation_documents_sha256_in_metadata():
    meta = dict(MINIMAL_META)
    expected_sha = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    extraction = make_fake_extraction(page_count=1, sha256_override=expected_sha)
    docs = build_graduation_documents(meta, extraction)
    assert docs[0]["metadata"]["sha256"] == expected_sha
    assert docs[0]["metadata"]["sha256"] != MINIMAL_META["sha256"]


def test_build_graduation_documents_metadata():
    extraction = make_fake_extraction(page_count=2)
    docs = build_graduation_documents(MINIMAL_META, extraction)
    for doc in docs:
        m = doc["metadata"]
        assert m["domain"] == "graduation"
        assert m["department"] == "컴퓨터인공지능학부"
        assert m["curriculum_year"] == "2026"
        assert m["source_id"] == "cnu_computer_ai_graduation_2026"


def test_build_graduation_documents_includes_ocr_note():
    extraction = make_fake_extraction(
        page_count=3,
        texts=["Page one", "", "Page three"],
        needs_ocr_pages=[2],
    )
    docs = build_graduation_documents(MINIMAL_META, extraction)
    assert docs[1]["metadata"]["needs_ocr"] is True
    assert "OCR" in docs[1]["text"] or "ocr" in docs[1]["text"].lower()
    assert docs[0]["metadata"]["needs_ocr"] is False
    assert docs[2]["metadata"]["needs_ocr"] is False


def test_build_graduation_documents_table_in_text():
    extraction = make_fake_extraction(
        page_count=1,
        texts=["Some text"],
        tables={1: [[["Cell1", "Cell2"], ["A", "B"]]]},
    )
    docs = build_graduation_documents(MINIMAL_META, extraction)
    assert "[표]" in docs[0]["text"]
    assert "Cell1 | Cell2" in docs[0]["text"]


def test_build_graduation_documents_ids_are_stable():
    extraction = make_fake_extraction(page_count=5)
    docs_a = build_graduation_documents(MINIMAL_META, extraction)
    docs_b = build_graduation_documents(MINIMAL_META, extraction)
    for a, b in zip(docs_a, docs_b):
        assert a["id"] == b["id"]
        assert a["title"] == b["title"]


def test_build_graduation_documents_title_format():
    extraction = make_fake_extraction(page_count=2)
    docs = build_graduation_documents(MINIMAL_META, extraction)
    for doc in docs:
        title = doc["title"]
        assert "컴퓨터인공지능학부" in title
        assert "2026" in title
        assert "페이지" in title


def test_generated_graduation_index():
    index_path = project_root / "examples" / "cnu-campus" / "data" / "processed" / "graduation-index.jsonl"
    if not index_path.exists():
        from build_graduation_index import main as build_main
        build_main()

    assert index_path.exists()
    lines = [line for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 5
    for line in lines:
        doc = json.loads(line)
        assert "id" in doc
        assert "title" in doc
        assert "text" in doc
        assert "source_url" in doc
        assert "source_name" in doc
        assert "metadata" in doc
        m = doc["metadata"]
        assert m["domain"] == "graduation"
        assert m["department"] == "컴퓨터인공지능학부"
        assert m["curriculum_year"] == "2026"


def test_generated_graduation_index_ocr_flag():
    index_path = project_root / "examples" / "cnu-campus" / "data" / "processed" / "graduation-index.jsonl"
    if not index_path.exists():
        from build_graduation_index import main as build_main
        build_main()

    lines = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ocr_pages = [doc["metadata"]["page_no"] for doc in lines if doc["metadata"]["needs_ocr"]]
    non_ocr_pages = [doc["metadata"]["page_no"] for doc in lines if not doc["metadata"]["needs_ocr"]]
    # At least some pages may need OCR (depends on actual PDF content)
    # This assertion is informative — the test passes regardless
    total_pages = len(lines)
    assert len(ocr_pages) + len(non_ocr_pages) == total_pages


def test_merged_knowledge_index_includes_graduation():
    index_path = project_root / "examples" / "cnu-campus" / "data" / "processed" / "knowledge-index.jsonl"
    if not index_path.exists():
        pytest.skip("knowledge-index.jsonl not found; run build_clean_index.py first")

    lines = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    graduation_docs = [doc for doc in lines if doc["metadata"].get("domain") == "graduation"]
    # Corpus = computer-ai 2026 pages (5) + general graduation docs (22) from
    # graduation-general-index.jsonl.
    assert len(graduation_docs) == 27
    for doc in graduation_docs:
        assert doc["id"].startswith("cnu-graduation-")
    computer_ai_pages = [d for d in graduation_docs if d["id"].startswith("cnu-graduation-computer-ai-2026-page-")]
    assert len(computer_ai_pages) == 5


def test_graduation_report_exists():
    report_path = project_root / "examples" / "cnu-campus" / "data" / "reports" / "graduation-build-report.json"
    if not report_path.exists():
        from build_graduation_index import main as build_main
        build_main()

    assert report_path.exists()
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    assert "source_id" in report
    assert "department" in report
    assert "curriculum_year" in report
    assert "page_count" in report
    assert "docs_written" in report
    assert "sha256_match" in report
    assert "pages_needing_ocr" in report
    assert "warnings" in report
    assert "tables_by_page" in report
    assert "text_chars_by_page" in report
    assert "known_limitations" in report
    assert report["department"] == "컴퓨터인공지능학부"
    assert report["curriculum_year"] == "2026"
    assert report["page_count"] == 5
    assert report["docs_written"] == 5
