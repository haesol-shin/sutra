from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable
from datetime import datetime
import json
from pathlib import Path
import time

from nlp_term.chat.llama_server_backend import generate_with_llama_server
from nlp_term.chat.orchestrator import answer_with_harness
from nlp_term.chat.public_probe_experiment import (
    DOMAINS,
    REFERENCE_TIME,
    PublicProbeCase,
    _candidate_rows,
    _classify_bottleneck,
    _load_cases,
    _rate,
)
from nlp_term.chat.state_contract import OutputStatus
from nlp_term.paths import data_dir
from nlp_term.validators import file_checksum


DEFAULT_LLAMA_SERVER_URL = "http://127.0.0.1:18080"
DEFAULT_MAX_TOKENS = 1024


def run_qwen_public_probe_baseline(
    *,
    probe_path: Path,
    knowledge_path: Path,
    output_path: Path,
    markdown_path: Path | None = None,
    reference_time: datetime = REFERENCE_TIME,
    llama_server_url: str = DEFAULT_LLAMA_SERVER_URL,
    writer: Callable[[str], str] | None = None,
    timeout_seconds: int = 180,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict[str, object]:
    cases = _load_cases(probe_path)
    rows: list[dict[str, object]] = []
    bottleneck_counts: Counter[str] = Counter()
    label_match_count = 0
    temporal_match_count = 0
    answered_count = 0
    fail_close_count = 0
    writer_called_count = 0
    writer_blocked_count = 0

    for case in cases:
        row = _run_case(
            case,
            knowledge_path=knowledge_path,
            reference_time=reference_time,
            llama_server_url=llama_server_url,
            writer=writer,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
        )
        label_match_count += int(bool(row["label_match"]))
        temporal_match_count += int(bool(row["temporal_match"]))
        answered_count += int(row["output_status"] == str(OutputStatus.ANSWERED))
        fail_close_count += int(row["output_status"] == str(OutputStatus.FAIL_CLOSED))
        writer_called_count += int(bool(row["qwen_writer_called"]))
        writer_blocked_count += int(bool(row["qwen_writer_called"]) and row["output_status"] != str(OutputStatus.ANSWERED))
        bottleneck_counts[str(row["bottleneck"])] += 1
        rows.append(row)

    question_count = len(cases)
    report = {
        "evaluation_scope": "task2_public_probe_qwen_baseline",
        "evaluation_set_type": "public_probe",
        "dataset_origin": "discussion_fixed_probe",
        "claim_level": "qwen_writer_baseline_not_final_performance",
        "final_performance_claim_allowed": False,
        "writer_backend": "llama_server",
        "llama_server_url": llama_server_url,
        "max_tokens": max_tokens,
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
        "writer_called_count": writer_called_count,
        "writer_blocked_count": writer_blocked_count,
        "bottleneck_counts": dict(sorted(bottleneck_counts.items())),
        "rows": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if markdown_path:
        write_qwen_markdown_report(report, markdown_path)
    return report


def _run_case(
    case: PublicProbeCase,
    *,
    knowledge_path: Path,
    reference_time: datetime,
    llama_server_url: str,
    writer: Callable[[str], str] | None,
    timeout_seconds: int,
    max_tokens: int,
) -> dict[str, object]:
    writer_state: dict[str, object] = {"called": False, "elapsed_seconds": None}

    def qwen_writer(prompt: str) -> str:
        writer_state["called"] = True
        started = time.perf_counter()
        try:
            if writer is not None:
                return writer(prompt)
            return generate_with_llama_server(
                prompt=prompt,
                base_url=llama_server_url,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
            )
        finally:
            writer_state["elapsed_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    result = answer_with_harness(
        case.question,
        mode="chat",
        backend="deterministic",
        knowledge_path=knowledge_path,
        generator=qwen_writer,
        question_time=reference_time,
    )
    elapsed_seconds = time.perf_counter() - started
    trace = result.trace
    actual_temporal_type = str(trace.temporal_type)
    expected_domain = DOMAINS[case.expected_label]
    label_match = trace.route_label == case.expected_label
    domain_match = trace.route_domain == expected_domain
    temporal_match = actual_temporal_type == case.expected_temporal_type
    output_status = str(result.output_status)
    bottleneck = _classify_bottleneck(
        label_match=label_match,
        temporal_match=temporal_match,
        output_status=output_status,
        trace=trace,
    )
    return {
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
        "trace_generation_backend": trace.generation_backend,
        "qwen_writer_called": bool(writer_state["called"]),
        "qwen_writer_elapsed_seconds": writer_state["elapsed_seconds"],
        "elapsed_seconds": elapsed_seconds,
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


def write_qwen_markdown_report(report: dict[str, object], output_path: Path) -> None:
    rows = report["rows"]
    assert isinstance(rows, list)
    lines = [
        "# Task 2 Public Probe Qwen Baseline",
        "",
        f"- 기준 시각: `{report['reference_time']}`",
        f"- writer backend: `{report['writer_backend']}`",
        f"- 질문 수: {report['question_count']}",
        f"- Task1 label match: {report['label_match_count']} / {report['question_count']} ({report['label_match_rate']:.2%})",
        f"- Temporal type match: {report['temporal_match_count']} / {report['question_count']} ({report['temporal_match_rate']:.2%})",
        f"- Answered: {report['answered_count']} / {report['question_count']} ({report['answered_rate']:.2%})",
        f"- Fail-closed: {report['fail_close_count']} / {report['question_count']} ({report['fail_close_rate']:.2%})",
        f"- Qwen writer called: {report['writer_called_count']} / {report['question_count']}",
        f"- Writer-called but blocked: {report['writer_blocked_count']}",
        f"- Bottlenecks: `{json.dumps(report['bottleneck_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "이 결과는 현재 harness를 통과한 Qwen writer baseline이며 최종 Task 2 성능 claim이 아니다.",
        "",
        "| ID | Label | Temporal | Status | Writer | Bottleneck | Failure |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        assert isinstance(row, dict)
        label = f"{row['actual_label']} / {row['expected_label']}"
        temporal = f"{row['actual_temporal_type']} / {row['expected_temporal_type']}"
        writer_called = "yes" if row["qwen_writer_called"] else "no"
        lines.append(
            "| {id} | {label} | {temporal} | {status} | {writer} | {bottleneck} | {failure} |".format(
                id=row["id"],
                label=_escape_md(label),
                temporal=_escape_md(temporal),
                status=_escape_md(str(row["output_status"])),
                writer=writer_called,
                bottleneck=_escape_md(str(row["bottleneck"])),
                failure=_escape_md(str(row["failure_reason"] or "")),
            )
        )
    lines.extend(["", "## Answers", ""])
    for index, row in enumerate(rows, start=1):
        assert isinstance(row, dict)
        lines.extend(
            [
                f"### {index}. {row['question']}",
                "",
                f"- id: `{row['id']}`",
                f"- status: `{row['output_status']}`",
                f"- qwen_writer_called: `{row['qwen_writer_called']}`",
                f"- retrieved_doc_ids: `{row['retrieved_doc_ids']}`",
                "",
                str(row["answer"]),
                "",
            ]
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Task 2 public probe through the Qwen llama-server writer.")
    parser.add_argument("--probe", type=Path, default=data_dir() / "gold" / "task2_public_probe_eval.json")
    parser.add_argument("--knowledge", type=Path, default=data_dir() / "knowledge_seed.json")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/evidence/task2-public-probe-qwen-baseline-2026-06-08.json"),
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("docs/task2_public_probe_qwen_baseline_2026_06_08.md"),
    )
    parser.add_argument("--llama-server-url", default=DEFAULT_LLAMA_SERVER_URL)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args()
    report = run_qwen_public_probe_baseline(
        probe_path=args.probe,
        knowledge_path=args.knowledge,
        output_path=args.output,
        markdown_path=args.markdown,
        llama_server_url=args.llama_server_url,
        timeout_seconds=args.timeout_seconds,
        max_tokens=args.max_tokens,
    )
    print(f"wrote {args.output}")
    print(f"wrote {args.markdown}")
    print(
        json.dumps(
            {
                "answered": report["answered_count"],
                "fail_closed": report["fail_close_count"],
                "label_match": report["label_match_count"],
                "temporal_match": report["temporal_match_count"],
                "writer_called": report["writer_called_count"],
                "writer_blocked": report["writer_blocked_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
