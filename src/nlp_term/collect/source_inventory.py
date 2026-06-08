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
    official_chain_ok: bool = False
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
        official_chain_ok=True,
        notes="central curriculum PDF",
        curriculum_year="2025",
    ),
    SourceSpec(
        source_id="graduation_english_requirements",
        label=0,
        domain="graduation",
        url="https://english.cnu.ac.kr/english/edu/undergraduate02.do",
        parser_type="html",
        official_chain_ok=True,
        notes="English department graduation requirements",
        department="영어영문학과",
    ),
    SourceSpec(
        source_id="graduation_biochemistry_requirements",
        label=0,
        domain="graduation",
        url="https://biochemistry.cnu.ac.kr/biochemistry/info/requirements.do",
        parser_type="html",
        official_chain_ok=True,
        notes="Biochemistry department graduation requirements",
        department="생화학과",
    ),
    SourceSpec(
        source_id="academic_notice_board",
        label=1,
        domain="notices",
        url="https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr",
        parser_type="html",
        official_chain_ok=True,
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
        official_chain_ok=True,
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
        official_chain_ok=True,
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
        official_chain_ok=True,
        freshness_policy="latest_snapshot",
        notes="recent academic notice detail",
    ),
    SourceSpec(
        source_id="academic_calendar",
        label=2,
        domain="academic_calendar",
        url="https://plus.cnu.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&site_dvs_cd=kr",
        parser_type="calendar",
        official_chain_ok=True,
        notes="official academic calendar",
    ),
    SourceSpec(
        source_id="cnu_mobile_food",
        label=3,
        domain="dining",
        url="https://mobileadmin.cnu.ac.kr/food/index.jsp",
        parser_type="dining",
        official_chain_ok=False,
        freshness_policy="short_ttl",
        notes="current mobile dining menu snapshot; needs explicit official-chain confirmation before current/latest claims",
    ),
    SourceSpec(
        source_id="shuttle_bus",
        label=4,
        domain="shuttle",
        url="https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html",
        parser_type="shuttle",
        official_chain_ok=True,
        freshness_policy="snapshot_with_term_check",
        notes="official shuttle timetable page",
    ),
)


def _curriculum_year_sources() -> tuple[SourceSpec, ...]:
    return tuple(
        SourceSpec(
            source_id=f"graduation_curriculum_{year}_pdf",
            label=0,
            domain="graduation",
            url=f"https://plus.cnu.ac.kr/html/kr/{year[-2:]}file/{year}_book.pdf",
            parser_type="pdf",
            raw_suffix="pdf",
            stage="stage1",
            active=True,
            priority=12 + index,
            official_chain_ok=True,
            notes=f"central curriculum PDF for {year}; HEAD verified 2026-06-08",
            curriculum_year=year,
        )
        for index, year in enumerate(("2023", "2024"))
    )


def _academic_calendar_year_sources() -> tuple[SourceSpec, ...]:
    return tuple(
        SourceSpec(
            source_id=f"academic_calendar_{year}",
            label=2,
            domain="academic_calendar",
            url=(
                "https://plus.cnu.ac.kr/_prog/academic_calendar/"
                f"?menu_dvs_cd=05020101&site_dvs_cd=kr&year={year}"
            ),
            parser_type="calendar",
            stage="stage1",
            active=True,
            priority=42 + index,
            official_chain_ok=True,
            notes=f"official academic calendar for {year}; HEAD and calen_box verified 2026-06-08",
            curriculum_year=year,
        )
        for index, year in enumerate(("2023", "2024", "2025"))
    )


def _academic_notice_page_sources() -> tuple[SourceSpec, ...]:
    return tuple(
        SourceSpec(
            source_id=f"academic_notice_board_page_{page}",
            label=1,
            domain="notices",
            url=(
                "https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702"
                f"&menu_dvs_cd=0702&site_dvs_cd=kr&GotoPage={page}"
            ),
            parser_type="html",
            stage="stage1",
            active=True,
            priority=70 + page,
            official_chain_ok=True,
            freshness_policy="latest_snapshot",
            notes=f"central academic notice board list page {page}; HEAD verified 2026-06-08",
        )
        for page in range(2, 7)
    )


