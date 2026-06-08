from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from nlp_term.chat.orchestrator import answer_with_harness
from nlp_term.chat.public_probe_experiment import _classify_bottleneck
from nlp_term.chat.public_probe_experiment import _rate
from nlp_term.paths import data_dir
from nlp_term.schemas import Domain
from nlp_term.validators import file_checksum, read_json


REFERENCE_TIME = datetime(2026, 6, 8, tzinfo=ZoneInfo("Asia/Seoul"))
DOMAINS: dict[int, Domain] = {
    0: "graduation",
    1: "notices",
    2: "academic_calendar",
    3: "dining",
    4: "shuttle",
}


def run_probe39_experiment(
    *,
    public_probe_path: Path,
    generalization_probe_path: Path,
    knowledge_path: Path,
    sample_output_path: Path,
    output_path: Path,
    markdown_path: Path,
    reference_time: datetime = REFERENCE_TIME,
) -> dict[str, object]:
    cases = build_probe39_cases(
        public_probe_path=public_probe_path,
        generalization_probe_path=generalization_probe_path,
    )
    _write_json(sample_output_path, cases)

    rows = []
    label_match_count = 0
    temporal_match_count = 0
    answered_count = 0
    fail_close_count = 0
    retrieval_top1_domain_match_count = 0
    retrieval_top3_domain_hit_count = 0
    bottleneck_counts: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()

    for case in cases:
        result = answer_with_harness(
            case["question"],
            mode="chat",
            backend="deterministic",
            knowledge_path=knowledge_path,
            question_time=reference_time,
            allowed_stages={"stage0", "stage1"},
        )
        trace = result.trace
        expected_label = int(case["expected_label"])
        expected_domain = str(case.get("expected_domain") or DOMAINS[expected_label])
        actual_temporal_type = str(trace.temporal_type)
        label_match = trace.route_label == expected_label
        temporal_match = actual_temporal_type == str(case["expected_temporal_type"])
        prefilter = trace.prefilter_retrieved_candidates
        top1_domain_match = bool(prefilter and str(prefilter[0].domain) == expected_domain)
        top3_domain_hit = any(str(candidate.domain) == expected_domain for candidate in prefilter[:3])
        bottleneck = _classify_bottleneck(
            label_match=label_match,
            temporal_match=temporal_match,
            output_status=str(result.output_status),
            trace=trace,
        )

        label_match_count += int(label_match)
        temporal_match_count += int(temporal_match)
        answered_count += int(str(result.output_status) == "answered")
        fail_close_count += int(str(result.output_status) == "fail_closed")
        retrieval_top1_domain_match_count += int(top1_domain_match)
        retrieval_top3_domain_hit_count += int(top3_domain_hit)
        bottleneck_counts[bottleneck] += 1
        domain_counts[expected_domain] += 1
        rows.append(
            {
                "id": case["id"],
                "source_set": case["source_set"],
                "question": case["question"],
                "expected_label": expected_label,
                "actual_label": trace.route_label,
                "label_match": label_match,
                "expected_domain": expected_domain,
                "actual_domain": str(trace.route_domain),
                "expected_temporal_type": case["expected_temporal_type"],
                "actual_temporal_type": actual_temporal_type,
                "temporal_match": temporal_match,
                "target_start": trace.target_start,
                "target_end": trace.target_end,
                "output_status": str(result.output_status),
                "evidence_sufficiency_status": str(trace.evidence_sufficiency_status),
                "fetch_decision": str(trace.fetch_decision),
                "answer_validation_status": str(trace.answer_validation_status),
                "retrieval_top1_domain_match": top1_domain_match,
                "retrieval_top3_domain_hit": top3_domain_hit,
                "prefilter_retrieved_candidates": [
                    {
                        "doc_id": candidate.doc_id,
                        "score": candidate.score,
                        "label": candidate.label,
                        "domain": str(candidate.domain),
                        "source_id": candidate.source_id,
                    }
                    for candidate in prefilter[:5]
                ],
                "postfilter_retrieved_doc_ids": [
                    candidate.doc_id for candidate in trace.postfilter_retrieved_candidates
                ],
                "selected_retrieved_doc_ids": trace.retrieved_doc_ids,
                "failure_reason": trace.failure_reason,
                "bottleneck": bottleneck,
                "answer": result.output.model,
            }
        )

    question_count = len(cases)
    report = {
        "evaluation_scope": "task2_probe39_trace_diagnosis",
        "evaluation_set_type": "public14_plus_generalization25",
        "dataset_origin": "discussion_fixed_probe_and_generalization_sample",
        "claim_level": "diagnostic",
        "final_performance_claim_allowed": False,
        "reference_time": reference_time.isoformat(),
        "sample_path": str(sample_output_path),
        "sample_checksum": file_checksum(sample_output_path),
        "public_probe_path": str(public_probe_path),
        "generalization_probe_path": str(generalization_probe_path),
        "knowledge_path": str(knowledge_path),
        "knowledge_checksum": file_checksum(knowledge_path),
        "question_count": question_count,
        "domain_counts": dict(sorted(domain_counts.items())),
        "label_match_count": label_match_count,
        "label_match_rate": _rate(label_match_count, question_count),
        "temporal_match_count": temporal_match_count,
        "temporal_match_rate": _rate(temporal_match_count, question_count),
        "retrieval_top1_domain_match_count": retrieval_top1_domain_match_count,
        "retrieval_top1_domain_match_rate": _rate(retrieval_top1_domain_match_count, question_count),
        "retrieval_top3_domain_hit_count": retrieval_top3_domain_hit_count,
        "retrieval_top3_domain_hit_rate": _rate(retrieval_top3_domain_hit_count, question_count),
        "answered_count": answered_count,
        "answered_rate": _rate(answered_count, question_count),
        "fail_close_count": fail_close_count,
        "fail_close_rate": _rate(fail_close_count, question_count),
        "bottleneck_counts": dict(sorted(bottleneck_counts.items())),
        "rows": rows,
    }
    _write_json(output_path, report)
    write_markdown_report(report, markdown_path)
    return report


