from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
import json
from pathlib import Path

from pydantic import BaseModel, Field

from nlp_term.chat.orchestrator import answer_with_harness
from nlp_term.chat.state_contract import (
    AnswerKind,
    AnswerValidationStatus,
    FetchDecision,
    OutputStatus,
)
from nlp_term.paths import data_dir, model_dir
from nlp_term.schemas import Domain
from nlp_term.validators import file_checksum, read_json


class HarnessSafetyCase(BaseModel):
    case_id: str
    question: str
    expected_label: int = Field(ge=0, le=4)
    expected_domain: Domain
    expected_answer_kind: AnswerKind
    scenario: str
    must_not_contain: list[str] = Field(default_factory=list)


def run_harness_safety_experiment(
    *,
    questions_path: Path,
    knowledge_path: Path,
    output_path: Path,
    generator: Callable[[str, str], str] | None = None,
) -> dict[str, object]:
    cases = _load_cases(questions_path)
    writer = generator or _unsafe_probe_writer
    rows: list[dict[str, object]] = []
    domain_coverage: set[str] = set()
    answer_kind_counts: Counter[str] = Counter()
    scenario_counts: Counter[str] = Counter()
    bottleneck_counts: Counter[str] = Counter()
    answered_count = 0
    fail_close_count = 0
    route_match_count = 0
    answer_kind_match_count = 0
    validation_failure_count = 0
    wrong_domain_pass_count = 0
    current_fact_hallucination_count = 0

    for case in cases:
        result = answer_with_harness(
            case.question,
            mode="realtime" if case.expected_answer_kind == AnswerKind.CURRENT_FACT else "chat",
            knowledge_path=knowledge_path,
            generator=lambda prompt, question=case.question: writer(question, prompt),
            question_time=datetime(2026, 6, 7, tzinfo=timezone.utc),
        )
        trace = result.trace
        output_status = str(result.output_status)
        answered = result.output_status == OutputStatus.ANSWERED
        fail_closed = result.output_status == OutputStatus.FAIL_CLOSED
        route_match = trace.route_domain == case.expected_domain
        answer_kind_match = trace.answer_kind == case.expected_answer_kind
        has_wrong_domain_evidence = any(
            status.metadata_domain is not None and status.metadata_domain != trace.route_domain
            for status in trace.source_statuses
        )
        current_hallucination = _has_current_fact_hallucination(case, result.output.model)
        validation_failed = trace.answer_validation_status not in {
            AnswerValidationStatus.PASSED,
            AnswerValidationStatus.BLOCKED,
        }
        bottleneck = _classify_bottleneck(case, output_status=output_status, route_match=route_match, trace=trace)

        domain_coverage.add(case.expected_domain)
        answer_kind_counts[str(case.expected_answer_kind)] += 1
        scenario_counts[case.scenario] += 1
        bottleneck_counts[bottleneck] += 1
        answered_count += int(answered)
        fail_close_count += int(fail_closed)
        route_match_count += int(route_match)
        answer_kind_match_count += int(answer_kind_match)
        validation_failure_count += int(validation_failed)
        wrong_domain_pass_count += int(
            answered and (has_wrong_domain_evidence or not route_match)
        )
        current_fact_hallucination_count += int(current_hallucination)

        rows.append(
            {
                "case_id": case.case_id,
                "question": case.question,
                "scenario": case.scenario,
                "expected_label": case.expected_label,
                "expected_domain": case.expected_domain,
                "expected_answer_kind": str(case.expected_answer_kind),
                "output_status": output_status,
                "route_label": trace.route_label,
                "route_domain": trace.route_domain,
                "answer_kind": str(trace.answer_kind),
                "route_match": route_match,
                "answer_kind_match": answer_kind_match,
                "retrieved_doc_ids": trace.retrieved_doc_ids,
                "retrieved_scores": trace.retrieved_scores,
                "fetch_decision": str(trace.fetch_decision),
                "freshness_status": str(trace.freshness_status),
                "generation_status": str(trace.generation_status),
                "answer_validation_status": str(trace.answer_validation_status),
                "wrong_domain_evidence": has_wrong_domain_evidence,
                "current_fact_hallucination": current_hallucination,
                "bottleneck": bottleneck,
                "failure_reason": trace.failure_reason,
                "answer": result.output.model,
            }
        )

    question_count = len(cases)
    report = {
        "evaluation_scope": "task2_task3_phase_a_harness_safety",
        "evaluation_set_type": "harness_safety_probe",
        "dataset_origin": "synthetic",
        "claim_level": "sanity",
        "input_path": str(questions_path),
        "input_checksum": file_checksum(questions_path),
        "knowledge_path": str(knowledge_path),
        "knowledge_checksum": file_checksum(knowledge_path),
        "question_count": question_count,
        "domain_coverage": sorted(domain_coverage),
        "answer_kind_counts": dict(sorted(answer_kind_counts.items())),
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "answered_count": answered_count,
        "fail_close_count": fail_close_count,
        "answered_rate": _rate(answered_count, question_count),
        "fail_close_rate": _rate(fail_close_count, question_count),
        "route_match_rate": _rate(route_match_count, question_count),
        "answer_kind_match_rate": _rate(answer_kind_match_count, question_count),
        "wrong_domain_pass_count": wrong_domain_pass_count,
        "current_fact_hallucination_count": current_fact_hallucination_count,
        "validator_failure_count": validation_failure_count,
        "bottleneck_counts": dict(sorted(bottleneck_counts.items())),
        "pass_criteria": {
            "wrong_domain_pass_count": 0,
            "current_fact_hallucination_count": 0,
        },
        "pass_criteria_met": wrong_domain_pass_count == 0 and current_fact_hallucination_count == 0,
        "final_performance_claim_allowed": False,
        "rows": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _load_cases(path: Path) -> list[HarnessSafetyCase]:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    return [HarnessSafetyCase.model_validate(row) for row in payload]


def _unsafe_probe_writer(question: str, prompt: str) -> str:
    compact = question.replace(" ", "")
    if "메뉴" in compact or "점심" in compact:
        return "오늘 점심은 김치찌개입니다."
    if "시간표" in compact and ("오늘" in compact or "현재" in compact):
        return "오늘 셔틀은 08:30에 운행합니다."
    fact = _first_prompt_fact(prompt)
    if fact:
        return f"{fact} 자세한 내용은 공식 출처를 확인해 주세요."
    return "공식 근거가 충분하지 않아 확답하기 어렵습니다."


def _first_prompt_fact(prompt: str) -> str | None:
    marker = "핵심 사실:"
    for line in prompt.splitlines():
        if marker in line:
            fact = line.split(marker, 1)[1].strip()
            if fact:
                return fact
    return None


def _has_current_fact_hallucination(case: HarnessSafetyCase, answer: str) -> bool:
    if case.expected_answer_kind != AnswerKind.CURRENT_FACT and case.scenario != "current_fact_guard":
        return False
    forbidden = case.must_not_contain or ["김치찌개", "돈까스", "08:30", "마감일"]
    return any(term in answer for term in forbidden)


def _classify_bottleneck(
    case: HarnessSafetyCase,
    *,
    output_status: str,
    route_match: bool,
    trace,
) -> str:
    if not route_match:
        return "classifier"
    if output_status == OutputStatus.ANSWERED:
        return "none"
    if trace.answer_validation_status not in {AnswerValidationStatus.PASSED, AnswerValidationStatus.BLOCKED}:
        return "validator"
    if trace.fetch_decision in {
        FetchDecision.FETCH_BLOCKED_UNOFFICIAL,
        FetchDecision.FETCH_BLOCKED_UNSUPPORTED_PARSER,
        FetchDecision.FETCH_REQUIRED_BUT_NOT_IMPLEMENTED,
    }:
        return "data"
    if trace.fetch_decision == FetchDecision.FETCH_BLOCKED_NO_REGISTRY:
        return "data"
    if case.scenario == "unsupported":
        return "scope"
    return "retrieval"


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Task 2/3 Phase A harness safety experiment.")
    parser.add_argument("--questions", type=Path, default=data_dir() / "harness_safety_questions.json")
    parser.add_argument("--knowledge", type=Path, default=data_dir() / "knowledge_seed.json")
    parser.add_argument("--output", type=Path, default=model_dir() / "metrics" / "harness_safety_experiment.json")
    args = parser.parse_args()
    run_harness_safety_experiment(
        questions_path=args.questions,
        knowledge_path=args.knowledge,
        output_path=args.output,
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
