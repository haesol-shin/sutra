from __future__ import annotations

from collections.abc import Iterable
import re

from pydantic import BaseModel, Field


INTERNAL_ID_RE = re.compile(r"(chunk[_\s-]*\d+|doc[_\s-]*\d+|source\s+\d+|source[_-]\d+)", re.IGNORECASE)
HANGUL_RE = re.compile(r"[가-힣]")
URL_RE = re.compile(r"https?://[^\s)>\]]+")
NUMERIC_CLAIM_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:학점|점|월|일|년|명|개|회|%)")
INSTITUTION_CLAIM_RE = re.compile(r"[가-힣A-Za-z0-9·]{2,}(?:대학교|학과|학부|대학원|대학|센터|처|팀|사무실)")
MENU_CLAIM_RE = re.compile(r"[\"'“”‘’]?([가-힣A-Za-z0-9\s]+>\s*[가-힣A-Za-z0-9\s>]+)[\"'“”‘’]?")


class Task2AnswerValidationResult(BaseModel):
    passed: bool
    failures: list[str] = Field(default_factory=list)
    answer_chars: int
    must_not_claim_violations: list[str] = Field(default_factory=list)
    unsupported_urls: list[str] = Field(default_factory=list)
    unsupported_numeric_claims: list[str] = Field(default_factory=list)
    unsupported_institution_claims: list[str] = Field(default_factory=list)
    unsupported_menu_claims: list[str] = Field(default_factory=list)


def validate_task2_answer(
    answer: str,
    *,
    must_not_claim: list[str] | None = None,
    evidence_texts: list[str] | None = None,
) -> Task2AnswerValidationResult:
    stripped = answer.strip()
    failures: list[str] = []

    if not stripped:
        failures.append("empty_answer")
    if stripped and not HANGUL_RE.search(stripped):
        failures.append("no_hangul_text")
    if stripped.startswith(("{", "[")):
        failures.append("raw_json_or_template_text")
    if INTERNAL_ID_RE.search(stripped):
        failures.append("internal_id_exposed")
    if "fallback" in stripped.lower() or "system prompt" in stripped.lower():
        failures.append("system_or_fallback_leak")

    violations = [claim for claim in must_not_claim or [] if claim and claim in stripped]
    if violations:
        failures.append("must_not_claim_violation")

    evidence_text = "\n".join(evidence_texts or [])
    unsupported_urls: list[str] = []
    unsupported_numeric_claims: list[str] = []
    unsupported_institution_claims: list[str] = []
    unsupported_menu_claims: list[str] = []
    if evidence_texts is not None:
        unsupported_urls = _unsupported_claims(_extract_urls(stripped), evidence_text)
        unsupported_numeric_claims = _unsupported_claims(_extract_numeric_claims(stripped), evidence_text)
        unsupported_institution_claims = _unsupported_claims(
            _extract_institution_claims(stripped),
            evidence_text,
        )
        unsupported_menu_claims = _unsupported_claims(_extract_menu_claims(stripped), evidence_text)
        if unsupported_urls:
            failures.append("unsupported_url_claim")
        if unsupported_numeric_claims:
            failures.append("unsupported_numeric_claim")
        if unsupported_institution_claims:
            failures.append("unsupported_institution_claim")
        if unsupported_menu_claims:
            failures.append("unsupported_menu_claim")

    return Task2AnswerValidationResult(
        passed=not failures,
        failures=failures,
        answer_chars=len(stripped),
        must_not_claim_violations=violations,
        unsupported_urls=unsupported_urls,
        unsupported_numeric_claims=unsupported_numeric_claims,
        unsupported_institution_claims=unsupported_institution_claims,
        unsupported_menu_claims=unsupported_menu_claims,
    )


def _extract_urls(text: str) -> list[str]:
    return [_strip_claim(match.group(0)) for match in URL_RE.finditer(text)]


def _extract_numeric_claims(text: str) -> list[str]:
    text_without_urls = URL_RE.sub(" ", text)
    return [_strip_claim(match.group(0)) for match in NUMERIC_CLAIM_RE.finditer(text_without_urls)]


def _extract_institution_claims(text: str) -> list[str]:
    text_without_urls = URL_RE.sub(" ", text)
    return _dedupe(_strip_claim(match.group(0)) for match in INSTITUTION_CLAIM_RE.finditer(text_without_urls))


def _extract_menu_claims(text: str) -> list[str]:
    return [_strip_claim(match.group(1)) for match in MENU_CLAIM_RE.finditer(text)]


def _unsupported_claims(claims: list[str], evidence_text: str) -> list[str]:
    return [claim for claim in _dedupe(claims) if claim and _normalize_claim(claim) not in _normalize_claim(evidence_text)]


def _strip_claim(value: str) -> str:
    return value.strip().strip(".,;:!?)]}'\"“”‘’")


def _normalize_claim(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        text = str(value)
        if text not in seen:
            seen.add(text)
            deduped.append(text)
    return deduped
