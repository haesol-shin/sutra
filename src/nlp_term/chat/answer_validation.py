from __future__ import annotations

import re

from pydantic import BaseModel, Field


INTERNAL_ID_RE = re.compile(r"(chunk[_\s-]*\d+|doc[_\s-]*\d+|source\s+\d+|source[_-]\d+)", re.IGNORECASE)
HANGUL_RE = re.compile(r"[가-힣]")


class Task2AnswerValidationResult(BaseModel):
    passed: bool
    failures: list[str] = Field(default_factory=list)
    answer_chars: int
    must_not_claim_violations: list[str] = Field(default_factory=list)


def validate_task2_answer(
    answer: str,
    *,
    must_not_claim: list[str] | None = None,
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

    return Task2AnswerValidationResult(
        passed=not failures,
        failures=failures,
        answer_chars=len(stripped),
        must_not_claim_violations=violations,
    )