def build_probe39_cases(*, public_probe_path: Path, generalization_probe_path: Path) -> list[dict[str, object]]:
    public_rows = read_json(public_probe_path)
    generalization_rows = read_json(generalization_probe_path)
    if not isinstance(public_rows, list) or not isinstance(generalization_rows, list):
        raise ValueError("probe inputs must be JSON lists")

    cases = []
    for row in public_rows:
        expected_label = int(row["expected_label"])
        cases.append(
            {
                "id": row["id"],
                "source_set": "public_probe",
                "question": row["question"],
                "expected_label": expected_label,
                "expected_domain": DOMAINS[expected_label],
                "expected_temporal_type": row["expected_temporal_type"],
            }
        )

    by_domain: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in generalization_rows:
        by_domain[str(row["expected_domain"])].append(row)
    for domain in ("graduation", "notices", "academic_calendar", "dining", "shuttle"):
        selected = by_domain[domain][:5]
        if len(selected) < 5:
            raise ValueError(f"generalization probe has fewer than 5 rows for {domain}")
        for row in selected:
            cases.append(
                {
                    "id": row["id"],
                    "source_set": "generalization_sample",
                    "question": row["question"],
                    "expected_label": int(row["expected_label"]),
                    "expected_domain": row["expected_domain"],
                    "expected_temporal_type": row["expected_temporal_type"],
                    "group": row.get("group"),
                }
            )
    return cases


def write_markdown_report(report: dict[str, object], output_path: Path) -> None:
    rows = report["rows"]
    assert isinstance(rows, list)
    lines = [
        "# Task 2 Probe 39 Harness Diagnosis",
        "",
        f"- 기준 시각: `{report['reference_time']}`",
        f"- 질문 수: {report['question_count']}",
        f"- 도메인 분포: `{json.dumps(report['domain_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Task 1 label match: {report['label_match_count']} / {report['question_count']} ({report['label_match_rate']:.2%})",
        f"- Temporal type match: {report['temporal_match_count']} / {report['question_count']} ({report['temporal_match_rate']:.2%})",
        f"- Retrieval top1 domain match: {report['retrieval_top1_domain_match_count']} / {report['question_count']} ({report['retrieval_top1_domain_match_rate']:.2%})",
        f"- Retrieval top3 domain hit: {report['retrieval_top3_domain_hit_count']} / {report['question_count']} ({report['retrieval_top3_domain_hit_rate']:.2%})",
        f"- Answered: {report['answered_count']} / {report['question_count']} ({report['answered_rate']:.2%})",
        f"- Fail-closed: {report['fail_close_count']} / {report['question_count']} ({report['fail_close_rate']:.2%})",
        f"- Bottlenecks: `{json.dumps(report['bottleneck_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "이 결과는 deterministic harness trace 진단이며 최종 Task 2 성능 claim이 아니다.",
        "",
        "| ID | Set | Domain | Label | Temporal | Retrieval | Status | Bottleneck | Failure |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        assert isinstance(row, dict)
        retrieval = f"top1={row['retrieval_top1_domain_match']}, top3={row['retrieval_top3_domain_hit']}"
        temporal = f"{row['actual_temporal_type']} / {row['expected_temporal_type']}"
        label = f"{row['actual_label']} / {row['expected_label']}"
        lines.append(
            "| {id} | {set} | {domain} | {label} | {temporal} | {retrieval} | {status} | {bottleneck} | {failure} |".format(
                id=_escape_md(str(row["id"])),
                set=_escape_md(str(row["source_set"])),
                domain=_escape_md(str(row["expected_domain"])),
                label=_escape_md(label),
                temporal=_escape_md(temporal),
                retrieval=_escape_md(retrieval),
                status=_escape_md(str(row["output_status"])),
                bottleneck=_escape_md(str(row["bottleneck"])),
                failure=_escape_md(str(row["failure_reason"] or "")),
            )
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run 14 public probes plus 25 sampled generalization probes.")
    parser.add_argument("--public-probe", type=Path, default=data_dir() / "gold" / "task2_public_probe_eval.json")
    parser.add_argument(
        "--generalization-probe",
        type=Path,
        default=data_dir() / "gold" / "task2_generalization_probe.json",
    )
    parser.add_argument("--knowledge", type=Path, default=data_dir() / "knowledge_seed.json")
    parser.add_argument("--sample-output", type=Path, default=data_dir() / "gold" / "task2_probe39_eval.json")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/evidence/task2-probe39-harness-2026-06-08.json"),
    )
    parser.add_argument("--markdown", type=Path, default=Path("docs/task2_probe39_report_2026_06_08.md"))
    args = parser.parse_args()
    run_probe39_experiment(
        public_probe_path=args.public_probe,
        generalization_probe_path=args.generalization_probe,
        knowledge_path=args.knowledge,
        sample_output_path=args.sample_output,
        output_path=args.output,
        markdown_path=args.markdown,
    )
    print(f"wrote {args.sample_output}")
    print(f"wrote {args.output}")
    print(f"wrote {args.markdown}")


if __name__ == "__main__":
    main()