def _june_dining_week_sources() -> tuple[SourceSpec, ...]:
    cafeterias = (
        ("1st", "OCL03.01", "제1학생회관"),
        ("2nd", "OCL03.02", "제2학생회관"),
        ("3rd", "OCL03.03", "제3학생회관"),
        ("4th", "OCL03.04", "제4학생회관"),
        ("life_science", "OCL03.05", "생활과학대학"),
    )
    weeks = ("2026.06.01", "2026.06.15", "2026.06.22", "2026.06.29")
    specs = []
    for week_index, week in enumerate(weeks):
        week_id = week.replace(".", "_")
        for cafeteria_index, (slug, code, cafeteria_name) in enumerate(cafeterias):
            specs.append(
                SourceSpec(
                    source_id=f"cnu_mobile_food_week_{week_id}_{slug}",
                    label=3,
                    domain="dining",
                    url=(
                        f"https://mobileadmin.cnu.ac.kr/food/index.jsp?searchYmd={week}"
                        f"&searchLang=OCL04.10&searchView=date&searchCafeteria={code}"
                    ),
                    parser_type="dining",
                    stage="stage1",
                    active=True,
                    priority=90 + week_index * 5 + cafeteria_index,
                    freshness_policy="short_ttl",
                    notes=f"June 2026 weekly dining endpoint for {cafeteria_name}",
                )
            )
    return tuple(specs)


STAGE1_CANDIDATE_SOURCES: tuple[SourceSpec, ...] = (
    *_curriculum_year_sources(),
    SourceSpec(
        source_id="graduation_energy_requirements",
        label=0,
        domain="graduation",
        url="https://energy.cnu.ac.kr/energy/department/graduate.do",
        parser_type="html",
        stage="stage1",
        active=False,
        priority=10,
        notes="candidate department graduation requirements",
        department="에너지공학과",
    ),
    SourceSpec(
        source_id="graduation_horticulture_counsel",
        label=0,
        domain="graduation",
        url="https://horti.cnu.ac.kr/horti/college/college04.do",
        parser_type="html",
        stage="stage1",
        active=False,
        priority=20,
        notes="candidate department academic counsel page with graduation table",
        department="원예학과",
    ),
    SourceSpec(
        source_id="notice_energy_academic",
        label=1,
        domain="notices",
        url="https://energy.cnu.ac.kr/energy/department/academic.do",
        parser_type="html",
        stage="stage1",
        active=False,
        priority=30,
        freshness_policy="snapshot",
        notes="candidate department academic guide covering course registration and leave/return",
        department="에너지공학과",
    ),
    SourceSpec(
        source_id="academic_calendar_dance",
        label=2,
        domain="academic_calendar",
        url="https://dance.cnu.ac.kr/dance/academiccal/calendar/academiccal02.do",
        parser_type="calendar",
        stage="stage1",
        active=False,
        priority=40,
        notes="candidate department academic calendar mirror",
        department="무용학과",
    ),
    *_academic_calendar_year_sources(),
    SourceSpec(
        source_id="shuttle_geo_notice_2026",
        label=4,
        domain="shuttle",
        url="https://geo.cnu.ac.kr/notice/?vid=956",
        parser_type="board_detail",
        stage="stage1",
        active=False,
        priority=50,
        freshness_policy="snapshot_with_term_check",
        notes="candidate 2026 shuttle notice with HWP attachment",
    ),
    SourceSpec(
        source_id="cnu_mobile_food_week_2026_06_08_1st",
        label=3,
        domain="dining",
        url=(
            "https://mobileadmin.cnu.ac.kr/food/index.jsp?searchYmd=2026.06.09&searchLang=OCL04.10"
            "&searchView=date&searchCafeteria=OCL03.01"
        ),
        parser_type="dining",
        stage="stage1",
        active=True,
        priority=55,
        freshness_policy="short_ttl",
        notes="verified weekly dining endpoint for 제1학생회관",
    ),
    SourceSpec(
        source_id="cnu_mobile_food_week_2026_06_08_2nd",
        label=3,
        domain="dining",
        url=(
            "https://mobileadmin.cnu.ac.kr/food/index.jsp?searchYmd=2026.06.09&searchLang=OCL04.10"
            "&searchView=date&searchCafeteria=OCL03.02"
        ),
        parser_type="dining",
        stage="stage1",
        active=True,
        priority=56,
        freshness_policy="short_ttl",
        notes="verified weekly dining endpoint for 제2학생회관",
    ),
    SourceSpec(
        source_id="cnu_mobile_food_week_2026_06_08_3rd",
        label=3,
        domain="dining",
        url=(
            "https://mobileadmin.cnu.ac.kr/food/index.jsp?searchYmd=2026.06.09&searchLang=OCL04.10"
            "&searchView=date&searchCafeteria=OCL03.03"
        ),
        parser_type="dining",
        stage="stage1",
        active=True,
        priority=57,
        freshness_policy="short_ttl",
        notes="verified weekly dining endpoint for 제3학생회관",
    ),
    SourceSpec(
        source_id="cnu_mobile_food_week_2026_06_08_4th",
        label=3,
        domain="dining",
        url=(
            "https://mobileadmin.cnu.ac.kr/food/index.jsp?searchYmd=2026.06.09&searchLang=OCL04.10"
            "&searchView=date&searchCafeteria=OCL03.04"
        ),
        parser_type="dining",
        stage="stage1",
        active=True,
        priority=58,
        freshness_policy="short_ttl",
        notes="verified weekly dining endpoint for 제4학생회관",
    ),
    SourceSpec(
        source_id="cnu_mobile_food_week_2026_06_08_life_science",
        label=3,
        domain="dining",
        url=(
            "https://mobileadmin.cnu.ac.kr/food/index.jsp?searchYmd=2026.06.09&searchLang=OCL04.10"
            "&searchView=date&searchCafeteria=OCL03.05"
        ),
        parser_type="dining",
        stage="stage1",
        active=True,
        priority=59,
        freshness_policy="short_ttl",
        notes="verified weekly dining endpoint for 생활과학대학",
    ),
    *_academic_notice_page_sources(),
    *_june_dining_week_sources(),
    SourceSpec(
        source_id="dining_mobile_candidate",
        label=3,
        domain="dining",
        url="https://mobileadmin.cnu.ac.kr/food/index.jsp",
        parser_type="dining",
        stage="stage1",
        active=False,
        priority=60,
        freshness_policy="short_ttl",
        notes="candidate dining endpoint retained inactive until official-chain and parser behavior are verified",
    ),
)

