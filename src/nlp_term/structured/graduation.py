from __future__ import annotations

from pathlib import Path
import re

from nlp_term.collect.source_inventory import SourceSpec
from nlp_term.paths import PROJECT_ROOT
from nlp_term.prepare.document_parsers import document_to_text
from nlp_term.prepare.parsers import html_to_text
from nlp_term.schemas import KnowledgeDoc, RawSource, SourceVerification
from nlp_term.structured.rows import GraduationRequirementRow, graduation_requirement_row_id


REQUIREMENT_TERMS = ("졸업", "이수", "학점", "전공", "교양", "교육과정")
VALUE_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>학점|회|개|년)")
YEAR_RE = re.compile(r"20\d{2}")
SNIPPET_RE = re.compile(
    r"[^.。]{0,160}(?:졸업소요학점|졸업학점|졸업이수|졸업 요건|졸업 요건|전공|교양|이수학점)[^.。]{0,260}"
)
TARGET_DEPARTMENTS = (
    "컴퓨터인공지능학부",
    "컴퓨터융합학부",
    "인공지능학과",
    "경영학부",
    "정보통신융합학부",
    "신소재공학과",
    "의예과",
    "영어영문학과",
    "생화학과",
)


class GraduationRequirementAdapter:
    source_id = "graduation_requirements"
    max_rows_per_source = 120

    def parse(
        self,
        *,
        spec: SourceSpec,
        raw: RawSource,
        verification: SourceVerification,
    ) -> list[GraduationRequirementRow]:
        text = _source_text(raw)
        rows: list[GraduationRequirementRow] = []
        seen: set[tuple[str, str, str, str]] = set()
        for ordinal, snippet in enumerate(_requirement_snippets(text), start=1):
            value, unit = _required_value(snippet)
            if not value:
                continue
            department = spec.department or _infer_department(snippet)
            curriculum_year = spec.curriculum_year or _infer_curriculum_year(snippet, raw.url)
            requirement_name = _requirement_name(snippet)
            key = (department, curriculum_year, requirement_name, snippet)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                GraduationRequirementRow.from_source_context(
                    spec=spec,
                    raw=raw,
                    verification=verification,
                    row_id=graduation_requirement_row_id(
                        source_id=spec.source_id,
                        department=department,
                        curriculum_year=curriculum_year,
                        requirement_name=requirement_name,
                        ordinal=len(rows) + 1,
                    ),
                    evidence_text=snippet,
                    department=department,
                    curriculum_year=curriculum_year,
                    admission_year=_infer_admission_year(snippet, curriculum_year),
                    requirement_category=_requirement_category(snippet),
                    requirement_name=requirement_name,
                    required_value=value,
                    unit=unit,
                    applies_to=_applies_to(snippet, department),
                    effective_year=curriculum_year,
                    source_section=f"requirement_candidate_{ordinal}",
                    confidence=_confidence(spec=spec, snippet=snippet, value=value),
                )
            )
            if len(rows) >= self.max_rows_per_source:
                break
        if not rows:
            raise ValueError("graduation requirement rows not found")
        return rows

    def to_knowledge_docs(self, rows: list[GraduationRequirementRow]) -> list[KnowledgeDoc]:
        return [row.to_knowledge_doc() for row in rows]


def _source_text(raw: RawSource) -> str:
    raw_path = PROJECT_ROOT / Path(raw.raw_path)
    suffix = raw_path.suffix.lower()
    if suffix in {".pdf", ".hwp", ".hwpx"} or any(kind in raw.content_type.lower() for kind in ("pdf", "hwp", "hwpx")):
        text = document_to_text(raw_path, content_type=raw.content_type)
    else:
        text = html_to_text(raw_path.read_bytes(), source_id=raw.source_id)
    return " ".join(text.split())


def _requirement_snippets(text: str) -> list[str]:
    del text
    return []


def _clean_snippet(value: str) -> str:
    return " ".join(value.split()).strip(" -·*")


def _is_requirement_snippet(snippet: str) -> bool:
    if len(snippet) < 25:
        return False
    if sum(1 for term in REQUIREMENT_TERMS if term in snippet) < 2:
        return False
    return bool(VALUE_RE.search(snippet))


def _required_value(snippet: str) -> tuple[str, str]:
    if "졸업소요학점" in snippet:
        tail = snippet.split("졸업소요학점", 1)[1]
        match = re.search(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>학점)", tail)
        if match:
            return match.group("value"), match.group("unit")
    match = re.search(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>학점)", snippet)
    if match:
        return match.group("value"), match.group("unit")
    match = re.search(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>회|개)", snippet)
    if not match:
        return "", ""
    return match.group("value"), match.group("unit")


def _infer_department(snippet: str) -> str:
    for department in TARGET_DEPARTMENTS:
        if department in snippet:
            return department
    return "공통"


def _infer_curriculum_year(snippet: str, url: str) -> str:
    for value in YEAR_RE.findall(snippet):
        if value.startswith("20"):
            return value
    url_match = re.search(r"/(\d{2})file/", url)
    if url_match:
        return f"20{url_match.group(1)}"
    return "unknown"


def _infer_admission_year(snippet: str, curriculum_year: str) -> str:
    years = YEAR_RE.findall(snippet)
    return years[0] if years else curriculum_year


def _requirement_category(snippet: str) -> str:
    if "졸업소요학점" in snippet or "졸업학점" in snippet:
        return "total_credits"
    if "교양" in snippet:
        return "general_education"
    if "전공" in snippet:
        return "major"
    if "진로설계" in snippet or "상담" in snippet:
        return "advising"
    return "other"


def _requirement_name(snippet: str) -> str:
    category = _requirement_category(snippet)
    if category == "total_credits":
        return "졸업소요학점"
    if category == "general_education":
        return "교양 이수학점"
    if category == "major":
        return "전공 이수학점"
    if category == "advising":
        return "진로설계/상담 이수"
    return "졸업요건"


def _applies_to(snippet: str, department: str) -> str:
    years = YEAR_RE.findall(snippet)
    if years:
        return f"{department} {years[0]}학년도 적용자"
    return f"{department} 적용자"


def _confidence(*, spec: SourceSpec, snippet: str, value: str) -> float:
    score = 0.55
    if spec.department:
        score += 0.15
    if spec.curriculum_year or YEAR_RE.search(snippet):
        score += 0.10
    if value and "학점" in snippet:
        score += 0.10
    if "졸업" in snippet:
        score += 0.10
    return min(score, 0.95)
