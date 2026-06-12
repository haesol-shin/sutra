from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import requests
from pydantic import BaseModel, RootModel

from sutra.config import Config, _default_model_dir, load_config, resolve_input_path, resolve_output_path
from sutra.errors import ConfigError, LlamaError, WorkspaceResolutionError
from sutra.llama import download_model, EchoClient, start_llama_server
from sutra.models import Document
from sutra.service import ask, fallback_answer

_WORKSPACE_COMMANDS = {"ask", "batch", "workspace", "docs", "llama", "doctor", "ui"}


class ChatOutputItem(BaseModel):
    """A single Q&A pair in a batch output file."""
    user: str
    model: str


ChatOutput = RootModel[list[ChatOutputItem]]


def _prepare_chainlit_app_root(app_root: Path, toml_path: Path) -> None:
    chainlit_dir = app_root / ".chainlit"
    chainlit_dir.mkdir(exist_ok=True)

    # Priority: 1) cwd/.chainlit/config.toml  2) workspace/.chainlit/config.toml  3) packaged default
    user_config = None
    cwd_local = Path.cwd() / ".chainlit" / "config.toml"
    if cwd_local.exists():
        user_config = cwd_local
    if user_config is None:
        ws_config = toml_path.parent / ".chainlit" / "config.toml"
        if ws_config.exists():
            user_config = ws_config

    pkg_dir = Path(__file__).resolve().parent
    if user_config:
        shutil.copy2(user_config, chainlit_dir / "config.toml")
    else:
        pkg_config = pkg_dir / "resources" / "ui" / "chainlit_config.toml"
        shutil.copy2(pkg_config, chainlit_dir / "config.toml")

    app_public = app_root / "public"
    app_public.mkdir(exist_ok=True)
    for public_dir in (
        pkg_dir / "resources" / "ui" / "public",
        toml_path.parent / ".chainlit" / "public",
        Path.cwd() / ".chainlit" / "public",
    ):
        if public_dir.exists():
            shutil.copytree(public_dir, app_public, dirs_exist_ok=True)

    pkg_readme = pkg_dir / "resources" / "ui" / "chainlit.md"
    app_readme = app_root / "chainlit.md"
    if pkg_readme.exists():
        shutil.copy2(pkg_readme, app_readme)
    else:
        app_readme.write_text("", encoding="utf-8")


def resolve_workspace_path(cli_workspace: str | None = None) -> Path:
    # 1. --workspace path
    if cli_workspace:
        path = Path(cli_workspace).expanduser().resolve()
        toml_path = path / "sutra.toml" if path.is_dir() else path
        if not toml_path.exists():
            raise WorkspaceResolutionError(f"Workspace config not found at: {toml_path}")
        return toml_path

    # 2. SUTRA_WORKSPACE environment variable
    env_workspace = os.getenv("SUTRA_WORKSPACE")
    if env_workspace:
        path = Path(env_workspace).expanduser().resolve()
        toml_path = path / "sutra.toml" if path.is_dir() else path
        if not toml_path.exists():
            raise WorkspaceResolutionError(f"Workspace config not found at SUTRA_WORKSPACE: {toml_path}")
        return toml_path

    # 3. Walk upward from current working directory looking for sutra.toml
    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        toml_path = parent / "sutra.toml"
        if toml_path.exists() and toml_path.is_file():
            return toml_path

    # 4. If not found, fail with a concrete example and exit code 2
    raise WorkspaceResolutionError(
        "Workspace config not found. Use one of:\n"
        "  --workspace examples/cnu-campus/sutra.toml\n"
        "  SUTRA_WORKSPACE=examples/cnu-campus/sutra.toml\n"
        "  cd examples/cnu-campus"
    )