STAGE2_CANDIDATE_SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        source_id="curriculum_2025_pdf_candidate",
        label=0,
        domain="graduation",
        url="https://plus.cnu.ac.kr/html/kr/25file/2025_book.pdf",
        parser_type="pdf",
        raw_suffix="pdf",
        stage="stage2",
        active=False,
        priority=10,
        notes="candidate expanded curriculum PDF parsing and chunking",
        curriculum_year="2025",
    ),
    SourceSpec(
        source_id="sugang_entry_2025_pdf",
        label=1,
        domain="notices",
        url="https://sugang.cnu.ac.kr/login/data/2025_SugangEntry.pdf",
        parser_type="pdf",
        raw_suffix="pdf",
        stage="stage2",
        active=False,
        priority=20,
        notes="candidate course-registration guide PDF",
    ),
    SourceSpec(
        source_id="academic_calendar_cic",
        label=2,
        domain="academic_calendar",
        url="https://cic.cnu.ac.kr/",
        parser_type="html",
        stage="stage2",
        active=False,
        priority=30,
        notes="candidate secondary academic calendar entrypoint",
    ),
    SourceSpec(
        source_id="dining_plus_welfare_candidate",
        label=3,
        domain="dining",
        url="https://plus.cnu.ac.kr/html/kr/sub05/sub05_050401.html",
        parser_type="dining",
        stage="stage2",
        active=False,
        priority=40,
        freshness_policy="short_ttl",
        notes="candidate welfare/dining page; URL requires fetch verification before activation",
    ),
    SourceSpec(
        source_id="shuttle_plus_main_candidate",
        label=4,
        domain="shuttle",
        url="https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html",
        parser_type="shuttle",
        stage="stage2",
        active=False,
        priority=50,
        freshness_policy="snapshot_with_term_check",
        notes="candidate expanded shuttle parsing for stops and term-specific operation dates",
    ),
)

SOURCE_SPECS: tuple[SourceSpec, ...] = STAGE0_SOURCES + STAGE1_CANDIDATE_SOURCES + STAGE2_CANDIDATE_SOURCES


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
            timeout=120.0 if spec.raw_suffix == "pdf" else 30.0,
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
