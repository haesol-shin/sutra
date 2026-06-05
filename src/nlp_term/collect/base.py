from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from nlp_term.schemas import RawSource, SourceVerification


PARSER_VERSION = "0.1.0"


def checksum_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


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
