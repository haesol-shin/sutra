from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlparse

from nlp_term.chat.state_contract import AllowlistStatus, SourceStatus
from nlp_term.collect.source_inventory import SOURCE_SPECS, SourceSpec
from nlp_term.schemas import KnowledgeDoc


OFFICIAL_HOST_SUFFIXES = (".cnu.ac.kr",)


def build_source_status(
    doc: KnowledgeDoc,
    *,
    specs: Iterable[SourceSpec] | None = None,
) -> SourceStatus:
    registry = {spec.source_id: spec for spec in specs or SOURCE_SPECS}
    spec = registry.get(doc.source_id)
    metadata = doc.metadata

    return SourceStatus(
        source_id=doc.source_id,
        source_url=doc.source_url,
        registry_present=spec is not None,
        active=bool(spec.active) if spec else _metadata_bool(metadata.get("source_active")),
        official_chain_ok=_official_chain_ok(doc, spec),
        parser_type=spec.parser_type if spec else _metadata_str(metadata.get("source_parser_type")),
        freshness_policy=spec.freshness_policy if spec else _metadata_str(metadata.get("source_freshness_policy"), "snapshot"),
        raw_fetched_at=_first_str(
            metadata.get("raw_fetched_at"),
            metadata.get("fetched_at"),
            metadata.get("source_fetched_at"),
        ),
        allowlist_status=_allowlist_status(doc.source_url),
        metadata_department=_first_str(
            metadata.get("source_department"),
            metadata.get("department"),
            spec.department if spec else None,
        ),
        metadata_curriculum_year=_first_str(
            metadata.get("source_curriculum_year"),
            metadata.get("curriculum_year"),
            spec.curriculum_year if spec else None,
        ),
        metadata_domain=doc.domain,
    )


def _official_chain_ok(doc: KnowledgeDoc, spec: SourceSpec | None) -> bool:
    if spec is not None:
        return spec.official_chain_ok
    return _metadata_bool(doc.metadata.get("verification_official_chain_ok"))


def _allowlist_status(url: str) -> AllowlistStatus:
    host = urlparse(url).netloc.lower()
    if not host:
        return AllowlistStatus.UNKNOWN
    if host == "cnu.ac.kr" or any(host.endswith(suffix) for suffix in OFFICIAL_HOST_SUFFIXES):
        return AllowlistStatus.ALLOWED
    return AllowlistStatus.BLOCKED


def _first_str(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _metadata_str(value: object, default: str | None = None) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _metadata_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return False
