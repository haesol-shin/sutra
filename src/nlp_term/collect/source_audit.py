from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from nlp_term.collect.source_inventory import SourceSpec, iter_specs
from nlp_term.paths import PROJECT_ROOT, ensure_parent
from nlp_term.schemas import RawSource, SourceVerification
from nlp_term.validators import read_json


OfficialChainStatus = Literal["verified", "official_linked", "unverified"]
StageDecision = Literal["retain", "replace", "promote", "defer"]


class OfficialLinkEvidence(BaseModel):
    source_id: str
    linking_source_url: str
    linked_url: str
    evidence_text: str


class SourceAuditRow(BaseModel):
    source_id: str
    label: int
    domain: str
    url: str
    stage: str
    active: bool
    parser_type: str
    decision: StageDecision
    decision_reason: str
    official_chain_status: OfficialChainStatus
    official_chain_evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    raw_status_code: int | None = None
    raw_content_type: str | None = None
    raw_path: str | None = None
    raw_checksum: str | None = None
    raw_fetched_at: str | None = None
    raw_file_exists: bool = False
    parser_name: str | None = None
    parser_version: str | None = None


class SourceAuditReport(BaseModel):
    baseline_knowledge_docs: int
    stage0_active_count: int
    stage0_active_cap: int
    stage0_policy: str
    rows: list[SourceAuditRow]


def build_source_audit(
    *,
    source_probe_path: Path,
    official_link_evidence: list[OfficialLinkEvidence] | None = None,
    baseline_knowledge_docs: int = 53,
    stage0_active_cap: int = 10,
) -> SourceAuditReport:
    probe = _load_probe(source_probe_path)
    link_evidence_by_source = {
        item.source_id: item for item in official_link_evidence or []
    }
    specs = iter_specs(stage="all", active_only=False)
    rows = [
        _audit_spec(
            spec,
            probe=probe,
            link_evidence=link_evidence_by_source.get(spec.source_id),
        )
        for spec in specs
    ]
    stage0_active_count = sum(1 for row in rows if row.stage == "stage0" and row.active)
    return SourceAuditReport(
        baseline_knowledge_docs=baseline_knowledge_docs,
        stage0_active_count=stage0_active_count,
        stage0_active_cap=stage0_active_cap,
        stage0_policy=(
            "freeze current Stage 0; classify new sources as candidate until a "
            "promotion/replacement decision is reviewed"
        ),
        rows=rows,
    )


