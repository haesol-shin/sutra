import json
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

# Use sutra package
from sutra.config import load_config
from sutra.documents import load_documents
from sutra.retrieval import retrieve
from sutra.service import ask

REPO_ROOT = Path(__file__).resolve().parents[3]

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
        output = subprocess.check_output([
            "uv", "run", "python", "-m", "sutra.cli", "docs", "check", 
            "--workspace", str(workspace_path), "--json"
        ], cwd=REPO_ROOT, text=True)
        return json.loads(output)
    except Exception:
        return {"error": "failed to run docs check"}

def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the CNU 39-question clean-corpus evaluation."
    )
    parser.add_argument(
        "--workspace",
        default="examples/cnu-campus/sutra.toml",
        help="Workspace config path, relative to repo root unless absolute.",
    )
    parser.add_argument(
        "--questions",
        default="data/gold/task2_probe39_eval.json",
        help="Probe question JSON path, relative to repo root unless absolute.",
    )
    parser.add_argument(
        "--trace",
        default="tmp/eval_39_clean_corpus_trace.json",
        help="Trace output path, relative to repo root unless absolute.",
    )
    parser.add_argument(
        "--report",
        default="tmp/eval_39_clean_corpus_report.md",
        help="Markdown report path, relative to repo root unless absolute.",
    )
    return parser.parse_args()


def resolve_path(path: str) -> Path:
    path_obj = Path(path)
    if path_obj.is_absolute():
        return path_obj
    return REPO_ROOT / path_obj


