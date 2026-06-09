from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import fitz
from pydantic import BaseModel, Field

from sutra.errors import ExtractionError

OCR_TEXT_MIN_CHARS = 50

_PDFPLUMBER_AVAILABLE: bool | None = None


def _is_pdfplumber_available() -> bool:
    global _PDFPLUMBER_AVAILABLE
    if _PDFPLUMBER_AVAILABLE is None:
        try:
            import pdfplumber  # noqa: F401
            _PDFPLUMBER_AVAILABLE = True
        except ImportError:
            _PDFPLUMBER_AVAILABLE = False
    return _PDFPLUMBER_AVAILABLE


class PdfTable(BaseModel):
    page_no: int
    table_index: int
    rows: list[list[str]]


class PdfWarning(BaseModel):
    code: str
    message: str
    page_no: int | None = None


class PdfPage(BaseModel):
    page_no: int
    text: str
    tables: list[PdfTable] = Field(default_factory=list)
    image_count: int = 0
    needs_ocr: bool = False


class PdfExtraction(BaseModel):
    path: str
    source_id: str
    page_count: int
    pages: list[PdfPage]
    sha256: str
    warnings: list[PdfWarning] = Field(default_factory=list)


def extract_pdf(path: str | Path, *, source_id: str | None = None) -> PdfExtraction:
    path_obj = Path(path)
    if not path_obj.exists():
        raise ExtractionError(f"PDF file not found: {path_obj}")

    try:
        raw_bytes = path_obj.read_bytes()
    except (OSError, PermissionError) as e:
        raise ExtractionError(f"Cannot read PDF file: {e}") from e

    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    if source_id is None:
        source_id = path_obj.stem

    try:
        doc = fitz.open(str(path_obj))
    except Exception as e:
        raise ExtractionError(f"Cannot open PDF (corrupt or invalid): {e}") from e

    page_count = doc.page_count

    pdfplumber_available = _is_pdfplumber_available()
    pdfplumber_doc: Any = None
    if pdfplumber_available:
        try:
            import pdfplumber
            pdfplumber_doc = pdfplumber.open(str(path_obj))
        except Exception:
            pdfplumber_available = False

    pages: list[PdfPage] = []
    warnings: list[PdfWarning] = []

    if not pdfplumber_available:
        warnings.append(PdfWarning(
            code="pdfplumber_unavailable",
            message="pdfplumber not available or could not open PDF; table extraction disabled",
            page_no=None,
        ))

    try:
        for page_no in range(page_count):
            page = doc[page_no]
            page_no_1 = page_no + 1

            text = ""
            image_count = 0
            needs_ocr = False
            tables: list[PdfTable] = []

            try:
                text = page.get_text()
                images = page.get_images(full=True)
                image_count = len(images)

                text_stripped = text.strip()
                needs_ocr = len(text_stripped) < OCR_TEXT_MIN_CHARS and image_count > 0

                if pdfplumber_doc is not None:
                    plumber_page = pdfplumber_doc.pages[page_no]
                    for ti, table in enumerate(plumber_page.extract_tables()):
                        rows = [[cell or "" for cell in row] for row in table]
                        tables.append(PdfTable(
                            page_no=page_no_1, table_index=ti, rows=rows
                        ))

                if needs_ocr:
                    warnings.append(PdfWarning(
                        code="ocr_needed",
                        message=(
                            f"Page {page_no_1}: only {len(text_stripped)} chars"
                            f" with {image_count} images, may need OCR"
                        ),
                        page_no=page_no_1,
                    ))
            except Exception as e:
                warnings.append(PdfWarning(
                    code="page_extraction_failed",
                    message=f"Page {page_no_1}: {e}",
                    page_no=page_no_1,
                ))

            pages.append(PdfPage(
                page_no=page_no_1,
                text=text,
                tables=tables,
                image_count=image_count,
                needs_ocr=needs_ocr,
            ))
    finally:
        doc.close()
        if pdfplumber_doc is not None:
            pdfplumber_doc.close()

    return PdfExtraction(
        path=str(path_obj),
        source_id=source_id,
        page_count=page_count,
        pages=pages,
        sha256=sha256,
        warnings=warnings,
    )
