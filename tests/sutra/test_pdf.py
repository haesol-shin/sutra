from __future__ import annotations

from pathlib import Path

import fitz
import pytest

import sutra.pdf
from sutra.errors import ExtractionError
from sutra.pdf import extract_pdf


def _make_text_pdf(path: Path, texts: list[str]) -> None:
    doc = fitz.open()
    for text in texts:
        page = doc.new_page()
        page.insert_text(fitz.Point(50, 50), text, fontsize=12)
    doc.save(str(path))
    doc.close()


def _make_image_pdf(path: Path,
                    pages: list[dict]) -> None:
    doc = fitz.open()
    for spec in pages:
        page = doc.new_page()
        if text := spec.get("text", ""):
            page.insert_text(fitz.Point(10, 10), text, fontsize=11)
        if spec.get("image", False):
            pix = fitz.Pixmap(fitz.csGRAY, (0, 0, 30, 30))
            page.insert_image(fitz.Rect(50, 50, 80, 80), pixmap=pix)
    doc.save(str(path))
    doc.close()


class TestTextOnlyPDF:
    def test_two_pages(self, tmp_path: Path) -> None:
        path = tmp_path / "sample.pdf"
        _make_text_pdf(path, ["Hello PDF", "Page two"])

        result = extract_pdf(path)

        assert result.page_count == 2
        assert len(result.pages) == 2
        assert "Hello PDF" in result.pages[0].text
        assert "Page two" in result.pages[1].text
        assert not result.pages[0].needs_ocr
        assert result.pages[0].image_count == 0
        assert len(result.sha256) == 64
        assert result.source_id == "sample"

    def test_source_id_explicit(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.pdf"
        _make_text_pdf(path, ["Some text"])

        result = extract_pdf(path, source_id="my-doc")
        assert result.source_id == "my-doc"

    def test_source_id_auto_derived(self, tmp_path: Path) -> None:
        path = tmp_path / "my_report.pdf"
        _make_text_pdf(path, ["Report"])

        result = extract_pdf(path)
        assert result.source_id == "my_report"


class TestTableExtraction:
    def test_with_pdfplumber(self, tmp_path: Path) -> None:
        pytest.importorskip("pdfplumber")
        path = tmp_path / "table.pdf"
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        x_positions = [50, 150, 250]
        rows_data = [
            ["Name", "Age", "City"],
            ["Alice", "30", "Daejeon"],
            ["Bob", "25", "Seoul"],
        ]
        for ri, row in enumerate(rows_data):
            y = 60 + ri * 20
            for ci, cell in enumerate(row):
                page.insert_text(fitz.Point(x_positions[ci], y), cell,
                                 fontsize=10)
        doc.save(str(path))
        doc.close()

        result = extract_pdf(path)
        assert len(result.pages[0].tables) >= 1
        assert result.pages[0].tables[0].rows[0] == ["Name", "Age", "City"]

    def test_pdfplumber_unavailable(self, tmp_path: Path,
                                    monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sutra.pdf, "_is_pdfplumber_available",
                            lambda: False)
        path = tmp_path / "note.pdf"
        _make_text_pdf(path, ["No tables today"])

        result = extract_pdf(path)
        assert all(len(p.tables) == 0 for p in result.pages)
        assert any(w.code == "pdfplumber_unavailable" for w in result.warnings)


class TestImageAndOCR:
    def test_image_page_detects_ocr_needed(self, tmp_path: Path) -> None:
        path = tmp_path / "mixed.pdf"
        _make_image_pdf(path, [
            {"text": "This is page one with plenty of text for detection"},
            {"text": "Hi", "image": True},
        ])

        result = extract_pdf(path)
        assert not result.pages[0].needs_ocr
        assert result.pages[1].needs_ocr
        assert result.pages[1].image_count > 0
        assert any(w.code == "ocr_needed" and w.page_no == 2
                   for w in result.warnings)


class TestErrorHandling:
    def test_missing_path(self) -> None:
        with pytest.raises(ExtractionError, match="not found"):
            extract_pdf("nonexistent_file.pdf")

    def test_corrupt_pdf(self, tmp_path: Path) -> None:
        path = tmp_path / "corrupt.pdf"
        path.write_bytes(b"not a pdf\0")
        with pytest.raises(ExtractionError, match="corrupt|invalid|open"):
            extract_pdf(path)

    def test_page_extraction_failure(self, tmp_path: Path,
                                     monkeypatch: pytest.MonkeyPatch) -> None:
        path = tmp_path / "multi.pdf"
        _make_text_pdf(path, ["Page one works", "Page two breaks"])

        original_get_text = fitz.Page.get_text

        def failing_get_text(self, *args: object, **kwargs: object) -> str:
            if self.number == 1:
                raise RuntimeError("mock failure on page 2")
            return original_get_text(self, *args, **kwargs)

        monkeypatch.setattr(fitz.Page, "get_text", failing_get_text)

        result = extract_pdf(path)
        assert len(result.pages) == 2
        assert "Page one works" in result.pages[0].text
        assert result.pages[1].text == ""
        assert any(
            w.code == "page_extraction_failed" and w.page_no == 2
            for w in result.warnings
        )
