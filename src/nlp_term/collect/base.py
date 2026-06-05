from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

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
    response = requests.get(url, timeout=timeout)
    relative_path = Path("data") / "raw" / domain / f"{source_id}.{raw_suffix}"
    raw_path = PROJECT_ROOT / relative_path
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(response.content)
    return RawSource(
        source_id=source_id,
        label=label,
        domain=domain,
        url=url,
        fetched_at=now_iso(),
        content_type=response.headers.get("content-type", "application/octet-stream"),
        raw_path=str(relative_path),
        status_code=response.status_code,
        checksum=checksum_bytes(response.content),
    )


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