def main():
    args = parse_args()
    workspace_path = resolve_path(args.workspace)
    questions_path = resolve_path(args.questions)
    output_trace_path = resolve_path(args.trace)
    output_report_path = resolve_path(args.report)

    if not output_trace_path.parent.exists():
        output_trace_path.parent.mkdir(parents=True)

    print(f"Loading workspace: {workspace_path}")
    config = load_config(workspace_path)
    documents = load_documents(config)
    
    print(f"Loading questions: {questions_path}")
    with open(questions_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print("Verifying environment...")
    git_commit, git_status = get_git_info()
    backend_available = check_backend(config.runtime.base_url)
    docs_check = get_docs_check(workspace_path)
    
    # Corpus counts by domain
    counts = {}
    for doc in documents:
        # Match sutra's logic or metadata
        domain = doc.metadata.get("domain")
        if not domain:
            # Heuristic if domain missing in metadata
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
        counts[domain] = counts.get(domain, 0) + 1
    
    metadata = {
        "git_commit": git_commit,
        "git_status_short": git_status,
        "workspace_path": str(workspace_path),
        "corpus_doc_counts": counts,
        "docs_check_result": docs_check,
        "question_source_path": str(questions_path),
        "question_count": len(questions),
        "full_generation_available": backend_available,
        "backend_url": config.runtime.base_url,
        "backend_model": config.runtime.model,
        "run_started_at": datetime.now().isoformat(),
    }

    print(f"Starting evaluation of {len(questions)} questions...")
    traces = []
    for q_data in questions:
        q_id = q_data["id"]
        q_text = q_data["question"]
        expected_domain = q_data.get("expected_domain")
        
        print(f"[{q_id}] {q_text[:30]}...")
        
        # Retrieve-only
        evidence_pack = retrieve(q_text, documents, config)
        
        trace = {
            "question_id": q_id,
            "question": q_text,
            "expected_or_likely_domain": expected_domain,
            "retrieved_doc_ids": [item.id for item in evidence_pack.items],
            "retrieved_titles": [item.title for item in evidence_pack.items],
            "retrieved_scores": [float(item.score) for item in evidence_pack.items],
            "evidence_preview": evidence_pack.items[0].text[:300] if evidence_pack.items else "",
            "failure_type": "ok", 
            "diagnostic_note": ""
        }
        
        if backend_available:
            try:
                ans = ask(q_text, workspace=config)
                trace["generated_answer"] = ans.answer
                trace["answer_model"] = ans.model
                # Basic groundedness check? For now, we manually label.
            except Exception as e:
                trace["failure_type"] = "generation_issue"
                trace["diagnostic_note"] = f"Generation failed: {str(e)}"
        
        # Heuristic failure typing for retrieval
        if not trace["retrieved_doc_ids"]:
            trace["failure_type"] = "data_missing"
            trace["diagnostic_note"] = "No evidence found for this query."
        elif expected_domain:
            retrieved_domains = []
            for item_id in trace["retrieved_doc_ids"]:
                # Quick lookup for domain in ID
                d = "unknown"
                if "dining" in item_id:
                    d = "dining"
                elif "shuttle" in item_id:
                    d = "shuttle"
                elif "calendar" in item_id:
                    d = "academic_calendar"
                elif "graduation" in item_id:
                    d = "graduation"
                elif "notice" in item_id:
                    d = "notices"
                retrieved_domains.append(d)
            
            # If expected domain is graduation, notices, etc.
            if expected_domain not in retrieved_domains:
                # If we got something else, it might be a retrieval miss or classifier issue
                trace["failure_type"] = "retrieval_miss"
                trace["diagnostic_note"] = f"Expected {expected_domain} but retrieved {set(retrieved_domains)}."

        traces.append(trace)

    metadata["run_finished_at"] = datetime.now().isoformat()
    
    # Save trace
    with open(output_trace_path, "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "traces": traces}, f, ensure_ascii=False, indent=2)

    # Generate Report
    generate_report(metadata, traces, output_report_path)
    print(f"Done. Trace: {output_trace_path}, Report: {output_report_path}")

def generate_report(metadata, traces, report_path):
    failure_counts = {}
    for t in traces:
        ft = t["failure_type"]
        failure_counts[ft] = failure_counts.get(ft, 0) + 1
    
    lines = [
        "# Evaluation Report: 39-Question Clean Corpus Run",
        "",
        "## 1. Run Metadata",
        f"- **Date:** {metadata['run_started_at']}",
        f"- **Git Commit:** `{metadata['git_commit']}`",
        f"- **Git Status:** `{metadata['git_status_short'] or 'clean'}`",
        f"- **Workspace:** `{metadata['workspace_path']}`",
        f"- **Question Source:** `{metadata['question_source_path']}`",
        f"- **Question Count:** {metadata['question_count']}",
        f"- **Backend Available:** {metadata['full_generation_available']}",
        "",
        "## 2. Corpus State",
        "| Domain | Count |",
        "| :--- | :--- |"
    ]
    for domain, count in metadata["corpus_doc_counts"].items():
        lines.append(f"| {domain} | {count} |")
    
    lines.extend([
        "",
        "## 3. Failure Summary",
        "| Failure Type | Count |",
        "| :--- | :--- |"
    ])
    # Ensure all failure types from taxonomy are present or at least summarized
    taxonomy = ["ok", "data_missing", "retrieval_miss", "generation_issue", "ocr_gap", "ambiguous_question", "classifier_issue", "tool_needed", "evaluation_unclear"]
    for ft in taxonomy:
        count = failure_counts.get(ft, 0)
        lines.append(f"| `{ft}` | {count} |")

    lines.extend([
        "",
        "## 4. Question Breakdown",
        "| ID | Question | Top Retrieval | Failure Type | Note |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ])
    for t in traces:
        top_title = t["retrieved_titles"][0] if t["retrieved_titles"] else "NONE"
        note = t["diagnostic_note"].replace("\n", " ")
        lines.append(f"| {t['question_id']} | {t['question']} | {top_title} | `{t['failure_type']}` | {note} |")

    lines.extend([
        "",
        "## 5. Recommended Next Fixes",
        "1. **Data Expansion**: Address `data_missing` cases by crawling missing sections.",
        "2. **Retrieval Tuning**: Fix `retrieval_miss` by adjusting weights or hybrid search if domain mismatches are high.",
        "3. **OCR/Page 3**: Review graduation requirements specifically if OCR gaps are suspected.",
    ])

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    main()