def validate_workspace(toml_path: Path | None) -> dict[str, Any]:
    if toml_path is None:
        return {
            "status": "fail",
            "exit_code": 2,
            "errors": [
                "Workspace config not found. Use one of:\n"
                "  --workspace examples/cnu-campus/sutra.toml\n"
                "  SUTRA_WORKSPACE=examples/cnu-campus/sutra.toml\n"
                "  cd examples/cnu-campus"
            ],
            "config": None,
        }

    errors = []
    config = None
    try:
        config = load_config(toml_path)
    except Exception as exc:
        errors.append(str(exc))
        return {
            "status": "fail",
            "exit_code": 1,
            "errors": errors,
            "config": None,
        }

    # Check referenced paths exist
    paths_to_check = [
        ("rag.index_path", config.rag.index_path),
        ("prompts.system", config.prompts.system),
    ]
    if config.evals.smoke is not None:
        paths_to_check.append(("evals.smoke", config.evals.smoke))
    if config.evals.regression is not None:
        paths_to_check.append(("evals.regression", config.evals.regression))

    for name, p in paths_to_check:
        if not p.exists():
            errors.append(f"Referenced path '{name}' does not exist: {p}")

    if errors:
        return {
            "status": "fail",
            "exit_code": 1,
            "errors": errors,
            "config": config,
        }

    return {
        "status": "ok",
        "exit_code": 0,
        "errors": [],
        "config": config,
    }


def check_documents(index_path: Path) -> dict[str, Any]:
    total_documents = 0
    invalid_lines = 0
    empty_text_rows = 0
    missing_source_name = 0
    missing_source_url = 0

    seen_ids = set()
    duplicate_ids = 0

    try:
        content = index_path.read_text(encoding="utf-8")
    except Exception as exc:
        return {
            "error": f"Failed to read document index at {index_path}: {exc}",
            "total_documents": 0,
            "invalid_lines": 1,
            "duplicate_ids": 0,
            "empty_text_rows": 0,
            "missing_source_name": 0,
            "missing_source_url": 0,
        }

    for line in content.splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            doc = Document.model_validate(obj)
            total_documents += 1

            if not doc.text or not doc.text.strip():
                empty_text_rows += 1

            if doc.id in seen_ids:
                duplicate_ids += 1
            else:
                seen_ids.add(doc.id)

            if not doc.source_name:
                missing_source_name += 1
            if not doc.source_url:
                missing_source_url += 1

        except (json.JSONDecodeError, Exception):
            invalid_lines += 1

    return {
        "total_documents": total_documents,
        "invalid_lines": invalid_lines,
        "duplicate_ids": duplicate_ids,
        "empty_text_rows": empty_text_rows,
        "missing_source_name": missing_source_name,
        "missing_source_url": missing_source_url,
    }


def check_docs(toml_path: Path | None, config: Config | None = None) -> dict[str, Any]:
    errors = []
    if config is None:
        ws_result = validate_workspace(toml_path)
        if ws_result["status"] == "fail":
            return {
                "status": "skipped",
                "exit_code": ws_result["exit_code"],
                "errors": ["Skipped due to workspace validation failure."] + ws_result["errors"],
                "report": None,
            }
        config = ws_result["config"]

    index_path = config.rag.index_path
    if not index_path.exists():
        return {
            "status": "fail",
            "exit_code": 1,
            "errors": [f"Document index path does not exist: {index_path}"],
            "report": None,
        }

    report = check_documents(index_path)
    if "error" in report:
        return {
            "status": "fail",
            "exit_code": 1,
            "errors": [report["error"]],
            "report": None,
        }

    if report["invalid_lines"] > 0:
        errors.append(f"Found {report['invalid_lines']} invalid JSON/schema lines.")
    if report["duplicate_ids"] > 0:
        errors.append(f"Found {report['duplicate_ids']} duplicate document IDs.")
    if report["empty_text_rows"] > 0:
        errors.append(f"Found {report['empty_text_rows']} documents with empty text.")

    if errors:
        return {
            "status": "fail",
            "exit_code": 1,
            "errors": errors,
            "report": report,
        }

    return {
        "status": "ok",
        "exit_code": 0,
        "errors": [],
        "report": report,
    }


def check_llama_health(base_url: str, timeout_seconds: int = 5) -> dict[str, Any]:
    root = base_url.rstrip("/")
    try:
        response = requests.get(f"{root}/health", timeout=timeout_seconds)
        if response.status_code == 404:
            # llama-cpp-python's OpenAI-compatible server exposes no /health route.
            response = requests.get(f"{root}/v1/models", timeout=timeout_seconds)
        reachable = response.status_code < 400
        return {
            "base_url": base_url,
            "reachable": reachable,
            "status_code": response.status_code,
            "error_detail": None if reachable else f"HTTP status {response.status_code}",
        }
    except Exception as exc:
        return {
            "base_url": base_url,
            "reachable": False,
            "status_code": None,
            "error_detail": str(exc) or exc.__class__.__name__,
        }