def write_source_audit_markdown(report: SourceAuditReport, path: Path) -> None:
    ensure_parent(path)
    lines = [
        "# Source Fetch Audit",
        "",
        f"- baseline knowledge docs: {report.baseline_knowledge_docs}",
        f"- stage0 active count: {report.stage0_active_count}",
        f"- stage0 active cap: {report.stage0_active_cap}",
        f"- policy: {report.stage0_policy}",
        "",
        "| Source | Stage | Active | Decision | Official status | Raw status | Warning |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        raw_status = str(row.raw_status_code) if row.raw_status_code is not None else "not fetched"
        warning = "; ".join(row.warnings) if row.warnings else ""
        lines.append(
            "| "
            f"`{row.source_id}` | {row.stage} | {str(row.active).lower()} | "
            f"{row.decision} | {row.official_chain_status} | {raw_status} | {warning} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _audit_spec(
    spec: SourceSpec,
    *,
    probe: dict[str, tuple[RawSource, SourceVerification]],
    link_evidence: OfficialLinkEvidence | None,
) -> SourceAuditRow:
    raw, verification = probe.get(spec.source_id, (None, None))
    evidence: list[str] = []
    warnings: list[str] = []
    parser_name = None
    parser_version = None
    if verification is not None:
        evidence.extend(verification.evidence)
        warnings.extend(verification.warnings)
        parser_name = verification.parser_name
        parser_version = verification.parser_version
    official_status = _official_chain_status(spec, verification, link_evidence)
    if link_evidence is not None:
        evidence.append(
            f"{link_evidence.linking_source_url} links to {link_evidence.linked_url}"
        )
    if official_status == "unverified":
        warnings.append("official-chain evidence is missing or insufficient")
    decision = _stage_decision(spec)
    decision_reason = _stage_decision_reason(spec, decision)
    raw_path = raw.raw_path if raw is not None else None
    raw_file_exists = bool(raw_path and (PROJECT_ROOT / raw_path).exists())
    return SourceAuditRow(
        source_id=spec.source_id,
        label=spec.label,
        domain=spec.domain,
        url=spec.url,
        stage=spec.stage,
        active=spec.active,
        parser_type=spec.parser_type,
        decision=decision,
        decision_reason=decision_reason,
        official_chain_status=official_status,
        official_chain_evidence=evidence,
        warnings=warnings,
        raw_status_code=raw.status_code if raw is not None else None,
        raw_content_type=raw.content_type if raw is not None else None,
        raw_path=raw_path,
        raw_checksum=raw.checksum if raw is not None else None,
        raw_fetched_at=raw.fetched_at if raw is not None else None,
        raw_file_exists=raw_file_exists,
        parser_name=parser_name,
        parser_version=parser_version,
    )


def _official_chain_status(
    spec: SourceSpec,
    verification: SourceVerification | None,
    link_evidence: OfficialLinkEvidence | None,
) -> OfficialChainStatus:
    if verification is not None and verification.official_chain_ok and _is_cnu_host(spec.url):
        return "verified"
    if link_evidence is not None and _is_cnu_host(link_evidence.linking_source_url):
        return "official_linked"
    return "unverified"


def _is_cnu_host(url: str) -> bool:
    hostname = urlparse(url).hostname or ""
    return hostname == "cnu.ac.kr" or hostname.endswith(".cnu.ac.kr")


def _stage_decision(spec: SourceSpec) -> StageDecision:
    if spec.stage == "stage0" and spec.active:
        return "retain"
    return "defer"


def _stage_decision_reason(spec: SourceSpec, decision: StageDecision) -> str:
    if decision == "retain":
        return "current Stage 0 source is frozen for Work Unit A audit"
    return f"{spec.stage} candidate remains inactive until a reviewed promotion/replacement decision"


def _load_probe(path: Path) -> dict[str, tuple[RawSource, SourceVerification]]:
    if not path.exists():
        return {}
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    probe: dict[str, tuple[RawSource, SourceVerification]] = {}
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError(f"{path} rows must be objects")
        raw = RawSource.model_validate(row.get("raw"))
        verification = SourceVerification.model_validate(row.get("verification"))
        probe[raw.source_id] = (raw, verification)
    return probe


def main() -> None:
    parser = argparse.ArgumentParser(description="Write source fetch and official-chain audit artifacts.")
    parser.add_argument("--source-probe", type=Path, default=Path("data/sources/source_probe.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/evidence/source-fetch-audit-2026-06-08.json"))
    parser.add_argument("--markdown", type=Path, default=Path("docs/source_fetch_audit_2026_06_08.md"))
    args = parser.parse_args()
    report = build_source_audit(
        source_probe_path=args.source_probe,
        official_link_evidence=[
            OfficialLinkEvidence(
                source_id="cnu_mobile_food",
                linking_source_url="https://plus.cnu.ac.kr/html/kr/sub05/sub05_050401.html",
                linked_url="https://mobileadmin.cnu.ac.kr/food/index.jsp",
                evidence_text="CNU welfare page links to 금주의식단 on mobileadmin.cnu.ac.kr",
            )
        ],
    )
    ensure_parent(args.output)
    args.output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    write_source_audit_markdown(report, args.markdown)
    print(f"wrote {args.output}")
    print(f"wrote {args.markdown}")


if __name__ == "__main__":
    main()
