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
    index_eligible: bool = True
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
            "index_eligible": self.index_eligible,
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
        official_chain_ok=True,
        freshness_policy="short_ttl",
        notes="current mobile dining menu linked from CNU official welfare menu 금주의식단",
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


def _high_value_official_sources() -> tuple[SourceSpec, ...]:
    return (
        SourceSpec(
            source_id="academic_calendar_2026",
            label=2,
            domain="academic_calendar",
            url=(
                "https://plus.cnu.ac.kr/_prog/academic_calendar/"
                "?menu_dvs_cd=05020101&site_dvs_cd=kr&year=2026"
            ),
            parser_type="calendar",
            stage="stage1",
            active=True,
            priority=45,
            official_chain_ok=True,
            notes="official academic calendar for 2026 with explicit year parameter",
            curriculum_year="2026",
        ),
        SourceSpec(
            source_id="course_registration_notice_2026",
            label=1,
            domain="notices",
            url=(
                "https://plus.cnu.ac.kr/_prog/_board/?GotoPage=1&code=sub07_0702"
                "&menu_dvs_cd=0702&mode=V&no=2511913&site_dvs_cd=kr"
                "&skey=title&sval=%EC%88%98%EA%B0%95%EC%8B%A0%EC%B2%AD"
            ),
            parser_type="board_detail",
            stage="stage1",
            active=True,
            priority=50,
            official_chain_ok=True,
            freshness_policy="snapshot",
            notes="2026 course registration academic notice detail",
        ),
        SourceSpec(
            source_id="course_registration_plan_2025_2_pdf",
            label=1,
            domain="notices",
            url="https://plus.cnu.ac.kr/Upl/_board/sub07_0702/sub07_0702_0_1753409201.pdf",
            parser_type="pdf",
            raw_suffix="pdf",
            stage="stage1",
            active=True,
            priority=51,
            official_chain_ok=True,
            notes="2025 second semester course registration plan attachment",
        ),
        SourceSpec(
            source_id="shuttle_geo_notice_2026",
            label=4,
            domain="shuttle",
            url="https://geo.cnu.ac.kr/notice/?vid=956",
            parser_type="board_detail",
            stage="stage1",
            active=True,
            priority=52,
            official_chain_ok=True,
            freshness_policy="snapshot_with_term_check",
            notes="2026 department-linked shuttle operation notice",
        ),
        SourceSpec(
            source_id="dining_operation_notice_2507684",
            label=3,
            domain="dining",
            url=(
                "https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0701&menu_dvs_cd=0701"
                "&mode=V&no=2507684&site_dvs_cd=kr&upr_ntt_no=2507684"
            ),
            parser_type="board_detail",
            stage="stage1",
            active=True,
            priority=53,
            official_chain_ok=True,
            freshness_policy="snapshot",
            notes="campus dining operation closure notice detail",
        ),
        SourceSpec(
            source_id="homepage_academic_calendar_module",
            label=2,
            domain="academic_calendar",
            url="https://homepage.cnu.ac.kr/dev/calendar/college.do",
            parser_type="board_detail",
            stage="stage1",
            active=True,
            priority=54,
            official_chain_ok=True,
            index_eligible=False,
            notes="official homepage academic calendar module retained as raw candidate until parser mapping is implemented",
        ),
        SourceSpec(
            source_id="scholarship_overview",
            label=1,
            domain="notices",
            url="https://plus.cnu.ac.kr/html/hub/support/support_030301.html",
            parser_type="board_detail",
            stage="stage1",
            active=True,
            priority=60,
            official_chain_ok=True,
            notes="campus scholarship system overview",
        ),
        SourceSpec(
            source_id="scholarship_external_overview",
            label=1,
            domain="notices",
            url="https://plus.cnu.ac.kr/html/hub/support/support_030303.html",
            parser_type="board_detail",
            stage="stage1",
            active=True,
            priority=61,
            official_chain_ok=True,
            notes="external scholarship system overview",
        ),
        SourceSpec(
            source_id="student_loan_overview",
            label=1,
            domain="notices",
            url="https://plus.cnu.ac.kr/html/hub/support/support_030306.html",
            parser_type="board_detail",
            stage="stage1",
            active=True,
            priority=62,
            official_chain_ok=True,
            notes="student loan policy overview",
        ),
        SourceSpec(
            source_id="english_ability_criteria",
            label=1,
            domain="notices",
            url="https://plus.cnu.ac.kr/html/hub/affairs/affairs_020305.html",
            parser_type="board_detail",
            stage="stage1",
            active=True,
            priority=63,
            official_chain_ok=True,
            notes="English ability recognition criteria including TOEIC-related standards",
        ),
        SourceSpec(
            source_id="english_ability_notice_2025_1_pdf",
            label=1,
            domain="notices",
            url="https://plus.cnu.ac.kr/Upl/_board/sub07_0702/sub07_0702_0_1742277916.pdf",
            parser_type="pdf",
            raw_suffix="pdf",
            stage="stage1",
            active=True,
            priority=64,
            official_chain_ok=True,
            notes="2025 first semester English ability recognition application attachment",
        ),
        SourceSpec(
            source_id="registration_overload_faq",
            label=1,
            domain="notices",
            url=(
                "https://plus.cnu.ac.kr/_prog/_board/?GotoPage=&code=sub05_050205"
                "&menu_dvs_cd=050205&mode=V&no=2507407&ntt_tag="
            ),
            parser_type="board_detail",
            stage="stage1",
            active=True,
            priority=65,
            official_chain_ok=True,
            notes="registration fee FAQ for students beyond normal study period",
        ),
        SourceSpec(
            source_id="graduation_energy_requirements",
            label=0,
            domain="graduation",
            url="https://energy.cnu.ac.kr/energy/department/graduate.do",
            parser_type="html",
            stage="stage1",
            active=True,
            priority=66,
            official_chain_ok=True,
            notes="department graduation requirements",
            department="에너지공학과",
        ),
        SourceSpec(
            source_id="graduation_law_requirements",
            label=0,
            domain="graduation",
            url="https://law.cnu.ac.kr/law/curriculum/graduate.do",
            parser_type="html",
            stage="stage1",
            active=True,
            priority=67,
            official_chain_ok=True,
            index_eligible=False,
            notes="graduate-school requirement source retained as raw candidate because Task 2 is undergraduate-centered",
            department="법학과",
        ),
        SourceSpec(
            source_id="academic_calendar_english_education_undergrad",
            label=2,
            domain="academic_calendar",
            url="https://enedu.cnu.ac.kr/enedu/curriculum/calendar-undergrad.do",
            parser_type="board_detail",
            stage="stage1",
            active=True,
            priority=68,
            official_chain_ok=True,
            index_eligible=False,
            notes="department undergrad calendar retained as raw candidate until non-plus calendar parser is implemented",
            department="영어교육과",
        ),
        SourceSpec(
            source_id="graduation_vetmed_requirements",
            label=0,
            domain="graduation",
            url="https://vetmed.cnu.ac.kr/vetmed/info/condition.do",
            parser_type="html",
            stage="stage1",
            active=True,
            priority=69,
            official_chain_ok=True,
            notes="department graduation requirements",
            department="수의학과",
        ),
        SourceSpec(
            source_id="graduation_chemistry_credit",
            label=0,
            domain="graduation",
            url="https://chem.cnu.ac.kr/chem/undergrad/credit.do",
            parser_type="html",
            stage="stage1",
            active=True,
            priority=70,
            official_chain_ok=True,
            notes="department credit and curriculum requirement page",
            department="화학과",
        ),
        SourceSpec(
            source_id="graduation_chemistry_teaching",
            label=0,
            domain="graduation",
            url="https://chem.cnu.ac.kr/chem/undergrad/teaching.do",
            parser_type="html",
            stage="stage1",
            active=True,
            priority=71,
            official_chain_ok=True,
            notes="department teaching-course requirement page",
            department="화학과",
        ),
    )


