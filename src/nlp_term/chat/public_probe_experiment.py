from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from nlp_term.chat.orchestrator import answer_with_harness
from nlp_term.chat.state_contract import AnswerValidationStatus, OutputStatus
from nlp_term.paths import data_dir
from nlp_term.schemas import Domain
from nlp_term.validators import file_checksum, read_json


DOMAINS: dict[int, Domain] = {
    0: "graduation",
    1: "notices",
    2: "academic_calendar",
    3: "dining",
    4: "shuttle",
}
REFERENCE_TIME = datetime(2026, 6, 8, tzinfo=ZoneInfo("Asia/Seoul"))


class PublicProbeCase(BaseModel):
    id: str
    question: str
    expected_label: int = Field(ge=0, le=4)
    expected_temporal_type: str
    expected_behavior: str


def run_public_probe_experiment(
    *,
    probe_path: Path,
    knowledge_path: Path,
    output_path: Path,
    markdown_path: Path | None = None,
    reference_time: datetime = REFERENCE_TIME,
) -> dict[str, object]:
    cases = _load_cases(probe_path)
    rows: list[dict[str, object]] = []
    bottleneck_counts: Counter[str] = Counter()
    label_match_count = 0
    temporal_match_count = 0
    answered_count = 0
    fail_close_count = 0

    for case in cases:
        result = answer_with_harness(
            case.question,
            mode="chat",
            backend="deterministic",
            knowledge_path=knowledge_path,
            question_time=reference_time,
        )
        trace = result.trace
        actual_temporal_type = str(trace.temporal_type)
        expected_domain = DOMAINS[case.expected_label]
        label_match = trace.route_label == case.expected_label
        domain_match = trace.route_domain == expected_domain
        temporal_match = actual_temporal_type == case.expected_temporal_type
        output_status = str(result.output_status)
        answered = result.output_status == OutputStatus.ANSWERED
        fail_closed = result.output_status == OutputStatus.FAIL_CLOSED
        bottleneck = _classify_bottleneck(
            label_match=label_match,
            temporal_match=temporal_match,
            output_status=output_status,
            trace=trace,
        )

        label_match_count += int(label_match)
        temporal_match_count += int(temporal_match)
        answered_count += int(answered)
        fail_close_count += int(fail_closed)
        bottleneck_counts[bottleneck] += 1
        rows.append(
            {
                "id": case.id,
                "question": case.question,
                "expected_label": case.expected_label,
                "actual_label": trace.route_label,
                "expected_domain": expected_domain,
                "actual_domain": trace.route_domain,
                "label_match": label_match,
                "domain_match": domain_match,
                "expected_temporal_type": case.expected_temporal_type,
                "actual_temporal_type": actual_temporal_type,
                "temporal_match": temporal_match,
                "temporal_confidence": str(trace.temporal_confidence),
                "target_start": trace.target_start,
                "target_end": trace.target_end,
                "retrieval_requirements": [str(item) for item in trace.retrieval_requirements],
                "output_status": output_status,
                "evidence_sufficiency_status": str(trace.evidence_sufficiency_status),
                "fetch_decision": str(trace.fetch_decision),
                "freshness_status": str(trace.freshness_status),
                "answer_validation_status": str(trace.answer_validation_status),
                "retrieved_doc_ids": trace.retrieved_doc_ids,
                "retrieved_scores": trace.retrieved_scores,
                "prefilter_retrieved_doc_ids": [candidate.doc_id for candidate in trace.prefilter_retrieved_candidates],
                "postfilter_retrieved_doc_ids": [candidate.doc_id for candidate in trace.postfilter_retrieved_candidates],
                "prefilter_retrieved_candidates": _candidate_rows(trace.prefilter_retrieved_candidates),
                "postfilter_retrieved_candidates": _candidate_rows(trace.postfilter_retrieved_candidates),
                "failure_reason": trace.failure_reason,
                "bottleneck": bottleneck,
                "expected_behavior": case.expected_behavior,
                "answer": result.output.model,
            }
        )

    question_count = len(cases)
    report = {
        "evaluation_scope": "task2_public_probe_trace_diagnosis",
        "evaluation_set_type": "public_probe",
        "dataset_origin": "discussion_fixed_probe",
        "claim_level": "diagnostic",
        "final_performance_claim_allowed": False,
        "reference_time": reference_time.isoformat(),
        "probe_path": str(probe_path),
        "probe_checksum": file_checksum(probe_path),
        "knowledge_path": str(knowledge_path),
        "knowledge_checksum": file_checksum(knowledge_path),
        "question_count": question_count,
        "label_match_count": label_match_count,
        "label_match_rate": _rate(label_match_count, question_count),
        "temporal_match_count": temporal_match_count,
        "temporal_match_rate": _rate(temporal_match_count, question_count),
        "answered_count": answered_count,
        "answered_rate": _rate(answered_count, question_count),
        "fail_close_count": fail_close_count,
        "fail_close_rate": _rate(fail_close_count, question_count),
        "bottleneck_counts": dict(sorted(bottleneck_counts.items())),
        "rows": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if markdown_path:
        write_markdown_report(report, markdown_path)
    return report


def write_markdown_report(report: dict[str, object], output_path: Path) -> None:
    rows = report["rows"]
    assert isinstance(rows, list)
    lines = [
        "# Task 2 Public Probe Harness Diagnosis",
        "",
        f"- 기준 시각: `{report['reference_time']}`",
        f"- 질문 수: {report['question_count']}",
        f"- Task1 label match: {report['label_match_count']} / {report['question_count']} ({report['label_match_rate']:.2%})",
        f"- Temporal type match: {report['temporal_match_count']} / {report['question_count']} ({report['temporal_match_rate']:.2%})",
        f"- Answered: {report['answered_count']} / {report['question_count']} ({report['answered_rate']:.2%})",
        f"- Fail-closed: {report['fail_close_count']} / {report['question_count']} ({report['fail_close_rate']:.2%})",
        f"- Bottlenecks: `{json.dumps(report['bottleneck_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "이 결과는 현재 harness의 trace 진단이며 최종 Task 2 성능 claim이 아니다.",
        "",
        "| ID | Label | Temporal | Target | Status | Bottleneck | Failure |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        assert isinstance(row, dict)
        target = _format_target(row)
        label = f"{row['actual_label']} / {row['expected_label']}"
        temporal = f"{row['actual_temporal_type']} / {row['expected_temporal_type']}"
        lines.append(
            "| {id} | {label} | {temporal} | {target} | {status} | {bottleneck} | {failure} |".format(
                id=row["id"],
                label=_escape_md(label),
                temporal=_escape_md(temporal),
                target=_escape_md(target),
                status=_escape_md(str(row["output_status"])),
                bottleneck=_escape_md(str(row["bottleneck"])),
                failure=_escape_md(str(row["failure_reason"] or "")),
            )
        )
    lines.extend(
        [
            "",
            "## Bottleneck Legend",
            "",
            "- `classifier`: Task 1 label이 기대값과 다르다.",
            "- `temporal`: temporal type이 기대값과 다르다.",
            "- `retrieval`: 검색 결과가 없거나 score가 낮아 근거 pack을 만들 수 없다.",
            "- `data`: controlled fetch/source registry/공식성/구조화 데이터가 부족하다.",
            "- `evidence`: 검색은 됐지만 날짜/근거 충분성 검사를 통과하지 못했다.",
            "- `writer`: 답변 생성 후 validator에서 막혔다.",
            "- `none`: 현재 trace 기준으로 harness 병목이 없다.",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_cases(path: Path) -> list[PublicProbeCase]:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    return [PublicProbeCase.model_validate(row) for row in payload]


def _candidate_rows(candidates) -> list[dict[str, object]]:
    return [
        {
            "doc_id": candidate.doc_id,
            "score": candidate.score,
            "label": candidate.label,
            "domain": str(candidate.domain),
            "source_id": candidate.source_id,
            "chunking_strategy": candidate.chunking_strategy,
            "boundary_type": candidate.boundary_type,
            "chunk_confidence": candidate.chunk_confidence,
        }
        for candidate in candidates
    ]


def _classify_bottleneck(
    *,
    label_match: bool,
    temporal_match: bool,
    output_status: str,
    trace,
) -> str:
    if not label_match:
        return "classifier"
    if not temporal_match:
        return "temporal"
    if output_status == OutputStatus.ANSWERED:
        return "none"
    if trace.answer_validation_status not in {AnswerValidationStatus.PASSED, AnswerValidationStatus.BLOCKED}:
        return "writer"
    failure_reason = trace.failure_reason or ""
    if "date_filtered_evidence" in failure_reason:
        return "evidence"
    if "no_retrieved_docs" in failure_reason or "top_score_below_threshold" in failure_reason:
        return "retrieval"
    if "fetch" in str(trace.fetch_decision) or "registry" in failure_reason or "official" in failure_reason:
        return "data"
    return "evidence"


def _format_target(row: dict[str, object]) -> str:
    start = row.get("target_start")
    end = row.get("target_end")
    if start and end and start != end:
        return f"{start}~{end}"
    if start:
        return str(start)
    return ""


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Task 2 public probe trace diagnosis.")
    parser.add_argument("--probe", type=Path, default=data_dir() / "gold" / "task2_public_probe_eval.json")
    parser.add_argument("--knowledge", type=Path, default=data_dir() / "knowledge_seed.json")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/evidence/task2-public-probe-harness-2026-06-08.json"),
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("docs/task2_public_probe_harness_diagnosis_2026_06_08.md"),
    )
    args = parser.parse_args()
    run_public_probe_experiment(
        probe_path=args.probe,
        knowledge_path=args.knowledge,
        output_path=args.output,
        markdown_path=args.markdown,
    )
    print(f"wrote {args.output}")
    print(f"wrote {args.markdown}")


if __name__ == "__main__":
    main()
