from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from nlp_term.collect.base import PARSER_VERSION, build_stub_source, fetch_source, now_iso
from nlp_term.schemas import Domain, RawSource, SourceVerification


Stage = Literal["stage0", "stage1", "stage2"]
ParserType = Literal["html", "board_detail", "pdf", "hwp", "hwpx", "calendar", "dining", "shuttle"]


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    label: int
    domain: Domain
    url: str
    parser_type: ParserType
    raw_suffix: str = "html"
    stage: Stage = "stage0"
    active: bool = True
    priority: int = 100
    official_chain_ok: bool = True
    freshness_policy: str = "snapshot"
    notes: str = ""
    department: str | None = None
    curriculum_year: str | None = None

    def metadata(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "stage": self.stage,
            "active": self.active,
            "parser_type": self.parser_type,
            "priority": self.priority,
            "freshness_policy": self.freshness_policy,
            "notes": self.notes,
        }
        if self.department:
            payload["department"] = self.department
        if self.curriculum_year:
            payload["curriculum_year"] = self.curriculum_year
        return payload


STAGE0_SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        source_id="graduation_curriculum_pdf",
        label=0,
        domain="graduation",
        url="https://plus.cnu.ac.kr/html/kr/25file/2025_book.pdf",
        parser_type="pdf",
        raw_suffix="pdf",
        notes="central curriculum PDF",
        curriculum_year="2025",
    ),
    SourceSpec(
        source_id="graduation_english_requirements",
        label=0,
        domain="graduation",
        url="https://english.cnu.ac.kr/english/edu/undergraduate02.do",
        parser_type="html",
        notes="English department graduation requirements",
        department="영어영문학과",
    ),
    SourceSpec(
        source_id="graduation_biochemistry_requirements",
        label=0,
        domain="graduation",
        url="https://biochemistry.cnu.ac.kr/biochemistry/info/requirements.do",
        parser_type="html",
        notes="Biochemistry department graduation requirements",
        department="생화학과",
    ),
    SourceSpec(
        source_id="academic_notice_board",
        label=1,
        domain="notices",
        url="https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr",
        parser_type="html",
        freshness_policy="latest_snapshot",
        notes="central academic notice board list",
    ),
    SourceSpec(
        source_id="academic_notice_detail_2512782",
        label=1,
        domain="notices",
        url=(
            "https://plus.cnu.ac.kr/_prog/_board/?mode=V&no=2512782&code=sub07_0702"
            "&site_dvs_cd=kr&menu_dvs_cd=0702"
        ),
        parser_type="board_detail",
        freshness_policy="latest_snapshot",
        notes="recent academic notice detail",
    ),
    SourceSpec(
        source_id="academic_notice_detail_2512124",
        label=1,
        domain="notices",
        url=(
            "https://plus.cnu.ac.kr/_prog/_board/?mode=V&no=2512124&code=sub07_0702"
            "&site_dvs_cd=kr&menu_dvs_cd=0702"
        ),
        parser_type="board_detail",
        freshness_policy="latest_snapshot",
        notes="recent academic notice detail",
    ),
    SourceSpec(
        source_id="academic_notice_detail_2511200",
        label=1,
        domain="notices",
        url=(
            "https://plus.cnu.ac.kr/_prog/_board/?mode=V&no=2511200&code=sub07_0702"
            "&site_dvs_cd=kr&menu_dvs_cd=0702"
        ),
        parser_type="board_detail",
        freshness_policy="latest_snapshot",
        notes="recent academic notice detail",
    ),
    SourceSpec(
        source_id="academic_calendar",
        label=2,
        domain="academic_calendar",
        url="https://plus.cnu.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&site_dvs_cd=kr",
        parser_type="calendar",
        notes="official academic calendar",
    ),
    SourceSpec(
        source_id="cnu_mobile_food",
        label=3,
        domain="dining",
        url="https://mobileadmin.cnu.ac.kr/food/index.jsp",
        parser_type="dining",
        freshness_policy="short_ttl",
        notes="current mobile dining menu snapshot",
    ),
    SourceSpec(
        source_id="shuttle_bus",
        label=4,
        domain="shuttle",
        url="https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html",
        parser_type="shuttle",
        freshness_policy="snapshot_with_term_check",
        notes="official shuttle timetable page",
    ),
)

SOURCE_SPECS: tuple[SourceSpec, ...] = STAGE0_SOURCES


def iter_specs(*, stage: Stage | Literal["all"] = "stage0", active_only: bool = True) -> list[SourceSpec]:
    specs = []
    for spec in SOURCE_SPECS:
        if stage != "all" and spec.stage != stage:
            continue
        if active_only and not spec.active:
            continue
        specs.append(spec)
    return sorted(specs, key=lambda item: (item.stage, item.priority, item.label, item.source_id))


def collect_spec(spec: SourceSpec, *, fetch: bool = False) -> RawSource:
    if fetch:
        return fetch_source(
            spec.source_id,
            spec.label,
            spec.domain,
            spec.url,
            raw_suffix=spec.raw_suffix,
        )
    content_type = "application/pdf" if spec.raw_suffix == "pdf" else "text/html"
    return build_stub_source(
        spec.source_id,
        spec.label,
        spec.domain,
        spec.url,
        content_type=content_type,
        raw_suffix=spec.raw_suffix,
    )


def verify_spec(spec: SourceSpec, raw: RawSource) -> SourceVerification:
    warnings = []
    if not spec.official_chain_ok:
        warnings.append("source is not official-chain verified")
    if spec.freshness_policy in {"short_ttl", "latest_snapshot"}:
        warnings.append(f"freshness policy: {spec.freshness_policy}")
    return SourceVerification(
        source_id=raw.source_id,
        official_chain_ok=spec.official_chain_ok,
        parser_name=f"{spec.parser_type}_stage_inventory",
        parser_version=PARSER_VERSION,
        evidence=[raw.url],
        warnings=warnings,
        verified_at=now_iso(),
    )