def _department_notice_candidate_sources() -> tuple[SourceSpec, ...]:
    boards = (
        ("chemistry", "화학과", "https://chem.cnu.ac.kr/chem/undergrad/notice.do"),
        ("ai", "인공지능학과", "https://ai.cnu.ac.kr/ai/board/notice.do"),
        ("computer", "컴퓨터융합학부", "https://computer.cnu.ac.kr/computer/notice/notice.do"),
    )
    specs = []
    for board_index, (slug, department, base_url) in enumerate(boards):
        for page_index, offset in enumerate(range(0, 100, 10)):
            specs.append(
                SourceSpec(
                    source_id=f"notice_candidate_{slug}_{offset}",
                    label=1,
                    domain="notices",
                    url=f"{base_url}?article.offset={offset}&articleLimit=10",
                    parser_type="board_detail",
                    stage="stage1",
                    active=True,
                    priority=140 + board_index * 10 + page_index,
                    official_chain_ok=True,
                    index_eligible=False,
                    freshness_policy="snapshot",
                    notes=f"department notice raw candidate page for {department}; not promoted until parser/gate review",
                    department=department,
                )
            )
    return tuple(specs)


def _academic_notice_candidate_pool_sources() -> tuple[SourceSpec, ...]:
    return tuple(
        SourceSpec(
            source_id=f"academic_notice_candidate_page_{page}",
            label=1,
            domain="notices",
            url=(
                "https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702"
                f"&menu_dvs_cd=0702&site_dvs_cd=kr&GotoPage={page}"
            ),
            parser_type="board_detail",
            stage="stage1",
            active=True,
            priority=180 + page,
            official_chain_ok=True,
            index_eligible=False,
            freshness_policy="latest_snapshot",
            notes="central academic notice raw candidate page; not promoted to avoid notice dominance",
        )
        for page in range(7, 37)
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
                    official_chain_ok=True,
                    freshness_policy="short_ttl",
                    notes=f"June 2026 weekly dining endpoint for {cafeteria_name}",
                )
            )
    return tuple(specs)


STAGE1_CANDIDATE_SOURCES: tuple[SourceSpec, ...] = (
    *_curriculum_year_sources(),
    *_high_value_official_sources(),
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
        official_chain_ok=True,
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
        official_chain_ok=True,
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
        official_chain_ok=True,
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
        official_chain_ok=True,
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
        official_chain_ok=True,
        freshness_policy="short_ttl",
        notes="verified weekly dining endpoint for 생활과학대학",
    ),
    *_academic_notice_page_sources(),
    *_june_dining_week_sources(),
    *_department_notice_candidate_sources(),
    *_academic_notice_candidate_pool_sources(),
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
            timeout=180.0 if spec.raw_suffix == "pdf" else 60.0,
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
