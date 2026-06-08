from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
import json
import re
from typing import Literal
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
import requests

from nlp_term.chat.answer_validation import validate_task2_answer
from nlp_term.retrieve.knowledge import load_knowledge
from nlp_term.retrieve.rank import rank_docs


PlannerVariant = Literal["json_only", "short_notes_json", "freeform_json"]
ToolActionName = Literal[
    "rag_search",
    "official_url_search",
    "official_page_extract",
    "answer_now",
    "stop",
]

DEFAULT_OFFICIAL_SEED_URLS = (
    "https://www.cnu.ac.kr/",
    "https://plus.cnu.ac.kr/",
)
OFFICIAL_HOST_SUFFIX = ".cnu.ac.kr"
MAX_EXTRACT_CHARS = 3000


class PlannerAction(BaseModel):
    action: ToolActionName
    query: str | None = None
    scope: str | None = None
    candidate_id: str | None = None
    url: str | None = None
    private_notes: str | None = None


class UrlCandidate(BaseModel):
    candidate_id: str
    url: str
    title: str = ""
    snippet: str = ""


class EvidenceBlock(BaseModel):
    source_url: str
    title: str = ""
    text: str
    page_archetype: str = "unknown"


class ToolStepTrace(BaseModel):
    action: str
    status: str
    query: str | None = None
    candidate_id: str | None = None
    url: str | None = None
    generated_url: bool = False
    evidence_count: int = 0
    error: str | None = None


class ToolExperimentTrace(BaseModel):
    question: str
    planner_variant: PlannerVariant
    max_steps: int
    steps: list[ToolStepTrace] = Field(default_factory=list)
    generated_url_count: int = 0
    writer_tool_call_attempt: bool = False
    unsupported_claim_count: int = 0
    validation_failures: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    final_status: str = "not_started"


class ToolExperimentResult(BaseModel):
    answer: str
    evidence: list[EvidenceBlock] = Field(default_factory=list)
    candidates: list[UrlCandidate] = Field(default_factory=list)
    trace: ToolExperimentTrace


@dataclass
class ToolExperimentTools:
    rag_search: Callable[[str, int], list[EvidenceBlock]] = field(default_factory=lambda: default_rag_search)
    official_url_search: Callable[[str, str], list[UrlCandidate]] = field(
        default_factory=lambda: default_official_url_search
    )
    official_page_extract: Callable[[UrlCandidate], list[EvidenceBlock]] = field(
        default_factory=lambda: default_official_page_extract
    )


def run_tool_use_experiment(
    *,
    question: str,
    planner: Callable[[str], str],
    writer: Callable[[str], str],
    tools: ToolExperimentTools | None = None,
    max_steps: int = 4,
    planner_variant: PlannerVariant = "json_only",
    allow_direct_url_fetch: bool = False,
    current_date: date | None = None,
    rag_top_k: int = 5,
) -> ToolExperimentResult:
    toolset = tools or ToolExperimentTools()
    trace = ToolExperimentTrace(question=question, planner_variant=planner_variant, max_steps=max_steps)
    candidates: dict[str, UrlCandidate] = {}
    evidence: list[EvidenceBlock] = []
    today = current_date or date.today()

    for _ in range(max(max_steps, 0)):
        prompt = _planner_prompt(question=question, today=today, evidence=evidence, candidates=list(candidates.values()))
        try:
            action = parse_planner_action(planner(prompt), variant=planner_variant)
        except Exception as exc:
            trace.steps.append(ToolStepTrace(action="parse_error", status="failed", error=str(exc)))
            trace.final_status = "planner_parse_failed"
            return ToolExperimentResult(answer="", evidence=evidence, candidates=list(candidates.values()), trace=trace)

        generated_url = bool(action.url and action.candidate_id is None)
        if generated_url:
            trace.generated_url_count += 1

        if action.action == "rag_search":
            blocks = toolset.rag_search(action.query or question, rag_top_k)
            evidence.extend(blocks)
            trace.steps.append(
                ToolStepTrace(
                    action=action.action,
                    status="ok",
                    query=action.query,
                    generated_url=generated_url,
                    evidence_count=len(blocks),
                )
            )
            continue

        if action.action == "official_url_search":
            found = toolset.official_url_search(action.query or question, action.scope or "all_cnu")
            for candidate in found:
                candidates[candidate.candidate_id] = candidate
            trace.steps.append(
                ToolStepTrace(
                    action=action.action,
                    status="ok",
                    query=action.query,
                    generated_url=generated_url,
                    evidence_count=len(found),
                )
            )
            continue

        if action.action == "official_page_extract":
            if generated_url and not allow_direct_url_fetch:
                trace.steps.append(
                    ToolStepTrace(
                        action=action.action,
                        status="blocked",
                        url=action.url,
                        generated_url=True,
                        error="direct_url_fetch_disabled",
                    )
                )
                trace.final_status = "blocked_generated_url"
                return ToolExperimentResult(answer="", evidence=evidence, candidates=list(candidates.values()), trace=trace)
            candidate = _candidate_for_action(action, candidates)
            if candidate is None:
                trace.steps.append(
                    ToolStepTrace(
                        action=action.action,
                        status="failed",
                        candidate_id=action.candidate_id,
                        url=action.url,
                        generated_url=generated_url,
                        error="candidate_not_found",
                    )
                )
                trace.final_status = "candidate_not_found"
                return ToolExperimentResult(answer="", evidence=evidence, candidates=list(candidates.values()), trace=trace)
            blocks = toolset.official_page_extract(candidate)
            evidence.extend(blocks)
            trace.steps.append(
                ToolStepTrace(
                    action=action.action,
                    status="ok",
                    candidate_id=candidate.candidate_id,
                    url=candidate.url,
                    generated_url=generated_url,
                    evidence_count=len(blocks),
                )
            )
            continue

        if action.action in {"answer_now", "stop"}:
            trace.steps.append(ToolStepTrace(action=action.action, status="ok"))
            return _write_answer(
                question=question,
                today=today,
                writer=writer,
                evidence=evidence,
                candidates=list(candidates.values()),
                trace=trace,
            )

    trace.final_status = "max_steps_exceeded"
    return ToolExperimentResult(answer="", evidence=evidence, candidates=list(candidates.values()), trace=trace)