def check_llama(toml_path: Path | None, config: Config | None = None) -> dict[str, Any]:
    if config is None:
        ws_result = validate_workspace(toml_path)
        if ws_result["status"] == "fail":
            return {
                "status": "skipped",
                "exit_code": ws_result["exit_code"],
                "errors": ["Skipped due to workspace validation failure."] + ws_result["errors"],
                "base_url": None,
                "reachable": False,
                "status_code": None,
                "error_detail": "Workspace config invalid or missing",
            }
        config = ws_result["config"]

    base_url = config.runtime.base_url
    health_result = check_llama_health(base_url)

    if not health_result["reachable"]:
        return {
            "status": "fail",
            "exit_code": 3,
            "errors": [f"llama-server at {base_url} is unreachable: {health_result['error_detail']}"],
            "base_url": base_url,
            "reachable": False,
            "status_code": health_result["status_code"],
            "error_detail": health_result["error_detail"],
        }

    return {
        "status": "ok",
        "exit_code": 0,
        "errors": [],
        "base_url": base_url,
        "reachable": True,
        "status_code": health_result["status_code"],
        "error_detail": None,
    }


def output_result(
    status: Literal["ok", "fail", "skipped"],
    exit_code: int,
    workspace_path: Path | None,
    errors: list[str],
    json_mode: bool,
    extra_fields: dict[str, Any] | None = None,
    human_string: str | None = None,
) -> int:
    if json_mode:
        payload = {
            "status": status,
            "exit_code": exit_code,
            "workspace_path": str(workspace_path.resolve()) if workspace_path else None,
            "errors": errors,
        }
        if extra_fields:
            payload.update(extra_fields)
        print(json.dumps(payload, indent=2))
    else:
        if errors and status == "fail":
            for err in errors:
                print(f"Error: {err}", file=sys.stderr)
        if human_string:
            print(human_string)
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sutra", description="Lightweight local RAG runtime.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. sutra ask "question"
    ask_parser = subparsers.add_parser("ask", help="Ask one question against a Sutra workspace.")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--workspace", help="Path to sutra.toml or workspace directory.")
    ask_parser.add_argument("--echo", action="store_true", help="Use an echo LLM client for smoke tests.")
    ask_parser.add_argument("--json", action="store_true", help="Print the structured response as JSON.")
    ask_parser.add_argument("--backend", choices=["bm25", "qwen3", "hybrid", "lexical"], help="Override the RAG retrieval backend.")

    # 2. sutra workspace validate
    workspace_parser = subparsers.add_parser("workspace", help="Manage or inspect workspace configuration.")
    workspace_subparsers = workspace_parser.add_subparsers(dest="subcommand", required=True)
    
    workspace_validate_parser = workspace_subparsers.add_parser("validate", help="Validate workspace configuration and schema.")
    workspace_validate_parser.add_argument("--workspace", help="Path to sutra.toml or workspace directory.")
    workspace_validate_parser.add_argument("--json", action="store_true", help="Print the structured response as JSON.")

    # 3. sutra docs check
    docs_parser = subparsers.add_parser("docs", help="Inspect or check document index database.")
    docs_subparsers = docs_parser.add_subparsers(dest="subcommand", required=True)
    
    docs_check_parser = docs_subparsers.add_parser("check", help="Check document index health and counts.")
    docs_check_parser.add_argument("--workspace", help="Path to sutra.toml or workspace directory.")
    docs_check_parser.add_argument("--json", action="store_true", help="Print the structured response as JSON.")

    # 4. sutra batch
    batch_parser = subparsers.add_parser("batch", help="Batch process questions and output JSON.")
    batch_parser.add_argument("--input", required=True, help="Input JSON file path.")
    batch_parser.add_argument("--output", required=True, help="Output JSON file path.")
    batch_parser.add_argument("--live", action="store_true", help="Enable live fetch for stale evidence.")
    batch_parser.add_argument("--workspace", help="Path to sutra.toml or workspace directory.")
    batch_parser.add_argument("--echo", action="store_true", help="Use an echo LLM client for smoke tests.")
    batch_parser.add_argument(
        "--provenance",
        action="store_true",
        help="Write a <output>.provenance.json sidecar recording per-item mode (llm/llm_retry/fallback). Off by default.",
    )

    # 5. sutra llama health
    llama_parser = subparsers.add_parser("llama", help="Inspect or interact with llama-server.")
    llama_subparsers = llama_parser.add_subparsers(dest="subcommand", required=True)
    
    llama_health_parser = llama_subparsers.add_parser("health", help="Check health status of the running llama-server.")
    llama_health_parser.add_argument("--workspace", help="Path to sutra.toml or workspace directory.")
    llama_health_parser.add_argument("--json", action="store_true", help="Print the structured response as JSON.")

    # llama serve
    llama_serve_parser = llama_subparsers.add_parser("serve", help="Start llama-cpp-python server for serving the model.")
    llama_serve_parser.add_argument("--workspace", help="Path to sutra.toml or workspace directory.")
    llama_serve_parser.add_argument("--port", type=int, help="Port to run llama-server on.")
    llama_serve_parser.add_argument("--gpu-layers", type=int, default=-1, help="Number of layers to offload to GPU (-1 for all).")
    llama_serve_parser.add_argument("--chat-template-kwargs", help="JSON string passed to llama-cpp-python server (e.g. '{\"enable_thinking\": false}' for Qwen3 reasoning off).")
    llama_serve_parser.add_argument("--n-ctx", type=int, default=2048, help="Context size in tokens (default: 2048).")
    llama_serve_parser.add_argument("--dry-run", action="store_true", help="Print the command without executing.")

    # llama download
    llama_download_parser = llama_subparsers.add_parser("download", help="Download a GGUF model from Hugging Face.")
    llama_download_parser.add_argument("--workspace", help="Path to sutra.toml or workspace directory.")
    llama_download_parser.add_argument("--dest", help="Destination directory (overrides workspace config model directory).")
    llama_download_parser.add_argument("--repo-id", default="unsloth/Qwen3.5-9B-GGUF", help="Hugging Face repository ID.")
    llama_download_parser.add_argument("--filename", default="Qwen3.5-9B-Q4_K_M.gguf", help="GGUF filename in the repository.")
    llama_download_parser.add_argument("--json", action="store_true", help="Print structured JSON output.")

    # 5. sutra doctor
    doctor_parser = subparsers.add_parser("doctor", help="Run workspace validation, document check, and llama health checks.")
    doctor_parser.add_argument("--workspace", help="Path to sutra.toml or workspace directory.")
    doctor_parser.add_argument("--json", action="store_true", help="Print the structured response as JSON.")

    # 6. sutra ui
    ui_parser = subparsers.add_parser("ui", help="Launch the Sutra Chainlit web UI.")
    ui_parser.add_argument("--workspace", help="Path to sutra.toml or workspace directory.")
    ui_parser.add_argument("--host", default="127.0.0.1", help="Host to bind the UI server to.")
    ui_parser.add_argument("--port", type=int, default=8000, help="Port to run the UI server on.")
    ui_parser.add_argument("--echo", action="store_true", help="Use echo LLM client (no real LLM needed).")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    toml_path = None
    if args.command in _WORKSPACE_COMMANDS:
        cli_workspace = getattr(args, "workspace", None)
        try:
            toml_path = resolve_workspace_path(cli_workspace)
        except WorkspaceResolutionError as exc:
            if args.command == "doctor":
                toml_path = None
            else:
                return output_result(
                    status="fail",
                    exit_code=2,
                    workspace_path=None,
                    errors=[str(exc)],
                    json_mode=getattr(args, "json", False),
                )

    if args.command == "ask":
        try:
            config = load_config(toml_path)
            if args.backend:
                config.rag.backend = args.backend
            client = EchoClient() if args.echo else None
            answer = ask(args.question, workspace=config, client=client, trace_source="batch")
            if args.json:
                print(answer.model_dump_json(indent=2))
            else:
                print(answer.answer)
            return 0
        except ConfigError as exc:
            return output_result(
                status="fail",
                exit_code=1,
                workspace_path=toml_path,
                errors=[str(exc)],
                json_mode=args.json,
                human_string=f"Error: {exc}",
            )
        except LlamaError as exc:
            return output_result(
                status="fail",
                exit_code=3,
                workspace_path=toml_path,
                errors=[str(exc)],
                json_mode=args.json,
                human_string=f"Error: {exc}",
            )

    elif args.command == "batch":
        try:
            config = load_config(toml_path)

            input_path = resolve_input_path(args.input, config.root)
            with input_path.open("r", encoding="utf-8") as f:
                items: list[dict[str, str]] = json.load(f)

            input_uses_cwd = _is_relative_to(input_path, (Path.cwd() / "data").resolve()) and not _is_relative_to(
                input_path,
                (config.root / "data").resolve(),
            )
            output_path = resolve_output_path(args.output, config.root, prefer_cwd=input_uses_cwd)

            results: list[dict[str, str]] = []
            provenance: list[dict[str, str | int]] = []
            for i, item in enumerate(items):
                question = item.get("user") or item.get("question") or ""
                if not question:
                    message = "질문이 비어 있어 답변할 수 없습니다."
                    results.append(ChatOutputItem(user=question, model=message).model_dump())
                    provenance.append({"index": i, "mode": "fallback", "error": "missing question"})
                    print(f"WARNING: Item {i} used deterministic fallback: missing question", file=sys.stderr)
                    continue

                client = EchoClient() if args.echo else None
                try:
                    answer = ask(
                        question,
                        workspace=config,
                        live=args.live,
                        client=client,
                        mode="router",
                        trace_source="batch",
                    )
                    results.append(ChatOutputItem(user=question, model=answer.answer).model_dump())
                    provenance.append({"index": i, "mode": "llm", "error": ""})
                    continue
                except Exception as first_exc:
                    try:
                        answer = ask(
                            question,
                            workspace=config,
                            live=args.live,
                            client=client,
                            mode="router",
                            trace_source="batch",
                        )
                        results.append(ChatOutputItem(user=question, model=answer.answer).model_dump())
                        provenance.append({"index": i, "mode": "llm_retry", "error": str(first_exc)})
                        continue
                    except Exception as second_exc:
                        answer = fallback_answer(question, workspace=config)
                        results.append(ChatOutputItem(user=question, model=answer.answer).model_dump())
                        provenance.append({"index": i, "mode": "fallback", "error": str(second_exc)})
                        print(
                            f"WARNING: Item {i} used deterministic fallback: {second_exc}",
                            file=sys.stderr,
                        )

            ChatOutput.model_validate(results)

            output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
            if getattr(args, "provenance", False):
                provenance_path = output_path.with_suffix(".provenance.json")
                provenance_path.write_text(json.dumps(provenance, indent=2, ensure_ascii=False), encoding="utf-8")
            return 0

        except ConfigError as exc:
            return output_result(
                status="fail",
                exit_code=1,
                workspace_path=toml_path,
                errors=[str(exc)],
                json_mode=False,
                human_string=f"Error: {exc}",
            )
        except LlamaError as exc:
            return output_result(
                status="fail",
                exit_code=3,
                workspace_path=toml_path,
                errors=[str(exc)],
                json_mode=False,
                human_string=f"Error: {exc}",
            )
        except (FileNotFoundError, PermissionError, json.JSONDecodeError) as exc:
            return output_result(
                status="fail",
                exit_code=1,
                workspace_path=toml_path,
                errors=[str(exc)],
                json_mode=False,
                human_string=f"Error reading input: {exc}",
            )
        except Exception as exc:
            return output_result(
                status="fail",
                exit_code=1,
                workspace_path=toml_path,
                errors=[str(exc)],
                json_mode=False,
                human_string=f"Unexpected error: {exc}",
            )

    elif args.command == "workspace" and args.subcommand == "validate":
        res = validate_workspace(toml_path)
        return output_result(
            status=res["status"],
            exit_code=res["exit_code"],
            workspace_path=toml_path,
            errors=res["errors"],
            json_mode=args.json,
            human_string=f"Workspace configuration is valid.\nPath: {toml_path}" if res["status"] == "ok" else "Workspace validation failed:\n" + "\n".join(f"- {e}" for e in res["errors"]),
        )

    elif args.command == "docs" and args.subcommand == "check":
        res = check_docs(toml_path)
        report = res["report"]
        errors = res["errors"]
        status = res["status"]
        exit_code = res["exit_code"]

        human_string = ""
        if status == "ok":
            index_path = load_config(toml_path).rag.index_path if toml_path else ""
            human_string = (
                f"Document index check passed.\n"
                f"Path: {index_path}\n"
                f"Total documents: {report['total_documents']}\n"
                f"Invalid lines: {report['invalid_lines']}\n"
                f"Duplicate IDs: {report['duplicate_ids']}\n"
                f"Empty text rows: {report['empty_text_rows']}\n"
                f"Missing source_name count: {report['missing_source_name']}\n"
                f"Missing source_url count: {report['missing_source_url']}"
            )
        elif status == "skipped":
            human_string = "Document index check skipped:\n" + "\n".join(f"- {e}" for e in errors)
        else:
            human_string = "Document index check failed:\n" + "\n".join(f"- {e}" for e in errors)
            if report:
                human_string += (
                    f"\nTotal documents parsed: {report['total_documents']}\n"
                    f"Invalid lines: {report['invalid_lines']}\n"
                    f"Duplicate IDs: {report['duplicate_ids']}\n"
                    f"Empty text rows: {report['empty_text_rows']}"
                )

        extra = {"report": report} if report else {}
        return output_result(
            status=status,
            exit_code=exit_code,
            workspace_path=toml_path,
            errors=errors,
            json_mode=args.json,
            extra_fields=extra,
            human_string=human_string,
        )

    elif args.command == "llama" and args.subcommand == "health":
        res = check_llama(toml_path)
        status = res["status"]
        exit_code = res["exit_code"]
        errors = res["errors"]

        human_string = ""
        if status == "ok":
            human_string = (
                f"Llama server is healthy.\n"
                f"Base URL: {res['base_url']}\n"
                f"Reachable: {res['reachable']}\n"
                f"Status Code: {res['status_code']}"
            )
        elif status == "skipped":
            human_string = "Llama health check skipped:\n" + "\n".join(f"- {e}" for e in errors)
        else:
            human_string = (
                f"Llama server is unhealthy or unreachable.\n"
                f"Base URL: {res['base_url']}\n"
                f"Reachable: {res['reachable']}\n"
                f"Error: {res['error_detail']}"
            )

        extra = {
            "base_url": res["base_url"],
            "reachable": res["reachable"],
            "status_code": res["status_code"],
            "error_detail": res["error_detail"],
        }
        return output_result(
            status=status,
            exit_code=exit_code,
            workspace_path=toml_path,
            errors=errors,
            json_mode=args.json,
            extra_fields=extra,
            human_string=human_string,
        )

    elif args.command == "llama" and args.subcommand == "serve":
        config = load_config(toml_path)

        if args.port is not None:
            port = args.port
        else:
            try:
                parsed = urlparse(config.runtime.base_url)
                port = parsed.port or 18080
            except Exception:
                port = 18080

        model_path = config.runtime.model_path

        if args.dry_run:
            print(f"Resolved model path: {model_path}")

        ctk = args.chat_template_kwargs or config.runtime.chat_template_kwargs or None

        process = start_llama_server(model_path, port=port, gpu_layers=args.gpu_layers, chat_template_kwargs=ctk, dry_run=args.dry_run, n_ctx=args.n_ctx)

        if process is not None:
            try:
                process.wait()
            except KeyboardInterrupt:
                print("Terminating llama-server...")
                process.terminate()
                process.wait()
                sys.exit(0)
        return 0

    elif args.command == "llama" and args.subcommand == "download":
        config = load_config(toml_path)

        if args.dest is not None:
            dest_dir = Path(args.dest).expanduser().resolve()
        elif config.runtime.model_path is not None:
            dest_dir = config.runtime.model_path.parent
        else:
            dest_dir = _default_model_dir()

        if not args.json:
            print("Downloading model...")

        downloaded_path = download_model(dest_dir, repo_id=args.repo_id, filename=args.filename)

        return output_result(
            status="ok",
            exit_code=0,
            workspace_path=toml_path,
            errors=[],
            json_mode=args.json,
            human_string=f"Model downloaded to: {downloaded_path}",
            extra_fields={
                "downloaded_path": str(downloaded_path),
                "repo_id": args.repo_id,
                "filename": args.filename,
            },
        )

    elif args.command == "doctor":
        ws_res = validate_workspace(toml_path)
        config = ws_res.get("config")
        docs_res = check_docs(toml_path, config=config)
        llama_res = check_llama(toml_path, config=config)

        components = {
            "workspace": {
                "status": ws_res["status"],
                "errors": ws_res["errors"],
            },
            "docs": {
                "status": docs_res["status"],
                "errors": docs_res["errors"],
                "report": docs_res["report"],
            },
            "llama": {
                "status": llama_res["status"],
                "errors": llama_res["errors"],
                "base_url": llama_res["base_url"],
                "reachable": llama_res["reachable"],
                "status_code": llama_res["status_code"],
                "error_detail": llama_res["error_detail"],
            }
        }

        all_errors = []
        for comp in components.values():
            all_errors.extend(comp["errors"])

        if ws_res["status"] == "fail":
            exit_code = ws_res["exit_code"]
        elif docs_res["status"] == "fail":
            exit_code = 1
        elif llama_res["status"] == "fail":
            exit_code = 3
        else:
            exit_code = 0

        status = "ok" if exit_code == 0 else "fail"

        human_string = (
            f"[Workspace]\n"
            f"Status: {ws_res['status'].upper()}\n"
        )
        if ws_res["status"] == "ok":
            human_string += f"Path: {toml_path}\n"
        else:
            human_string += "\n".join(f"- {e}" for e in ws_res["errors"]) + "\n"

        human_string += f"\n[Documents]\nStatus: {docs_res['status'].upper()}\n"
        if docs_res["status"] == "ok":
            human_string += f"Total documents: {docs_res['report']['total_documents']}\n"
        else:
            human_string += "\n".join(f"- {e}" for e in docs_res["errors"]) + "\n"

        human_string += f"\n[Llama]\nStatus: {llama_res['status'].upper()}\n"
        if llama_res["status"] == "ok":
            human_string += f"Base URL: {llama_res['base_url']}\n"
        else:
            human_string += "\n".join(f"- {e}" for e in llama_res["errors"]) + "\n"

        extra = {"components": components}
        return output_result(
            status=status,
            exit_code=exit_code,
            workspace_path=toml_path,
            errors=all_errors,
            json_mode=args.json,
            extra_fields=extra,
            human_string=human_string.strip(),
        )

    elif args.command == "ui":
        import importlib.resources
        import importlib.util
        import pathlib
        import subprocess
        import tempfile

        if importlib.util.find_spec("chainlit") is None:
            return output_result(
                status="fail",
                exit_code=1,
                workspace_path=toml_path,
                errors=["chainlit is not installed. Install it with: uv sync --extra ui"],
                json_mode=False,
                human_string="chainlit is not installed. Install it with: uv sync --extra ui",
            )

        ui_path = importlib.resources.files("sutra").joinpath("ui.py")
        env = os.environ.copy()
        env["SUTRA_WORKSPACE"] = str(toml_path)
        if args.echo:
            env["SUTRA_ECHO"] = "1"

        temp_dir = tempfile.TemporaryDirectory(prefix="sutra-ui-")
        temp_root = pathlib.Path(temp_dir.name)
        env["CHAINLIT_APP_ROOT"] = str(temp_root)
        _prepare_chainlit_app_root(temp_root, toml_path)

        cmd = [
            sys.executable,
            "-m",
            "chainlit",
            "run",
            str(ui_path),
            "--host",
            args.host,
            "--port",
            str(args.port),
        ]

        process = subprocess.Popen(cmd, cwd=temp_dir.name, env=env)

        try:
            process.wait()
        except KeyboardInterrupt:
            process.terminate()
            process.wait()
        finally:
            try:
                temp_dir.cleanup()
            except (PermissionError, OSError):
                pass

        if process.returncode > 0:
            print(
                f"Warning: chainlit exited with code {process.returncode}",
                file=sys.stderr,
            )

        return process.returncode

    parser.error(f"unknown command: {args.command}")
    return 2


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
