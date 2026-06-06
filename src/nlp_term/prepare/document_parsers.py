from __future__ import annotations

from pathlib import Path
import re
import zipfile
from xml.etree import ElementTree

import fitz
import olefile

from nlp_term.prepare.normalize import normalize_whitespace


def pdf_to_text(path: Path) -> str:
    with fitz.open(path) as document:
        parts = [page.get_text("text") for page in document]
    return normalize_whitespace(" ".join(parts))


def hwpx_to_text(path: Path) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if not name.lower().endswith(".xml"):
                continue
            with archive.open(name) as file:
                try:
                    root = ElementTree.parse(file).getroot()
                except ElementTree.ParseError:
                    continue
            for element in root.iter():
                if element.text:
                    parts.append(element.text)
    return normalize_whitespace(" ".join(parts))


def hwp_to_text(path: Path) -> str:
    if not olefile.isOleFile(path):
        raise ValueError(f"{path} is not an OLE HWP file")
    with olefile.OleFileIO(path) as document:
        body_streams = sorted(name for name in document.listdir() if name[:1] == ["BodyText"])
        chunks: list[str] = []
        for stream_name in body_streams:
            data = document.openstream(stream_name).read()
            chunks.append(_decode_hwp_bytes(data))
    return normalize_whitespace(" ".join(chunks))


def document_to_text(path: Path, *, content_type: str = "") -> str:
    suffix = path.suffix.lower()
    lowered_type = content_type.lower()
    if suffix == ".pdf" or "pdf" in lowered_type:
        return pdf_to_text(path)
    if suffix == ".hwpx" or "hwpx" in lowered_type:
        return hwpx_to_text(path)
    if suffix == ".hwp" or "hwp" in lowered_type:
        return hwp_to_text(path)
    raise ValueError(f"unsupported document type: {path} ({content_type})")


def _decode_hwp_bytes(data: bytes) -> str:
    candidates = [
        data.decode("utf-16-le", errors="ignore"),
        data.decode("cp949", errors="ignore"),
        data.decode("utf-8", errors="ignore"),
    ]
    return max(candidates, key=_hangul_score)


def _hangul_score(text: str) -> int:
    return len(re.findall(r"[가-힣]", text))