def parse_planner_action(text: str, *, variant: PlannerVariant = "json_only") -> PlannerAction:
    payload_text = text.strip()
    if variant == "freeform_json":
        payload_text = _extract_json_object(payload_text)
    elif variant == "short_notes_json":
        payload_text = _extract_json_object(payload_text)
    payload = json.loads(payload_text)
    return PlannerAction.model_validate(payload)


def default_rag_search(query: str, top_k: int) -> list[EvidenceBlock]:
    docs = load_knowledge()
    by_id = {doc.doc_id: doc for doc in docs}
    blocks: list[EvidenceBlock] = []
    for row in rank_docs(query, docs, top_k=top_k):
        doc = by_id.get(row.doc_id)
        if not doc:
            continue
        blocks.append(
            EvidenceBlock(
                source_url=doc.source_url,
                title=doc.title,
                text=_normalize_text(doc.body)[:MAX_EXTRACT_CHARS],
                page_archetype=str(doc.metadata.get("row_type") or doc.metadata.get("source_parser_type") or "rag_doc"),
            )
        )
    return blocks


def default_official_url_search(query: str, scope: str) -> list[UrlCandidate]:
    del scope
    query_tokens = _tokens(query)
    candidates: list[UrlCandidate] = []
    seen: set[str] = set()
    for seed_url in DEFAULT_OFFICIAL_SEED_URLS:
        try:
            response = requests.get(seed_url, timeout=10)
            response.raise_for_status()
        except Exception:
            continue
        soup = BeautifulSoup(response.text, "lxml")
        for link in soup.find_all("a", href=True):
            url = urljoin(seed_url, str(link.get("href")))
            if url in seen or not is_official_cnu_url(url):
                continue
            title = _normalize_text(link.get_text(" ", strip=True))
            haystack = f"{title} {url}"
            if query_tokens and not query_tokens & _tokens(haystack):
                continue
            seen.add(url)
            candidates.append(
                UrlCandidate(
                    candidate_id=f"u{len(candidates) + 1}",
                    url=url,
                    title=title or url,
                    snippet=haystack[:240],
                )
            )
            if len(candidates) >= 10:
                return candidates
    return candidates


def default_official_page_extract(candidate: UrlCandidate) -> list[EvidenceBlock]:
    if not is_official_cnu_url(candidate.url):
        return []
    try:
        response = requests.get(candidate.url, timeout=15)
        response.raise_for_status()
    except Exception:
        return []
    soup = BeautifulSoup(response.text, "lxml")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    title = _normalize_text(soup.title.get_text(" ", strip=True) if soup.title else candidate.title)
    text = _normalize_text(soup.get_text(" ", strip=True))[:MAX_EXTRACT_CHARS]
    if not text:
        return []
    return [
        EvidenceBlock(
            source_url=candidate.url,
            title=title or candidate.title,
            text=text,
            page_archetype="official_page",
        )
    ]


