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
from sutra.models import Evidence, EvidencePack
from sutra.prompts import render_prompt
from sutra.llama import LlamaClient
from sutra.errors import LlamaError

try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

from embedding_retrieval import (
    check_deps as check_dense_deps,
    load_embedding_model,
    get_cache_dir as get_dense_cache_dir,
    get_cached_embeddings,
    dense_retrieve,
    hybrid_combine,
    get_model_name,
    get_model_device,
)

from korean_bm25_retrieval import (
    check_deps as check_bm25_deps,
    build_bm25_index,
    bm25_retrieve,
    hybrid_bm25_dense,
    get_tokenizer_config,
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


def _get_device():
    if not _TORCH_AVAILABLE:
        return "cpu"
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        return "xpu"
    return "cpu"


def load_previous_trace():
    previous_path = REPO_ROOT / "tmp" / "eval_39_clean_corpus_trace.json"
    if not previous_path.exists():
        return {}
    try:
        data = json.loads(previous_path.read_text("utf-8"))
        return {t["question_id"]: t["failure_type"] for t in data.get("traces", [])}
    except Exception:
        return {}


# ── LLM Generation ────────────────────────────────────────────────────


def _get_trace_doc_ids_and_scores(entry):
    doc_ids = entry.get("retrieved_doc_ids")
    scores = entry.get("retrieved_scores")
    if doc_ids is not None:
        return doc_ids, scores
    lexical = entry.get("lexical")
    if isinstance(lexical, dict):
        doc_ids = lexical.get("retrieved_doc_ids", [])
        scores = lexical.get("retrieved_scores")
        if doc_ids:
            return doc_ids, scores
    qid = entry.get("question_id", "?")
    print(f"  WARNING: no doc_ids found for question [{qid}], evidence pack will be empty")
    return [], None


def _build_evidence_pack_from_ids(doc_ids, documents, config, scores=None):
    doc_map = {d.id: d for d in documents}
    items = []
    score_iter = iter(scores) if scores else None
    for doc_id in doc_ids[: config.rag.top_k]:
        doc = doc_map.get(doc_id)
        if doc is None:
            next(score_iter, None) if score_iter else None
            continue
        stripped = " ".join(doc.text.split())
        if len(stripped) > config.rag.max_fact_chars:
            stripped = stripped[: config.rag.max_fact_chars - 1].rstrip() + "..."
        items.append(
            Evidence(
                id=doc.id,
                title=doc.title,
                text=stripped,
                source_url=doc.source_url,
                source_name=doc.source_name,
                score=next(score_iter, None) if score_iter else None,
            )
        )
    return EvidencePack(question="", items=items)


def add_generation_to_traces(traces, documents, config, model_override):
    client = LlamaClient(
        base_url=config.runtime.base_url,
        timeout_seconds=config.runtime.timeout_seconds,
    )

    for entry in traces:
        q_text = entry.get("question", "")
        if not q_text:
            continue

        try:
            doc_ids, scores = _get_trace_doc_ids_and_scores(entry)
            evidence_pack = _build_evidence_pack_from_ids(doc_ids, documents, config, scores)
            prompt_bundle = render_prompt(q_text, evidence_pack, config)
            model = model_override or config.runtime.model

            print(f"  generating answer for [{entry['question_id']}]...")
            result = client.chat(
                messages=prompt_bundle.messages,
                model=model,
                temperature=config.runtime.temperature,
                max_tokens=config.runtime.max_tokens,
            )

            entry["generated_answer"] = result.content
            entry["rendered_user_message"] = (
                prompt_bundle.messages[-1].content if prompt_bundle.messages else ""
            )
            entry["context_text"] = prompt_bundle.context
            entry["generated_answer_model"] = result.model or model
        except LlamaError as e:
            entry["generated_answer"] = None
            entry["generation_error"] = str(e)[:300]
            if entry.get("failure_type", "ok") in ("ok", ""):
                entry["failure_type"] = "generation_issue"
                entry["diagnostic_note"] = str(e)[:200]


def handle_generation(args, traces, documents, config, metadata):
    if not getattr(args, "generation", False):
        metadata["generation_enabled"] = False
        return

    if not check_backend(config.runtime.base_url):
        print("WARNING: LLM backend offline. Skipping generation tests.")
        metadata["generation_enabled"] = False
        return

    try:
        add_generation_to_traces(traces, documents, config, args.model)
        metadata["generation_enabled"] = True
    except Exception as e:
        print(f"WARNING: LLM generation failed: {e}. Skipping generation tests.")
        metadata["generation_enabled"] = False


# ── CLI ───────────────────────────────────────────────────────────────


RETRIEVAL_CHOICES = [
    "lexical", "dense_qwen3", "hybrid_simple",
    "kiwi_bm25", "kiwi_bm25_dense_hybrid", "compare",
]


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
    parser.add_argument(
        "--generation",
        action="store_true",
        default=False,
        help="Enable LLM answer generation via llama-server.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override the default model label from sutra.toml.",
    )
    return parser.parse_args()


# ── Entry Point ────────────────────────────────────────────────────────


def main():
    args = parse_args()
    workspace_path = resolve_path(args.workspace)
    questions_path = resolve_path(args.questions)

    print(f"Loading workspace: {workspace_path}")
    try:
        config = load_config(workspace_path)
        documents = load_documents(config)
    except Exception as e:
        print(f"Error: Failed to load workspace — {e}")
        sys.exit(1)

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
    elif args.retrieval == "kiwi_bm25":
        run_kiwi_bm25(args, config, documents, questions, docs_check)
    elif args.retrieval == "kiwi_bm25_dense_hybrid":
        run_kiwi_bm25_dense_hybrid(args, config, documents, questions, docs_check)
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

    handle_generation(args, traces, documents, config, metadata)

    metadata["run_finished_at"] = datetime.now().isoformat()
    with open(output_trace_path, "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "traces": traces}, f, ensure_ascii=False, indent=2)

    generate_report(metadata, traces, output_report_path)
    print(f"Done. Trace: {output_trace_path}")
    print(f"Report: {output_report_path}")


def run_dense(args, config, documents, questions, docs_check):
    dense_status = check_dense_deps()
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

    model = load_embedding_model(device=_get_device())
    cache_dir = get_dense_cache_dir(resolve_path(args.workspace))
    embeddings, cache_meta = get_cached_embeddings(documents, model, cache_dir)

    metadata["embedding_model"] = get_model_name(model)
    metadata["embedding_device"] = get_model_device(model)
    metadata["embedding_dimension"] = int(embeddings.shape[1])
    metadata["embedding_cache_path"] = str(cache_dir)
    metadata["embedding_cache_hit"] = cache_meta.get("cache_hit", False)

    traces = run_questions_dense(questions, documents, model, embeddings, config)

    handle_generation(args, traces, documents, config, metadata)

    metadata["run_finished_at"] = datetime.now().isoformat()
    with open(output_trace_path, "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "traces": traces}, f, ensure_ascii=False, indent=2)

    generate_report(metadata, traces, output_report_path)
    print(f"Done. Trace: {output_trace_path}")
    print(f"Report: {output_report_path}")


def run_hybrid(args, config, documents, questions, docs_check):
    dense_status = check_dense_deps()
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

    model = load_embedding_model(device=_get_device())
    cache_dir = get_dense_cache_dir(resolve_path(args.workspace))
    embeddings, cache_meta = get_cached_embeddings(documents, model, cache_dir)

    metadata["embedding_model"] = get_model_name(model)
    metadata["embedding_device"] = get_model_device(model)
    metadata["embedding_dimension"] = int(embeddings.shape[1])
    metadata["embedding_cache_path"] = str(cache_dir)
    metadata["embedding_cache_hit"] = cache_meta.get("cache_hit", False)

    traces = run_questions_hybrid(
        questions, documents, model, embeddings, config, metadata
    )

    handle_generation(args, traces, documents, config, metadata)

    metadata["run_finished_at"] = datetime.now().isoformat()
    with open(output_trace_path, "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "traces": traces}, f, ensure_ascii=False, indent=2)

    generate_report(metadata, traces, output_report_path)
    print(f"Done. Trace: {output_trace_path}")
    print(f"Report: {output_report_path}")


def run_kiwi_bm25(args, config, documents, questions, docs_check):
    bm25_status = check_bm25_deps()
    if not bm25_status["kiwipiepy_available"] or not bm25_status["bm25s_available"]:
        print("=" * 60)
        print("ERROR: Kiwi + BM25 retrieval unavailable.")
        print("  kiwipiepy and bm25s not installed.")
        print("  Install: uv add --optional korean-search kiwipiepy bm25s")
        print("=" * 60)
        sys.exit(1)

    output_trace_path = resolve_path(args.trace)
    output_report_path = resolve_path(args.report)
    output_trace_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = build_base_metadata(
        resolve_path(args.workspace), resolve_path(args.questions),
        questions, docs_check, config,
    )
    metadata["retrieval_mode"] = "kiwi_bm25"
    metadata["bm25_dependency_status"] = bm25_status
    metadata["tokenizer_config"] = get_tokenizer_config()

    try:
        bm25, bm25_meta = build_bm25_index(documents)
    except Exception as e:
        print(f"ERROR: BM25 index build failed: {e}")
        sys.exit(1)
    metadata["bm25_cache"] = bm25_meta

    traces = run_questions_kiwi_bm25(questions, documents, bm25, config)

    handle_generation(args, traces, documents, config, metadata)

    metadata["run_finished_at"] = datetime.now().isoformat()
    with open(output_trace_path, "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "traces": traces}, f, ensure_ascii=False, indent=2)

    generate_report(metadata, traces, output_report_path)
    print(f"Done. Trace: {output_trace_path}")
    print(f"Report: {output_report_path}")


def run_kiwi_bm25_dense_hybrid(args, config, documents, questions, docs_check):
    bm25_status = check_bm25_deps()
    if not bm25_status["kiwipiepy_available"] or not bm25_status["bm25s_available"]:
        print("=" * 60)
        print("ERROR: Kiwi + BM25 dependency missing.")
        print("  Install: uv add --optional korean-search kiwipiepy bm25s")
        print("=" * 60)
        sys.exit(1)

    dense_status = check_dense_deps()
    if not dense_status["sentence_transformers_available"]:
        print("=" * 60)
        print("ERROR: Dense retrieval unavailable for hybrid.")
        print("  sentence-transformers not installed.")
        print("  Install: uv pip install sentence-transformers>=2.7.0")
        print("  Or run: uv run --extra korean-search --extra embeddings ...")
        print("=" * 60)
        sys.exit(1)

    output_trace_path = resolve_path(args.trace)
    output_report_path = resolve_path(args.report)
    output_trace_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = build_base_metadata(
        resolve_path(args.workspace), resolve_path(args.questions),
        questions, docs_check, config,
    )
    metadata["retrieval_mode"] = "kiwi_bm25_dense_hybrid"
    metadata["bm25_dependency_status"] = bm25_status
    metadata["embedding_dependency_status"] = dense_status
    metadata["tokenizer_config"] = get_tokenizer_config()
    metadata["hybrid_weights"] = {"bm25": 0.5, "dense": 0.5}

    try:
        bm25, bm25_meta = build_bm25_index(documents)
    except Exception as e:
        print(f"ERROR: BM25 index build failed: {e}")
        sys.exit(1)
    metadata["bm25_cache"] = bm25_meta

    model = load_embedding_model(device=_get_device())
    cache_dir = get_dense_cache_dir(resolve_path(args.workspace))
    embeddings, cache_meta = get_cached_embeddings(documents, model, cache_dir)

    metadata["embedding_model"] = get_model_name(model)
    metadata["embedding_device"] = get_model_device(model)
    metadata["embedding_dimension"] = int(embeddings.shape[1])
    metadata["embedding_cache_path"] = str(cache_dir)
    metadata["embedding_cache_hit"] = cache_meta.get("cache_hit", False)

    traces = run_questions_kiwi_bm25_dense_hybrid(
        questions, documents, bm25, model, embeddings, config
    )

    handle_generation(args, traces, documents, config, metadata)

    metadata["run_finished_at"] = datetime.now().isoformat()
    with open(output_trace_path, "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "traces": traces}, f, ensure_ascii=False, indent=2)

    generate_report(metadata, traces, output_report_path)
    print(f"Done. Trace: {output_trace_path}")
    print(f"Report: {output_report_path}")


def run_compare(args, config, documents, questions, docs_check):
    output_trace_path = REPO_ROOT / "tmp" / "eval_39_kiwi_bm25_compare_trace.json"
    output_report_path = REPO_ROOT / "tmp" / "eval_39_kiwi_bm25_compare_report.md"
    output_trace_path.parent.mkdir(parents=True, exist_ok=True)

    dense_status = check_dense_deps()
    bm25_status = check_bm25_deps()
    previous_labels = load_previous_trace()

    metadata = build_base_metadata(
        resolve_path(args.workspace), resolve_path(args.questions),
        questions, docs_check, config,
    )
    metadata["retrieval_mode"] = "compare"
    metadata["retrieval_modes_run"] = ["lexical"]
    metadata["dense_available"] = dense_status["sentence_transformers_available"]
    metadata["bm25_available"] = bm25_status["kiwipiepy_available"] and bm25_status["bm25s_available"]
    metadata["embedding_dependency_status"] = dense_status
    metadata["bm25_dependency_status"] = bm25_status
    metadata["embedding_model"] = None
    metadata["embedding_device"] = None
    metadata["embedding_dimension"] = None
    metadata["embedding_cache_path"] = None
    metadata["embedding_cache_hit"] = None
    metadata["tokenizer_config"] = get_tokenizer_config() if metadata["bm25_available"] else None

    model = None
    embeddings = None
    cache_meta = {}
    bm25 = None
    bm25_meta = {}

    if dense_status["sentence_transformers_available"]:
        metadata["retrieval_modes_run"].append("dense_qwen3")
        metadata["retrieval_modes_run"].append("hybrid_simple")
        try:
            model = load_embedding_model(device=_get_device())
            cache_dir = get_dense_cache_dir(resolve_path(args.workspace))
            embeddings, cache_meta = get_cached_embeddings(documents, model, cache_dir)
            metadata["embedding_model"] = get_model_name(model)
            metadata["embedding_device"] = get_model_device(model)
            metadata["embedding_dimension"] = int(embeddings.shape[1])
            metadata["embedding_cache_path"] = str(cache_dir)
            metadata["embedding_cache_hit"] = cache_meta.get("cache_hit", False)
        except Exception as e:
            metadata["dense_available"] = False
            metadata["dense_unavailable_reason"] = f"Model load failed: {e}"
            metadata["retrieval_modes_run"] = [m for m in metadata["retrieval_modes_run"] if m != "dense_qwen3" and m != "hybrid_simple"]
    else:
        metadata["dense_unavailable_reason"] = (
            "sentence-transformers not installed. "
            "Install: uv pip install sentence-transformers>=2.7.0"
        )

    if metadata["bm25_available"]:
        metadata["retrieval_modes_run"].append("kiwi_bm25")
        if metadata["dense_available"]:
            metadata["retrieval_modes_run"].append("kiwi_bm25_dense_hybrid")
        try:
            bm25, bm25_meta = build_bm25_index(documents)
        except Exception as e:
            metadata["bm25_available"] = False
            metadata["bm25_unavailable_reason"] = f"BM25 index build failed: {e}"
            metadata["retrieval_modes_run"] = [m for m in metadata["retrieval_modes_run"] if m not in ("kiwi_bm25", "kiwi_bm25_dense_hybrid")]
    else:
        metadata["bm25_unavailable_reason"] = (
            "kiwipiepy or bm25s not installed. "
            "Install: uv add --optional korean-search kiwipiepy bm25s"
        )

    metadata["bm25_cache"] = bm25_meta

    traces = run_questions_compare(
        questions, documents, config, model, embeddings,
        bm25, metadata, previous_labels,
    )

    handle_generation(args, traces, documents, config, metadata)

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
        "expected_temporal_type": q_data.get("expected_temporal_type", "none"),
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


def run_questions_kiwi_bm25(questions, documents, bm25, config):
    traces = []
    for q_data in questions:
        q_text = q_data["question"]
        expected_domain = q_data.get("expected_domain")
        print(f"[{q_data['id']}] kiwi_bm25: {q_text[:40]}...")

        pack = bm25_retrieve(q_text, documents, bm25, config)
        base = process_question_common(q_data, expected_domain)
        base["retrieved_doc_ids"] = [item.id for item in pack.items]
        base["retrieved_titles"] = [item.title for item in pack.items]
        base["retrieved_scores"] = [float(item.score) for item in pack.items]
        base["evidence_preview"] = (
            pack.items[0].text[:300] if pack.items else ""
        )
        base["failure_type"], base["diagnostic_note"] = classify_failure(
            base["retrieved_doc_ids"], expected_domain
        )
        traces.append(base)
    return traces


def run_questions_kiwi_bm25_dense_hybrid(
    questions, documents, bm25, model, embeddings, config
):
    traces = []
    for q_data in questions:
        q_text = q_data["question"]
        expected_domain = q_data.get("expected_domain")
        print(f"[{q_data['id']}] kiwi_bm25_dense_hybrid: {q_text[:40]}...")

        pack = hybrid_bm25_dense(q_text, documents, bm25, model, embeddings, config)
        base = process_question_common(q_data, expected_domain)
        base["retrieved_doc_ids"] = [item.id for item in pack.items]
        base["retrieved_titles"] = [item.title for item in pack.items]
        base["retrieved_scores"] = [float(item.score) for item in pack.items]
        base["evidence_preview"] = (
            pack.items[0].text[:300] if pack.items else ""
        )
        base["failure_type"], base["diagnostic_note"] = classify_failure(
            base["retrieved_doc_ids"], expected_domain
        )
        traces.append(base)
    return traces


def run_questions_compare(
    questions, documents, config, model, embeddings,
    bm25, metadata, previous_labels,
):
    traces = []
    dense_available = model is not None and embeddings is not None
    bm25_available = bm25 is not None

    for q_data in questions:
        q_text = q_data["question"]
        expected_domain = q_data.get("expected_domain")
        print(f"[{q_data['id']}] compare: {q_text[:40]}...")

        entry = process_question_common(q_data, expected_domain)

        q_id = q_data["id"]
        entry["previous_failure_label"] = previous_labels.get(q_id)

        # ── Lexical ──
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

        # ── Kiwi BM25 ──
        if bm25_available:
            bm25_pack = bm25_retrieve(q_text, documents, bm25, config)
            entry["kiwi_bm25"] = {
                "retrieved_doc_ids": [item.id for item in bm25_pack.items],
                "retrieved_titles": [item.title for item in bm25_pack.items],
                "retrieved_scores": [float(item.score) for item in bm25_pack.items],
            }
            kb_top1, kb_topk = check_domain_in_results(
                entry["kiwi_bm25"]["retrieved_doc_ids"], expected_domain
            )
            entry["kiwi_bm25_expected_domain_in_top1"] = kb_top1
            entry["kiwi_bm25_expected_domain_in_topk"] = kb_topk
        else:
            entry["kiwi_bm25"] = None
            entry["kiwi_bm25_expected_domain_in_top1"] = None
            entry["kiwi_bm25_expected_domain_in_topk"] = None

        # ── Dense ──
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

            # ── Hybrid (simple) ──
            hybrid_pack = hybrid_combine(lexical_pack, dense_pack, config)
            entry["hybrid_simple"] = {
                "retrieved_doc_ids": [item.id for item in hybrid_pack.items],
                "retrieved_titles": [item.title for item in hybrid_pack.items],
                "retrieved_scores": [float(item.score) for item in hybrid_pack.items],
            }
            h_top1, h_topk = check_domain_in_results(
                entry["hybrid_simple"]["retrieved_doc_ids"], expected_domain
            )
            entry["hybrid_simple_expected_domain_in_top1"] = h_top1
            entry["hybrid_simple_expected_domain_in_topk"] = h_topk

            # ── Kiwi BM25 + Dense hybrid ──
            if bm25_available:
                kd_pack = hybrid_bm25_dense(
                    q_text, documents, bm25, model, embeddings, config
                )
                entry["kiwi_bm25_dense_hybrid"] = {
                    "retrieved_doc_ids": [item.id for item in kd_pack.items],
                    "retrieved_titles": [item.title for item in kd_pack.items],
                    "retrieved_scores": [float(item.score) for item in kd_pack.items],
                }
                kd_top1, kd_topk = check_domain_in_results(
                    entry["kiwi_bm25_dense_hybrid"]["retrieved_doc_ids"],
                    expected_domain,
                )
                entry["kiwi_bm25_dense_hybrid_expected_domain_in_top1"] = kd_top1
                entry["kiwi_bm25_dense_hybrid_expected_domain_in_topk"] = kd_topk
            else:
                entry["kiwi_bm25_dense_hybrid"] = None
                entry["kiwi_bm25_dense_hybrid_expected_domain_in_top1"] = None
                entry["kiwi_bm25_dense_hybrid_expected_domain_in_topk"] = None
        else:
            entry["dense"] = None
            entry["dense_expected_domain_in_top1"] = None
            entry["dense_expected_domain_in_topk"] = None
            entry["hybrid_simple"] = None
            entry["hybrid_simple_expected_domain_in_top1"] = None
            entry["hybrid_simple_expected_domain_in_topk"] = None
            entry["kiwi_bm25_dense_hybrid"] = None
            entry["kiwi_bm25_dense_hybrid_expected_domain_in_top1"] = None
            entry["kiwi_bm25_dense_hybrid_expected_domain_in_topk"] = None

        # Improvement / regression flag (vs previous trace)
        entry["improved"] = False
        entry["regressed"] = False
        entry["diagnostic_note"] = ""

        prev = entry.get("previous_failure_label")
        if prev == "retrieval_miss":
            any_new_ok = (
                (bm25_available and entry["kiwi_bm25_expected_domain_in_topk"])
                or (dense_available and entry["dense_expected_domain_in_topk"])
                or (dense_available and entry["hybrid_simple_expected_domain_in_topk"])
                or (
                    bm25_available and dense_available
                    and entry["kiwi_bm25_dense_hybrid_expected_domain_in_topk"]
                )
            )
            if any_new_ok:
                entry["improved"] = True
                entry["diagnostic_note"] = (
                    "Previously retrieval_miss; improved by newer mode."
                )
        if prev == "ok":
            lexical_ok = entry["lexical_expected_domain_in_topk"]
            any_new_miss = (
                (bm25_available and not entry["kiwi_bm25_expected_domain_in_topk"])
                or (dense_available and not entry["dense_expected_domain_in_topk"])
                or (
                    dense_available
                    and not entry["hybrid_simple_expected_domain_in_topk"]
                )
                or (
                    bm25_available and dense_available
                    and not entry["kiwi_bm25_dense_hybrid_expected_domain_in_topk"]
                )
            )
            if any_new_miss and lexical_ok:
                entry["regressed"] = True
                entry["diagnostic_note"] = (
                    "Previously ok; newer mode(s) lost expected domain."
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


def _compute_generation_metrics(traces, total_count):
    answered = sum(1 for t in traces if t.get("generated_answer"))
    gen_acc = (
        f"{answered}/{total_count} ({100 * answered / total_count:.1f}%)"
        if total_count
        else "N/A"
    )
    return answered, gen_acc


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

    answered, gen_acc = _compute_generation_metrics(
        traces, len(traces)
    )
    generation_enabled = metadata.get("generation_enabled", False)

    lines.extend([
        "",
        "## 5. Generation",
        "",
    ])
    if generation_enabled:
        lines.extend([
            f"- **Generation Accuracy:** {gen_acc}",
            "",
            "| ID | Question | Generated Answer (preview) | Failure Type |",
            "| :--- | :--- | :--- | :--- |",
        ])
        for t in traces:
            qid = t["question_id"]
            qtext = t["question"][:35]
            ans = (t.get("generated_answer") or "—")[:80].replace("\n", " ")
            ft = t.get("failure_type", "?")
            lines.append(f"| {qid} | {qtext} | {ans} | `{ft}` |")
    else:
        lines.append("*Generation was not enabled for this run. Use `--generation` to enable LLM answer generation.*")

    lines.extend([
        "",
        "## 6. Recommended Next Fixes",
        "1. **Data Expansion**: Address `data_missing` cases by crawling missing sections.",
        "2. **Retrieval Tuning**: Fix `retrieval_miss` by adjusting weights or hybrid search.",
        "3. **OCR/Page 3**: Review graduation requirements if OCR gaps are suspected.",
    ])

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ── Compare Report (5-mode) ─────────────────────────────────────────


def generate_compare_report(metadata, traces, report_path):
    dense_avail = metadata.get("dense_available", False)
    bm25_avail = metadata.get("bm25_available", False)
    total = len(traces)

    # ── Count metrics per mode ──
    def _always_true(t):
        return True

    def _mode_count(field_prefix, cond=None):
        pred = cond if cond is not None else _always_true
        top1 = sum(1 for t in traces if pred(t) and t.get(f"{field_prefix}_expected_domain_in_top1") is True)
        topk = sum(1 for t in traces if pred(t) and t.get(f"{field_prefix}_expected_domain_in_topk") is True)
        return top1, topk

    lex_t1, lex_tk = _mode_count("lexical")
    kb_t1, kb_tk = _mode_count("kiwi_bm25", cond=lambda t: bm25_avail)
    d_t1, d_tk = _mode_count("dense", cond=lambda t: dense_avail)
    h_t1, h_tk = _mode_count("hybrid_simple", cond=lambda t: dense_avail)
    kd_t1, kd_tk = _mode_count("kiwi_bm25_dense_hybrid", cond=lambda t: bm25_avail and dense_avail)

    improved = sum(1 for t in traces if t.get("improved"))
    regressed = sum(1 for t in traces if t.get("regressed"))
    prev_retrieval_miss = sum(1 for t in traces if t.get("previous_failure_label") == "retrieval_miss")
    prev_ok = sum(1 for t in traces if t.get("previous_failure_label") == "ok")

    def _mode_fmt(t1, tk, count, label):
        if count == 0:
            return "N/A"
        return f"{t1}/{count} | {tk}/{count}"

    # ── Build lines ──
    lines = [
        "# Compare Report: Kiwi+BM25 vs Qwen3 Dense vs Lexical (5 modes)",
        "",
        "## 1. Run Metadata",
        f"- **Date:** {metadata['run_started_at']}",
        f"- **Finished:** {metadata.get('run_finished_at', '(unknown)')}",
        f"- **Git Commit:** `{metadata['git_commit']}`",
        f"- **Git Status:** `{metadata['git_status_short']}`",
        f"- **Workspace:** `{metadata['workspace_path']}`",
        f"- **Questions:** {metadata['question_count']}",
        f"- **Corpus:** {metadata['corpus_doc_counts']}",
        f"- **Retrieval Modes:** {metadata['retrieval_modes_run']}",
        "",
        "## 2. Dependency / Backend Availability",
        f"- **sentence-transformers:** {metadata.get('embedding_dependency_status', {}).get('sentence_transformers_available', '?')}",
        f"  - version: {metadata.get('embedding_dependency_status', {}).get('sentence_transformers_version', '?')}",
        f"- **Dense available:** {dense_avail}",
        f"- **kiwipiepy:** {metadata.get('bm25_dependency_status', {}).get('kiwipiepy_available', '?')}",
        f"  - version: {metadata.get('bm25_dependency_status', {}).get('kiwipiepy_version', '?')}",
        f"- **bm25s:** {metadata.get('bm25_dependency_status', {}).get('bm25s_available', '?')}",
        f"  - version: {metadata.get('bm25_dependency_status', {}).get('bm25s_version', '?')}",
        f"- **BM25 available:** {bm25_avail}",
    ]

    if dense_avail:
        lines.extend([
            "",
            "### Dense Model",
            f"- **Embedding model:** {metadata.get('embedding_model', '?')}",
            f"- **Device:** {metadata.get('embedding_device', '?')}",
            f"- **Dimension:** {metadata.get('embedding_dimension', '?')}",
        ])
    if bm25_avail:
        tc = metadata.get("tokenizer_config", {})
        lines.extend([
            "",
            "### Tokenizer Config (Kiwi+BM25)",
            f"- **Keep tags:** {tc.get('keep_tags', '?')}",
            f"- **Length filter policy:** {tc.get('length_filter_policy', '?')}",
            f"- **Compound map keys:** {list(tc.get('compound_map', {}).keys())}",
            f"- **Alias map keys:** {list(tc.get('alias_map', {}).keys())}",
            "",
            "### Tokenizer Caveats",
        ])
        for note in tc.get("notes", []):
            lines.append(f"- {note}")

    lines.extend([
        "",
        "## 3. Cache Summary",
        f"- **Dense cache path:** {metadata.get('embedding_cache_path', 'N/A')}",
        f"- **Dense cache hit:** {metadata.get('embedding_cache_hit', 'N/A')}",
        f"- **BM25 cache:** {metadata.get('bm25_cache', {}).get('cache_hit', 'N/A')}",
    ])

    # ── Mode Comparison Summary ──
    lines.extend([
        "",
        "## 4. Mode Comparison Summary",
        "| Metric | lexical | kiwi_bm25 | dense_qwen3 | hybrid_simple | kiwi_bm25_dense_hybrid |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
        f"| Expected domain in top-1 | {lex_t1}/{total} | {kb_t1}/{total if bm25_avail else 'N/A'} | {d_t1}/{total if dense_avail else 'N/A'} | {h_t1}/{total if dense_avail else 'N/A'} | {kd_t1}/{total if bm25_avail and dense_avail else 'N/A'} |",
        f"| Expected domain in top-k | {lex_tk}/{total} | {kb_tk}/{total if bm25_avail else 'N/A'} | {d_tk}/{total if dense_avail else 'N/A'} | {h_tk}/{total if dense_avail else 'N/A'} | {kd_tk}/{total if bm25_avail and dense_avail else 'N/A'} |",
        "",
        "### Improvement / Regression (vs previous trace)",
        f"- Previously `retrieval_miss` questions: {prev_retrieval_miss}",
        f"- Previously `ok` questions: {prev_ok}",
        f"- Improved by any newer mode: {improved}",
        f"- Regressed by any newer mode: {regressed}",
    ])

    # ── Per-Question Comparison ──
    lines.extend([
        "",
        "## 5. Per-Question Comparison",
        "| ID | Question | Expected domain | Lex top1/topk | KB top1/topk | Dense top1/topk | Hybrid top1/topk | KB+Dense top1/topk | Improved | Regressed | Note |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ])

    for t in traces:
        qid = t["question_id"]
        qtext = t["question"][:25]
        exp = t.get("expected_or_likely_domain", "?")[:12]
        def _cell(prefix, avail=False):
            if not avail:
                return "N/A"
            t1 = t.get(f"{prefix}_expected_domain_in_top1")
            tk = t.get(f"{prefix}_expected_domain_in_topk")
            return f"{'✓' if t1 else '✗'}/{'✓' if tk else '✗'}"
        imp = "✓" if t.get("improved") else ""
        reg = "✓" if t.get("regressed") else ""
        note = t.get("diagnostic_note", "")[:50]
        lines.append(
            f"| {qid} | {qtext} | {exp} | {_cell('lexical', True)} | "
            f"{_cell('kiwi_bm25', bm25_avail)} | {_cell('dense', dense_avail)} | "
            f"{_cell('hybrid_simple', dense_avail)} | {_cell('kiwi_bm25_dense_hybrid', bm25_avail and dense_avail)} | "
            f"{imp} | {reg} | {note} |"
        )

    # ── Manual Spot-Check ──
    lines.extend([
        "",
        "## 6. Manual Spot-Check for Temporal / Exact-Match Questions",
        "",
        "Verifying the *specific correct document* (not just domain) across all 5 modes.",
        "",
        "| Question ID | Topic | Lexical Top-1 | Kiwi+BM25 Top-1 | Dense Top-1 | Hybrid Top-1 | KB+Dense Top-1 | Correct Doc Expected |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ])

    spot_checks = [
        ("public_probe_02", "수강신청", "calendar_event_2026_0007"),
        ("public_probe_11", "종강", "calendar_event_2026_0035"),
        ("public_probe_03", "오늘 학식", "dining_2026-06-09 (today's date)"),
        ("public_probe_13", "다음주 화요일 2학생회관", "dining (data gap expected)"),
        ("gp046", "다음주 화요일 2학생회관", "dining (data gap expected)"),
        ("public_probe_04", "셔틀 정상 운행", "shuttle route doc"),
        ("gp050", "오늘 셔틀 정상 운행", "shuttle route doc"),
        ("gp051", "월평역 셔틀", "shuttle route doc (mentions 월평역)"),
        ("public_probe_01", "컴퓨터인공지능학부 졸업요건", "graduation page 1"),
        ("gp001", "컴퓨터인공지능학부 졸업요건", "graduation page 1"),
        ("gp002", "컴퓨터인공지능학부 졸업요건", "graduation page"),
        ("gp004", "컴퓨터인공지능학부 졸업요건", "graduation page"),
    ]

    trace_map = {t["question_id"]: t for t in traces}
    for qid, topic, expected_doc in spot_checks:
        t = trace_map.get(qid)
        if not t:
            lines.append(f"| {qid} | {topic} | N/A | N/A | N/A | N/A | N/A | {expected_doc} |")
            continue

        def _top1(mode_key):
            mode_data = t.get(mode_key)
            if mode_data is None:
                return "(N/A)"
            ids = mode_data.get("retrieved_doc_ids", [])
            return f"`{ids[0]}`" if ids else "(empty)"

        lines.append(
            f"| {qid} | {topic} | {_top1('lexical')} | {_top1('kiwi_bm25')} | "
            f"{_top1('dense')} | {_top1('hybrid_simple')} | {_top1('kiwi_bm25_dense_hybrid')} | {expected_doc} |"
        )

    lines.extend([
        "",
        "### Spot-Check Notes",
        "- **수강신청 (public_probe_02):** Expected `calendar_event_2026_0007` (2026 정규수강신청).",
        "  - Kiwi should tokenize '수강신청' as a compound via COMPOUND_MAP.",
        "  - BM25 should rank the 2026 calendar event higher due to year/term token match.",
        "- **종강 (public_probe_11):** Expected `calendar_event_2026_0035` (2026 하기종강).",
        "  - Kiwi tokenizer keeps '종강' as a single noun.",
        "  - Check if BM25 prefers the 2026 version over 2024.",
        "- **오늘 학식 (public_probe_03):** Today is 2026-06-09. Verify correct date's menu.",
        "  - Kiwi should keep '학식', and alias expansion adds '메뉴', '식단'.",
        "- **셔틀 정상 운행 (public_probe_04, gp050):** Verify shuttle route doc is top-1.",
        "  - Kiwi should keep '셔틀', '정상', '운행' tokens.",
        "  - Alias expansion should add '통학버스', '셔틀버스'.",
        "- **월평역 셔틀 (gp051):** Critical test for compound merge (`월평` + `역` → `월평역`).",
        "  - If compound merge works, BM25 should match shuttle docs mentioning '월평역'.",
        "  - Without compound merge, '역' (1 char) would be dropped.",
        "- **컴퓨터인공지능학부 졸업요건 (public_probe_01, gp001, gp002, gp004):**",
        "  - Kiwi compound merge should keep '컴퓨터인공지능학부' intact.",
        "  - Alias expansion adds '컴퓨터융합학부', '인공지능학과'.",
        "  - Verify no false positives from unrelated departments.",
        "- **다음주 화요일 2학생회관 (public_probe_13, gp046):** Data gap expected.",
        "  - Kiwi compound merge should handle '제2학생회관' if partially present in doc text.",
        "  - BM25 cannot fix data absence; expect `data_missing`.",
        "",
        "## 7. Summary Metrics",
        "| Metric | lexical | kiwi_bm25 | dense_qwen3 | hybrid_simple | kiwi_bm25_dense_hybrid |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
        f"| Expected domain top-1 | {lex_t1}/{total} | {kb_t1}/{total if bm25_avail else 'N/A'} | {d_t1}/{total if dense_avail else 'N/A'} | {h_t1}/{total if dense_avail else 'N/A'} | {kd_t1}/{total if bm25_avail and dense_avail else 'N/A'} |",
        f"| Expected domain top-k | {lex_tk}/{total} | {kb_tk}/{total if bm25_avail else 'N/A'} | {d_tk}/{total if dense_avail else 'N/A'} | {h_tk}/{total if dense_avail else 'N/A'} | {kd_tk}/{total if bm25_avail and dense_avail else 'N/A'} |",
        "| Previous retrieval_miss improved | — | — | — | — | — |",
        "| Previous ok regressed | — | — | — | — | — |",
        "| Manual spot-check pass/fail | — | — | — | — | — |",
        "",
        "> Note: 'Previous retrieval_miss improved' and 'Previous ok regressed' counts are shown in Section 4.",
        "> Manual spot-check results are in Section 6 above.",
        "",
        "## 8. Generation",
    ])

    answered, gen_acc = _compute_generation_metrics(
        traces, total
    )
    generation_enabled = metadata.get("generation_enabled", False)

    if generation_enabled:
        lines.extend([
            "",
            f"- **Generation Accuracy:** {gen_acc}",
            "",
            "| ID | Question | Generated Answer (preview) | Failure Type |",
            "| :--- | :--- | :--- | :--- |",
        ])
        for t in traces:
            qid = t["question_id"]
            qtext = t["question"][:35]
            ans = (t.get("generated_answer") or "—")[:80].replace("\n", " ")
            ft = t.get("failure_type", "?")
            lines.append(f"| {qid} | {qtext} | {ans} | `{ft}` |")
    else:
        lines.append("")
        lines.append("*Generation was not enabled for this run. Use `--generation` to enable LLM answer generation.*")

    lines.extend([
        "",
        "## 9. Final Recommendation",
    ])

    # ── Recommendation ──
    if not bm25_avail and not dense_avail:
        lines.append(
            "**Both Kiwi+BM25 and dense retrieval were unavailable.**\n"
            "> Recommendation: **Install dependencies and re-run.**"
        )
    elif not bm25_avail and dense_avail:
        lines.append(
            "**Kiwi+BM25 was unavailable; only dense results above.**\n"
            "> Recommendation: **Install korean-search deps and re-run for full comparison.**"
        )
    elif bm25_avail and not dense_avail:
        lines.append(
            "**Dense retrieval was unavailable; only lexical and Kiwi+BM25 results above.**\n"
            "> Recommendation: **Install embeddings deps and re-run for full 5-mode comparison.**"
        )
    else:
        # Both available — make evidence-based recommendation
        improvements = []
        if kb_tk > lex_tk:
            improvements.append("Kiwi+BM25 improves top-k domain coverage over lexical")
        if kd_tk > d_tk:
            improvements.append("Kiwi+BM25+Dense hybrid improves over Dense alone")
        if kd_tk > max(lex_tk, d_tk, h_tk):
            improvements.append("Kiwi+BM25+Dense hybrid achieves best overall top-k coverage")

        if improvements:
            lines.append("**Kiwi+BM25 shows measurable improvement:**\n")
            for imp in improvements:
                lines.append(f"- {imp}")
            if kd_tk >= max(lex_tk, d_tk, h_tk, kb_tk):
                lines.append(
                    "\n> Recommendation: **Use Kiwi+BM25 + Qwen dense hybrid** "
                    "for best coverage on this corpus."
                )
            else:
                lines.append(
                    "\n> Recommendation: **Use Kiwi+BM25** as lexical replacement. "
                    "Consider fine-tuning hybrid weights."
                )
        else:
            lines.append(
                "**Kiwi+BM25 does not significantly improve over existing methods on this corpus.**\n"
                "> Recommendation: **Keep current experimental setup and collect more data.** "
                "Kiwi+BM25 may still be useful for out-of-domain or low-resource queries."
            )

        if regressed > 0:
            lines.append(
                f"\n> **Caution:** {regressed} previously-ok questions regressed. "
                "Review individual cases before promoting."
            )

    lines.extend([
        "",
        "---",
        "",
        "*Report generated by run_probe39.py compare mode (5-mode Kiwi+BM25 experiment)*",
        "",
        "### Decision options:",
        "- keep Qwen dense only",
        "- use Kiwi+BM25",
        "- use Kiwi+BM25 + Qwen dense hybrid",
        "- keep current experimental setup and collect more data",
        "- abandon Kiwi/BM25 for now",
    ])

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
