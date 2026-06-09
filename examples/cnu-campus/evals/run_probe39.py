"""CNU 39-question probe evaluation runner with multi-mode retrieval comparison."""

import json
import argparse
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from sutra.config import load_config
from sutra.documents import load_documents
from sutra.retrieval import retrieve

from embedding_retrieval import (
    check_deps,
    load_embedding_model,
    get_cache_dir,
    get_cached_embeddings,
    dense_retrieve,
    hybrid_combine,
    get_model_name,
    get_model_device,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]


# ── Utilities ──────────────────────────────────────────────────────────


def get_git_info():
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--short"], cwd=REPO_ROOT, text=True
        ).strip()
        return commit, status
    except Exception:
        return "unknown", "unknown"


def check_backend(base_url):
    try:
        import requests
        resp = requests.get(f"{base_url}/health", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def get_docs_check(workspace_path):
    try:
        output = subprocess.check_output(
            [
                "uv",
                "run",
                "python",
                "-m",
                "sutra.cli",
                "docs",
                "check",
                "--workspace",
                str(workspace_path),
                "--json",
            ],
            cwd=REPO_ROOT,
            text=True,
        )
        return json.loads(output)
    except Exception:
        return {"error": "failed to run docs check"}


def resolve_path(path: str) -> Path:
    path_obj = Path(path)
    if path_obj.is_absolute():
        return path_obj
    return REPO_ROOT / path_obj


def build_base_metadata(
    workspace_path, questions_path, questions, docs_check, config
):
    git_commit, git_status = get_git_info()
    counts = {}
    for doc in documents_for_counts(load_documents(config)):
        domain = doc["domain"]
        counts[domain] = counts.get(domain, 0) + 1

    return {
        "git_commit": git_commit,
        "git_status_short": git_status or "(clean)",
        "workspace_path": str(workspace_path),
        "corpus_doc_counts": counts,
        "docs_check_result": docs_check,
        "question_source_path": str(questions_path),
        "question_count": len(questions),
        "full_generation_available": check_backend(config.runtime.base_url),
        "backend_url": config.runtime.base_url,
        "backend_model": config.runtime.model,
        "run_started_at": datetime.now().isoformat(),
    }


def documents_for_counts(documents):
    for doc in documents:
        domain = doc.metadata.get("domain")
        if not domain:
            if doc.id.startswith("dining_"):
                domain = "dining"
            elif doc.id.startswith("shuttle_"):
                domain = "shuttle"
            elif doc.id.startswith("calendar_"):
                domain = "academic_calendar"
            elif doc.id.startswith("graduation_"):
                domain = "graduation"
            else:
                domain = "unknown"
        yield {"domain": domain, "id": doc.id}


def infer_domain(item_id: str) -> str:
    if "dining" in item_id:
        return "dining"
    if "shuttle" in item_id:
        return "shuttle"
    if "calendar" in item_id:
        return "academic_calendar"
    if "graduation" in item_id:
        return "graduation"
    if "notice" in item_id:
        return "notices"
    return "unknown"


def check_domain_in_results(retrieved_ids, expected_domain):
    if not expected_domain:
        return False, False
    domains = [infer_domain(i) for i in retrieved_ids]
    in_top1 = domains[0] == expected_domain if domains else False
    in_topk = expected_domain in domains
    return in_top1, in_topk


def load_previous_trace():
    previous_path = REPO_ROOT / "tmp" / "eval_39_clean_corpus_trace.json"
    if not previous_path.exists():
        return {}
    try:
        data = json.loads(previous_path.read_text("utf-8"))
        return {t["question_id"]: t["failure_type"] for t in data.get("traces", [])}
    except Exception:
        return {}


# ── CLI ───────────────────────────────────────────────────────────────


RETRIEVAL_CHOICES = ["lexical", "dense_qwen3", "hybrid_simple", "compare"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run CNU 39-question clean-corpus evaluation with retrieval comparison."
    )
    parser.add_argument(
        "--workspace",
        default="examples/cnu-campus/sutra.toml",
        help="Workspace config path.",
    )
    parser.add_argument(
        "--questions",
        default="data/gold/task2_probe39_eval.json",
        help="Probe question JSON path.",
    )
    parser.add_argument(
        "--trace",
        default="tmp/eval_39_clean_corpus_trace.json",
        help="Trace output path (non-compare modes).",
    )
    parser.add_argument(
        "--report",
        default="tmp/eval_39_clean_corpus_report.md",
        help="Report output path (non-compare modes).",
    )
    parser.add_argument(
        "--retrieval",
        choices=RETRIEVAL_CHOICES,
        default="lexical",
        help="Retrieval mode.",
    )
    return parser.parse_args()


# ── Entry Point ────────────────────────────────────────────────────────


def main():
    args = parse_args()
    workspace_path = resolve_path(args.workspace)
    questions_path = resolve_path(args.questions)

    print(f"Loading workspace: {workspace_path}")
    config = load_config(workspace_path)
    documents = load_documents(config)

    print(f"Loading questions: {questions_path}")
    with open(questions_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"Retrieval mode: {args.retrieval}")
    docs_check = get_docs_check(workspace_path)

    if args.retrieval == "lexical":
        run_lexical(args, config, documents, questions, docs_check)
    elif args.retrieval == "dense_qwen3":
        run_dense(args, config, documents, questions, docs_check)
    elif args.retrieval == "hybrid_simple":
        run_hybrid(args, config, documents, questions, docs_check)
    elif args.retrieval == "compare":
        run_compare(args, config, documents, questions, docs_check)
    else:
        print(f"Unknown retrieval mode: {args.retrieval}")
        sys.exit(1)


# ── Mode Runners ──────────────────────────────────────────────────────


def run_lexical(args, config, documents, questions, docs_check):
    output_trace_path = resolve_path(args.trace)
    output_report_path = resolve_path(args.report)
    output_trace_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = build_base_metadata(
        resolve_path(args.workspace), resolve_path(args.questions),
        questions, docs_check, config,
    )
    metadata["retrieval_mode"] = "lexical"

    traces = run_questions_lexical(questions, documents, config, metadata)

    metadata["run_finished_at"] = datetime.now().isoformat()
    with open(output_trace_path, "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "traces": traces}, f, ensure_ascii=False, indent=2)

    generate_report(metadata, traces, output_report_path)
    print(f"Done. Trace: {output_trace_path}")
    print(f"Report: {output_report_path}")


def run_dense(args, config, documents, questions, docs_check):
    dense_status = check_deps()
    if not dense_status["sentence_transformers_available"]:
        print("=" * 60)
        print("ERROR: Dense retrieval unavailable.")
        print("  sentence-transformers not installed.")
        print("  Install: uv pip install sentence-transformers>=2.7.0")
        print("  Also ensure: transformers>=4.51.0 is available.")
        print("=" * 60)
        sys.exit(1)

    output_trace_path = resolve_path(args.trace)
    output_report_path = resolve_path(args.report)
    output_trace_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = build_base_metadata(
        resolve_path(args.workspace), resolve_path(args.questions),
        questions, docs_check, config,
    )
    metadata["retrieval_mode"] = "dense_qwen3"
    metadata["dense_available"] = True
    metadata["embedding_dependency_status"] = dense_status

    model = load_embedding_model()
    cache_dir = get_cache_dir(resolve_path(args.workspace))
    embeddings, cache_meta = get_cached_embeddings(documents, model, cache_dir)

    metadata["embedding_model"] = get_model_name(model)
    metadata["embedding_device"] = get_model_device(model)
    metadata["embedding_dimension"] = int(embeddings.shape[1])
    metadata["embedding_cache_path"] = str(cache_dir)
    metadata["embedding_cache_hit"] = cache_meta.get("cache_hit", False)

    traces = run_questions_dense(questions, documents, model, embeddings, config)

    metadata["run_finished_at"] = datetime.now().isoformat()
    with open(output_trace_path, "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "traces": traces}, f, ensure_ascii=False, indent=2)

    generate_report(metadata, traces, output_report_path)
    print(f"Done. Trace: {output_trace_path}")
    print(f"Report: {output_report_path}")


def run_hybrid(args, config, documents, questions, docs_check):
    dense_status = check_deps()
    if not dense_status["sentence_transformers_available"]:
        print("=" * 60)
        print("ERROR: Hybrid retrieval unavailable (deps missing).")
        print("  sentence-transformers not installed.")
        print("  Install: uv pip install sentence-transformers>=2.7.0")
        print("  Also ensure: transformers>=4.51.0 is available.")
        print("=" * 60)
        sys.exit(1)

    output_trace_path = resolve_path(args.trace)
    output_report_path = resolve_path(args.report)
    output_trace_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = build_base_metadata(
        resolve_path(args.workspace), resolve_path(args.questions),
        questions, docs_check, config,
    )
    metadata["retrieval_mode"] = "hybrid_simple"
    metadata["dense_available"] = True
    metadata["embedding_dependency_status"] = dense_status
    metadata["hybrid_weights"] = {"lexical": 0.5, "dense": 0.5}

    model = load_embedding_model()
    cache_dir = get_cache_dir(resolve_path(args.workspace))
    embeddings, cache_meta = get_cached_embeddings(documents, model, cache_dir)

    metadata["embedding_model"] = get_model_name(model)
    metadata["embedding_device"] = get_model_device(model)
    metadata["embedding_dimension"] = int(embeddings.shape[1])
    metadata["embedding_cache_path"] = str(cache_dir)
    metadata["embedding_cache_hit"] = cache_meta.get("cache_hit", False)

    traces = run_questions_hybrid(
        questions, documents, model, embeddings, config, metadata
    )

    metadata["run_finished_at"] = datetime.now().isoformat()
    with open(output_trace_path, "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "traces": traces}, f, ensure_ascii=False, indent=2)

    generate_report(metadata, traces, output_report_path)
    print(f"Done. Trace: {output_trace_path}")
    print(f"Report: {output_report_path}")


def run_compare(args, config, documents, questions, docs_check):
    output_trace_path = REPO_ROOT / "tmp" / "eval_39_retrieval_compare_trace.json"
    output_report_path = REPO_ROOT / "tmp" / "eval_39_retrieval_compare_report.md"
    output_trace_path.parent.mkdir(parents=True, exist_ok=True)

    dense_status = check_deps()
    previous_labels = load_previous_trace()

    metadata = build_base_metadata(
        resolve_path(args.workspace), resolve_path(args.questions),
        questions, docs_check, config,
    )
    metadata["retrieval_mode"] = "compare"
    metadata["retrieval_modes_run"] = ["lexical"]
    metadata["dense_available"] = dense_status["sentence_transformers_available"]
    metadata["embedding_dependency_status"] = dense_status
    metadata["embedding_model"] = None
    metadata["embedding_device"] = None
    metadata["embedding_dimension"] = None
    metadata["embedding_cache_path"] = None
    metadata["embedding_cache_hit"] = None

    model = None
    embeddings = None
    cache_meta = {}

    if dense_status["sentence_transformers_available"]:
        metadata["retrieval_modes_run"].append("dense_qwen3")
        metadata["retrieval_modes_run"].append("hybrid_simple")
        try:
            model = load_embedding_model()
            cache_dir = get_cache_dir(resolve_path(args.workspace))
            embeddings, cache_meta = get_cached_embeddings(documents, model, cache_dir)
            metadata["embedding_model"] = get_model_name(model)
            metadata["embedding_device"] = get_model_device(model)
            metadata["embedding_dimension"] = int(embeddings.shape[1])
            metadata["embedding_cache_path"] = str(cache_dir)
            metadata["embedding_cache_hit"] = cache_meta.get("cache_hit", False)
        except Exception as e:
            metadata["dense_available"] = False
            metadata["dense_unavailable_reason"] = f"Model load failed: {e}"
            metadata["retrieval_modes_run"] = ["lexical"]
    else:
        metadata["dense_unavailable_reason"] = (
            "sentence-transformers not installed. "
            "Install: uv pip install sentence-transformers>=2.7.0"
        )

    traces = run_questions_compare(
        questions, documents, config, model, embeddings,
        metadata, previous_labels,
    )

    metadata["run_finished_at"] = datetime.now().isoformat()

    with open(output_trace_path, "w", encoding="utf-8") as f:
        json.dump(
            {"metadata": metadata, "traces": traces},
            f, ensure_ascii=False, indent=2,
        )

    generate_compare_report(metadata, traces, output_report_path)
    print(f"Done. Compare trace: {output_trace_path}")
    print(f"Compare report: {output_report_path}")


# ── Question Processing ────────────────────────────────────────────────


def process_question_common(q_data, expected_domain):
    return {
        "question_id": q_data["id"],
        "question": q_data["question"],
        "expected_or_likely_domain": expected_domain or "unknown",
    }


def run_questions_lexical(questions, documents, config, metadata):
    traces = []
    for q_data in questions:
        q_text = q_data["question"]
        expected_domain = q_data.get("expected_domain")
        print(f"[{q_data['id']}] {q_text[:40]}...")

        evidence_pack = retrieve(q_text, documents, config)
        base = process_question_common(q_data, expected_domain)
        base["retrieved_doc_ids"] = [item.id for item in evidence_pack.items]
        base["retrieved_titles"] = [item.title for item in evidence_pack.items]
        base["retrieved_scores"] = [float(item.score) for item in evidence_pack.items]
        base["evidence_preview"] = (
            evidence_pack.items[0].text[:300] if evidence_pack.items else ""
        )
        base["failure_type"], base["diagnostic_note"] = classify_failure(
            base["retrieved_doc_ids"], expected_domain
        )
        traces.append(base)
    return traces


def run_questions_dense(questions, documents, model, embeddings, config):
    traces = []
    for q_data in questions:
        q_text = q_data["question"]
        expected_domain = q_data.get("expected_domain")
        print(f"[{q_data['id']}] dense: {q_text[:40]}...")

        dense_pack = dense_retrieve(q_text, documents, model, embeddings, config)
        base = process_question_common(q_data, expected_domain)
        base["retrieved_doc_ids"] = [item.id for item in dense_pack.items]
        base["retrieved_titles"] = [item.title for item in dense_pack.items]
        base["retrieved_scores"] = [float(item.score) for item in dense_pack.items]
        base["evidence_preview"] = (
            dense_pack.items[0].text[:300] if dense_pack.items else ""
        )
        base["failure_type"], base["diagnostic_note"] = classify_failure(
            base["retrieved_doc_ids"], expected_domain
        )
        traces.append(base)
    return traces


def run_questions_hybrid(
    questions, documents, model, embeddings, config, metadata
):
    traces = []
    for q_data in questions:
        q_text = q_data["question"]
        expected_domain = q_data.get("expected_domain")
        print(f"[{q_data['id']}] hybrid: {q_text[:40]}...")

        lexical_pack = retrieve(q_text, documents, config)
        dense_pack = dense_retrieve(q_text, documents, model, embeddings, config)
        hybrid_pack = hybrid_combine(lexical_pack, dense_pack, config)

        base = process_question_common(q_data, expected_domain)
        base["retrieved_doc_ids"] = [item.id for item in hybrid_pack.items]
        base["retrieved_titles"] = [item.title for item in hybrid_pack.items]
        base["retrieved_scores"] = [float(item.score) for item in hybrid_pack.items]
        base["evidence_preview"] = (
            hybrid_pack.items[0].text[:300] if hybrid_pack.items else ""
        )

        base["lexical_raw_ids"] = [item.id for item in lexical_pack.items]
        base["dense_raw_ids"] = [item.id for item in dense_pack.items]
        base["failure_type"], base["diagnostic_note"] = classify_failure(
            base["retrieved_doc_ids"], expected_domain
        )
        traces.append(base)
    return traces


def run_questions_compare(
    questions, documents, config, model, embeddings,
    metadata, previous_labels,
):
    traces = []
    dense_available = model is not None and embeddings is not None

    for q_data in questions:
        q_text = q_data["question"]
        expected_domain = q_data.get("expected_domain")
        print(f"[{q_data['id']}] compare: {q_text[:40]}...")

        entry = process_question_common(q_data, expected_domain)

        q_id = q_data["id"]
        entry["previous_failure_label"] = previous_labels.get(q_id)

        # Lexical
        lexical_pack = retrieve(q_text, documents, config)
        entry["lexical"] = {
            "retrieved_doc_ids": [item.id for item in lexical_pack.items],
            "retrieved_titles": [item.title for item in lexical_pack.items],
            "retrieved_scores": [float(item.score) for item in lexical_pack.items],
        }

        l_top1, l_topk = check_domain_in_results(
            entry["lexical"]["retrieved_doc_ids"], expected_domain
        )
        entry["lexical_expected_domain_in_top1"] = l_top1
        entry["lexical_expected_domain_in_topk"] = l_topk

        # Dense
        if dense_available:
            dense_pack = dense_retrieve(
                q_text, documents, model, embeddings, config
            )
            entry["dense"] = {
                "retrieved_doc_ids": [item.id for item in dense_pack.items],
                "retrieved_titles": [item.title for item in dense_pack.items],
                "retrieved_scores": [float(item.score) for item in dense_pack.items],
            }
            d_top1, d_topk = check_domain_in_results(
                entry["dense"]["retrieved_doc_ids"], expected_domain
            )
            entry["dense_expected_domain_in_top1"] = d_top1
            entry["dense_expected_domain_in_topk"] = d_topk

            # Hybrid
            hybrid_pack = hybrid_combine(lexical_pack, dense_pack, config)
            entry["hybrid"] = {
                "retrieved_doc_ids": [item.id for item in hybrid_pack.items],
                "retrieved_titles": [item.title for item in hybrid_pack.items],
                "retrieved_scores": [float(item.score) for item in hybrid_pack.items],
            }
            h_top1, h_topk = check_domain_in_results(
                entry["hybrid"]["retrieved_doc_ids"], expected_domain
            )
            entry["hybrid_expected_domain_in_top1"] = h_top1
            entry["hybrid_expected_domain_in_topk"] = h_topk
        else:
            entry["dense"] = None
            entry["dense_expected_domain_in_top1"] = None
            entry["dense_expected_domain_in_topk"] = None
            entry["hybrid"] = None
            entry["hybrid_expected_domain_in_top1"] = None
            entry["hybrid_expected_domain_in_topk"] = None

        # Improvement / regression flag
        entry["improved"] = False
        entry["regressed"] = False
        entry["diagnostic_note"] = ""

        prev = entry.get("previous_failure_label")
        if dense_available and prev:
            lex_fail = entry["lexical_expected_domain_in_topk"]
            dense_fail = entry["dense_expected_domain_in_topk"]
            hybrid_fail = entry["hybrid_expected_domain_in_topk"]

            if prev == "retrieval_miss":
                if dense_fail or hybrid_fail:
                    entry["improved"] = True
                    entry["diagnostic_note"] = (
                        "Previously retrieval_miss; dense/hybrid found expected domain."
                    )
            if prev == "ok":
                if not lex_fail and (not dense_fail or not hybrid_fail):
                    entry["regressed"] = True
                    entry["diagnostic_note"] = (
                        "Previously ok; dense/hybrid lost expected domain."
                    )

        traces.append(entry)

    return traces


# ── Classification ────────────────────────────────────────────────────


def classify_failure(retrieved_ids, expected_domain):
    if not retrieved_ids:
        return "data_missing", "No evidence found."
    if not expected_domain:
        return "ok", ""
    domains = [infer_domain(i) for i in retrieved_ids]
    if expected_domain not in domains:
        return (
            "retrieval_miss",
            f"Expected {expected_domain} but got {set(domains)}.",
        )
    return "ok", ""


# ── Report Generation (non-compare) ────────────────────────────────────


def generate_report(metadata, traces, report_path):
    failure_counts = {}
    for t in traces:
        ft = t.get("failure_type", "unknown")
        failure_counts[ft] = failure_counts.get(ft, 0) + 1

    lines = [
        "# Evaluation Report: 39-Question Clean Corpus Run",
        "",
        "## 1. Run Metadata",
        f"- **Date:** {metadata['run_started_at']}",
        f"- **Git Commit:** `{metadata['git_commit']}`",
        f"- **Git Status:** `{metadata['git_status_short'] or 'clean'}`",
        f"- **Workspace:** `{metadata['workspace_path']}`",
        f"- **Retrieval Mode:** `{metadata.get('retrieval_mode', 'lexical')}`",
        "",
        "## 2. Corpus State",
        "| Domain | Count |",
        "| :--- | :--- |",
    ]
    for domain, count in sorted(metadata["corpus_doc_counts"].items()):
        lines.append(f"| {domain} | {count} |")

    lines.extend([
        "",
        "## 3. Failure Summary",
        "| Failure Type | Count |",
        "| :--- | :--- |",
    ])
    taxonomy = [
        "ok", "data_missing", "retrieval_miss", "generation_issue",
        "ocr_gap", "ambiguous_question", "classifier_issue",
        "tool_needed", "evaluation_unclear",
    ]
    for ft in taxonomy:
        lines.append(f"| `{ft}` | {failure_counts.get(ft, 0)} |")

    lines.extend([
        "",
        "## 4. Question Breakdown",
        "| ID | Question | Top Retrieval | Failure Type | Note |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ])
    for t in traces:
        top = t.get("retrieved_titles", ["NONE"])[0] if t.get("retrieved_titles") else "NONE"
        note = t.get("diagnostic_note", "").replace("\n", " ")
        lines.append(
            f"| {t['question_id']} | {t['question']} | {top} | "
            f"`{t.get('failure_type', '?')}` | {note} |"
        )

    lines.extend([
        "",
        "## 5. Recommended Next Fixes",
        "1. **Data Expansion**: Address `data_missing` cases by crawling missing sections.",
        "2. **Retrieval Tuning**: Fix `retrieval_miss` by adjusting weights or hybrid search.",
        "3. **OCR/Page 3**: Review graduation requirements if OCR gaps are suspected.",
    ])

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ── Compare Report ─────────────────────────────────────────────────────


SPOT_CHECK_IDS = [
    "public_probe_02",
    "public_probe_11",
    "public_probe_03",
    "public_probe_13",
    "gp046",
    "public_probe_04",
    "gp049",
    "gp050",
    "gp051",
    "public_probe_01",
    "gp001",
    "gp002",
    "gp004",
]

SPOT_CHECK_QUESTIONS = {
    "public_probe_02": "수강신청",
    "public_probe_11": "종강",
    "public_probe_03": "오늘 학식",
    "public_probe_13": "다음주 화요일 2학생회관",
    "gp046": "다음주 화요일 2학생회관",
    "public_probe_04": "다음주 셔틀 정상 운행",
    "gp049": "다음주 셔틀 정상 운행",
    "gp050": "오늘 셔틀 정상 운행",
    "gp051": "월평역 셔틀",
    "public_probe_01": "컴퓨터인공지능학부 졸업요건",
    "gp001": "컴퓨터인공지능학부 졸업요건",
    "gp002": "컴퓨터인공지능학부 졸업요건",
    "gp004": "컴퓨터인공지능학부 졸업요건",
}


def generate_compare_report(metadata, traces, report_path):
    dense_avail = metadata["dense_available"]
    total = len(traces)

    # Count metrics
    lex_top1_ok = sum(1 for t in traces if t.get("lexical_expected_domain_in_top1"))
    lex_topk_ok = sum(1 for t in traces if t.get("lexical_expected_domain_in_topk"))
    dense_top1_ok = sum(
        1 for t in traces if t.get("dense_expected_domain_in_top1") is True
    )
    dense_topk_ok = sum(
        1 for t in traces if t.get("dense_expected_domain_in_topk") is True
    )
    hybrid_top1_ok = sum(
        1 for t in traces if t.get("hybrid_expected_domain_in_top1") is True
    )
    hybrid_topk_ok = sum(
        1 for t in traces if t.get("hybrid_expected_domain_in_topk") is True
    )

    # Improvement / regression counts (only for questions with previous failure label)
    improved = sum(1 for t in traces if t.get("improved"))
    regressed = sum(1 for t in traces if t.get("regressed"))
    prev_retrieval_miss = sum(
        1 for t in traces if t.get("previous_failure_label") == "retrieval_miss"
    )
    prev_ok = sum(1 for t in traces if t.get("previous_failure_label") == "ok")

    lines = [
        "# Compare Report: Qwen3 Embedding Retrieval vs Lexical Baseline",
        "",
        "## 1. Run Metadata",
        f"- **Date:** {metadata['run_started_at']}",
        f"- **Finished:** {metadata['run_finished_at']}",
        f"- **Git Commit:** `{metadata['git_commit']}`",
        f"- **Git Status:** `{metadata['git_status_short']}`",
        f"- **Workspace:** `{metadata['workspace_path']}`",
        f"- **Questions:** {metadata['question_count']}",
        f"- **Corpus:** {metadata['corpus_doc_counts']}",
        f"- **Retrieval Modes:** {metadata['retrieval_modes_run']}",
        "",
        "## 2. Dependency / Backend Availability",
        f"- **sentence-transformers:** {metadata['embedding_dependency_status']['sentence_transformers_available']}",
        f"  - version: {metadata['embedding_dependency_status']['sentence_transformers_version']}",
        f"- **transformers:** version {metadata['embedding_dependency_status']['transformers_version']}",
        f"- **Dense available:** {metadata['dense_available']}",
    ]

    if not dense_avail:
        reason = metadata.get("dense_unavailable_reason", "unknown")
        lines.append(f"- **Dense unavailable reason:** {reason}")
        lines.append("")
        lines.append("> Note: Dense and hybrid modes did not run. Only lexical results below.")
    else:
        lines.extend([
            f"- **Embedding model:** {metadata['embedding_model']}",
            f"- **Device:** {metadata['embedding_device']}",
            f"- **Dimension:** {metadata['embedding_dimension']}",
            "",
            "## 3. Cache Summary",
            f"- **Cache path:** {metadata['embedding_cache_path']}",
            f"- **Cache hit:** {metadata['embedding_cache_hit']}",
        ])

    lines.extend([
        "",
        "## 4. Mode Comparison Summary",
        "| Metric | Lexical | Dense | Hybrid |",
        "| :--- | :--- | :--- | :--- |",
        f"| Expected domain in top-1 | {lex_top1_ok}/{total} | "
        f"{dense_top1_ok}/{total if dense_avail else 'N/A'} | "
        f"{hybrid_top1_ok}/{total if dense_avail else 'N/A'} |",
        f"| Expected domain in top-k | {lex_topk_ok}/{total} | "
        f"{dense_topk_ok}/{total if dense_avail else 'N/A'} | "
        f"{hybrid_topk_ok}/{total if dense_avail else 'N/A'} |",
        "",
        "### Improvement / Regression",
        f"- Previously `retrieval_miss` questions: {prev_retrieval_miss}",
        f"- Previously `ok` questions: {prev_ok}",
        f"- Improved (retrieval_miss → found by dense/hybrid): {improved}",
        f"- Regressed (ok → missed by dense/hybrid): {regressed}",
        "",
        "## 5. Per-Question Comparison",
        "| ID | Question | Expected | Lex top1 | Lex topk | Dense top1 | Dense topk | Hybrid top1 | Hybrid topk | Improved | Regressed | Note |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ])

    for t in traces:
        qid = t["question_id"]
        qtext = t["question"][:25]
        exp = t.get("expected_or_likely_domain", "?")[:12]
        l1 = "✓" if t.get("lexical_expected_domain_in_top1") else "✗"
        lk = "✓" if t.get("lexical_expected_domain_in_topk") else "✗"
        if dense_avail:
            d1 = "✓" if t.get("dense_expected_domain_in_top1") else "✗"
            dk = "✓" if t.get("dense_expected_domain_in_topk") else "✗"
            h1 = "✓" if t.get("hybrid_expected_domain_in_top1") else "✗"
            hk = "✓" if t.get("hybrid_expected_domain_in_topk") else "✗"
        else:
            d1 = dk = h1 = hk = "N/A"
        imp = "✓" if t.get("improved") else ""
        reg = "✓" if t.get("regressed") else ""
        note = t.get("diagnostic_note", "")[:40]
        lines.append(
            f"| {qid} | {qtext} | {exp} | {l1} | {lk} | {d1} | {dk} | "
            f"{h1} | {hk} | {imp} | {reg} | {note} |"
        )

    lines.extend([
        "",
        "## 6. Manual Spot-Check for Temporal / Exact-Match Questions",
        "",
        "The following questions require verifying that the *specific correct document* "
        "(not just any document from the expected domain) was retrieved.",
        "",
        "| Question | Topic | Lexical Top-1 | Dense Top-1 | Hybrid Top-1 | Correct Doc Expected |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ])

    # Spot check section
    spot_ids = [
        ("public_probe_02", "수강신청", "calendar_event_2026_0007"),
        ("public_probe_11", "종강", "calendar_event_2026_0035"),
        ("public_probe_03", "오늘 학식", "dining_2026-06-09"),
        ("public_probe_13", "다음주 화요일 2학생회관", "dining (future)"),
        ("gp046", "다음주 화요일 2학생회관", "dining (future)"),
        ("gp050", "오늘 셔틀 정상 운행", "shuttle route doc"),
        ("gp051", "월평역 셔틀", "shuttle route doc"),
        ("public_probe_01", "컴퓨터인공지능학부 졸업요건", "graduation page 1"),
        ("gp001", "컴퓨터인공지능학부 졸업요건", "graduation page 1"),
    ]

    trace_map = {t["question_id"]: t for t in traces}
    for qid, topic, expected_doc in spot_ids:
        t = trace_map.get(qid)
        if not t:
            lines.append(f"| {qid} | {topic} | N/A | N/A | N/A | {expected_doc} |")
            continue

        lex_ids = (t.get("lexical") or {}).get("retrieved_doc_ids", [])
        lex_top1 = lex_ids[0] if lex_ids else "(empty)"
        dense_top1 = "(N/A)"
        hybrid_top1 = "(N/A)"
        if dense_avail and t.get("dense"):
            d_ids = t["dense"]["retrieved_doc_ids"]
            dense_top1 = d_ids[0] if d_ids else "(empty)"
        if dense_avail and t.get("hybrid"):
            h_ids = t["hybrid"]["retrieved_doc_ids"]
            hybrid_top1 = h_ids[0] if h_ids else "(empty)"

        lines.append(
            f"| {qid} | {topic} | `{lex_top1}` | `{dense_top1}` | "
            f"`{hybrid_top1}` | {expected_doc} |"
        )

    lines.extend([
        "",
        "### Spot-Check Notes",
        "- **수강신청 (public_probe_02):** Expected doc is `calendar_event_2026_0007` (2026 정규수강신청).",
        "  - Lexical currently retrieves shuttle/graduation docs (score 1.0 ties).",
        "  - Dense should theoretically rank the calendar event higher due to semantic match.",
        "- **종강 (public_probe_11):** Expected doc is `calendar_event_2026_0035` (하기종강).",
        "- **오늘 학식 (public_probe_03):** Today is 2026-06-09. Check if `dining_2026-06-09_*` is retrieved.",
        "  - If no dining doc found, check whether the correct date's menu is present.",
        "- **다음주 화요일 2학생회관 (public_probe_13 / gp046):** No future dining data.",
        "  - This is a data gap (`data_missing`), not repairable by retrieval mode.",
        "- **셔틀 정상 운행 (gp050):** Lexical correctly retrieves shuttle docs.",
        "  - Check whether dense/hybrid regresses by ranking non-shuttle docs higher.",
        "- **컴퓨터인공지능학부 졸업요건 (public_probe_01, gp001):** Lexical correctly finds graduation page 1.",
        "  - Ensure dense/hybrid does not regress.",
        "",
        "## 7. Final Recommendation",
    ])

    if not dense_avail:
        lines.extend([
            "**Dense retrieval was unavailable.**",
            "",
            "> Recommendation: **Inconclusive — needs dependency setup.**",
            ">",
            "> To evaluate Qwen3 embedding retrieval:",
            "> 1. Install: `uv pip install sentence-transformers>=2.7.0`",
            "> 2. Re-run: `uv run python examples/cnu-campus/evals/run_probe39.py --retrieval compare`",
            ">",
            "> Until then, **keep lexical** as the active retrieval mode.",
        ])
    else:
        # Simple heuristic recommendation
        if dense_topk_ok > lex_topk_ok and regressed <= 1:
            lines.append(
                "**Dense Qwen3 embedding improves retrieval over lexical baseline.**\n"
                "> Recommendation: **Use hybrid** (0.5 lexical + 0.5 dense). "
                "Dense alone may regress some previously-ok cases, but hybrid balances both."
            )
        elif dense_topk_ok > lex_topk_ok:
            lines.append(
                "**Dense improves some cases but regresses others.**\n"
                "> Recommendation: **Use hybrid with caution** — "
                "monitor regression cases before promoting to default."
            )
        else:
            lines.append(
                "**Dense Qwen3 does not significantly improve over lexical for this corpus.**\n"
                "> Recommendation: **Keep lexical** as default. "
                "Consider smaller Korean-specific embedding models."
            )

    lines.extend([
        "",
        "---",
        "",
        "*Report generated by run_probe39.py compare mode*",
    ])

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