def is_official_cnu_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host == "cnu.ac.kr" or host.endswith(OFFICIAL_HOST_SUFFIX)


def _write_answer(
    *,
    question: str,
    today: date,
    writer: Callable[[str], str],
    evidence: list[EvidenceBlock],
    candidates: list[UrlCandidate],
    trace: ToolExperimentTrace,
) -> ToolExperimentResult:
    prompt = _writer_prompt(question=question, today=today, evidence=evidence, candidates=candidates)
    answer = writer(prompt).strip()
    trace.writer_tool_call_attempt = _looks_like_tool_call(answer)
    validation = validate_task2_answer(
        answer,
        evidence_texts=[block.text + " " + block.source_url for block in evidence],
        strict_grounding=False,
    )
    trace.validation_failures = validation.failures
    trace.validation_warnings = validation.warnings
    trace.unsupported_claim_count = (
        len(validation.unsupported_urls)
        + len(validation.unsupported_numeric_claims)
        + len(validation.unsupported_institution_claims)
        + len(validation.unsupported_menu_claims)
    )
    trace.final_status = "answered"
    return ToolExperimentResult(answer=answer, evidence=evidence, candidates=candidates, trace=trace)


def _planner_prompt(
    *,
    question: str,
    today: date,
    evidence: list[EvidenceBlock],
    candidates: list[UrlCandidate],
) -> str:
    return "\n".join(
        [
            f"현재 날짜: {today.isoformat()}",
            f"질문: {question}",
            "도구 목록:",
            '- rag_search: {"action":"rag_search","query":"..."}',
            '- official_url_search: {"action":"official_url_search","query":"...","scope":"all_cnu"}',
            '- official_page_extract: {"action":"official_page_extract","candidate_id":"..."}',
            '- answer_now: {"action":"answer_now"}',
            "출력은 마지막에 JSON 객체 하나로 끝낸다.",
            _evidence_summary(evidence),
            _candidate_summary(candidates),
        ]
    )


def _writer_prompt(
    *,
    question: str,
    today: date,
    evidence: list[EvidenceBlock],
    candidates: list[UrlCandidate],
) -> str:
    lines = [
        f"현재 날짜: {today.isoformat()}",
        f"사용자 질문: {question}",
        "아래 자료만 사용자에게 자연스럽게 조립해서 답한다.",
        "자료가 부족하면 부족한 범위를 명시하되 내부 절차나 근거라는 표현은 노출하지 않는다.",
    ]
    if evidence:
        lines.append("자료:")
        for index, block in enumerate(evidence, start=1):
            lines.append(f"[{index}] {block.title or block.source_url}")
            lines.append(block.text)
            lines.append(block.source_url)
    elif candidates:
        lines.append("후보 URL:")
        for candidate in candidates:
            lines.append(f"- {candidate.title}: {candidate.url}")
    else:
        lines.append("자료 없음.")
    return "\n".join(lines)


def _candidate_for_action(action: PlannerAction, candidates: dict[str, UrlCandidate]) -> UrlCandidate | None:
    if action.candidate_id:
        return candidates.get(action.candidate_id)
    if action.url:
        return UrlCandidate(candidate_id="generated_url", url=action.url)
    return None


def _evidence_summary(evidence: list[EvidenceBlock]) -> str:
    if not evidence:
        return "현재 자료: 없음"
    lines = ["현재 자료:"]
    for index, block in enumerate(evidence, start=1):
        lines.append(f"- e{index}: {block.title or block.source_url} ({len(block.text)} chars)")
    return "\n".join(lines)


def _candidate_summary(candidates: list[UrlCandidate]) -> str:
    if not candidates:
        return "현재 URL 후보: 없음"
    lines = ["현재 URL 후보:"]
    for candidate in candidates:
        lines.append(f"- {candidate.candidate_id}: {candidate.title} {candidate.url}")
    return "\n".join(lines)


def _extract_json_object(text: str) -> str:
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return fenced[-1].strip()
    start = text.rfind("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return text.strip()
    return text[start : end + 1]


def _looks_like_tool_call(answer: str) -> bool:
    stripped = answer.strip()
    if not stripped.startswith("{"):
        return False
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and isinstance(payload.get("action"), str)


def _tokens(text: str) -> set[str]:
    compact = text.lower().replace(" ", "")
    tokens = {compact[index : index + 2] for index in range(max(len(compact) - 1, 0))}
    tokens.update(part.lower() for part in text.split())
    return {token for token in tokens if token}


def _normalize_text(text: str) -> str:
    return " ".join(str(text).replace("\r", " ").replace("\n", " ").split())
