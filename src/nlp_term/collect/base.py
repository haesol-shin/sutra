from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import tempfile

import requests

from nlp_term.paths import PROJECT_ROOT
from nlp_term.schemas import RawSource, SourceVerification


PARSER_VERSION = "0.1.0"


def checksum_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def checksum_bytes(content: bytes) -> str:
    return sha256(content).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_stub_source(
    source_id: str,
    label: int,
    domain: str,
    url: str,
    *,
    content_type: str = "text/html",
    raw_suffix: str = "html",
) -> RawSource:
    return RawSource(
        source_id=source_id,
        label=label,
        domain=domain,
        url=url,
        fetched_at=now_iso(),
        content_type=content_type,
        raw_path=f"data/raw/{domain}/{source_id}.{raw_suffix}",
        status_code=None,
        checksum=checksum_text(url),
    )


def fetch_source(
    source_id: str,
    label: int,
    domain: str,
    url: str,
    *,
    raw_suffix: str = "html",
    timeout: float = 20.0,
) -> RawSource:
    try:
        if "plus.cnu.ac.kr" in url:
            raise requests.RequestException("use curl for plus.cnu.ac.kr")
        response = requests.get(url, timeout=timeout)
        content = response.content
        content_type = response.headers.get("content-type", "application/octet-stream")
        status_code = response.status_code
    except requests.RequestException:
        content, content_type, status_code = _fetch_with_curl(url, timeout=timeout)
    relative_path = Path("data") / "raw" / domain / f"{source_id}.{raw_suffix}"
    raw_path = PROJECT_ROOT / relative_path
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(content)
    return RawSource(
        source_id=source_id,
        label=label,
        domain=domain,
        url=url,
        fetched_at=now_iso(),
        content_type=content_type,
        raw_path=str(relative_path),
        status_code=status_code,
        checksum=checksum_bytes(content),
    )


def _fetch_with_curl(url: str, *, timeout: float) -> tuple[bytes, str, int]:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("requests failed and curl is not available")
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_path = Path(temp_file.name)
    temp_file.close()
    command = [
        curl,
        "-L",
        "--max-time",
        str(max(int(timeout), 1)),
        "-s",
        "-o",
        str(temp_path),
        "-w",
        "%{http_code}\n%{content_type}",
        url,
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        status_code, content_type = result.stdout.split("\n", 1)
        return temp_path.read_bytes(), content_type, int(status_code)
    finally:
        temp_path.unlink(missing_ok=True)


def verify_stub(raw: RawSource, parser_name: str, warning: str) -> SourceVerification:
    return SourceVerification(
        source_id=raw.source_id,
        official_chain_ok=False,
        parser_name=parser_name,
        parser_version=PARSER_VERSION,
        evidence=[raw.url],
        warnings=[warning],
        verified_at=now_iso(),
    )
