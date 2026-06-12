# Sutra Architecture

Sutra is a lightweight local RAG runtime. The CNU Campus ChatBot is the first workspace that uses it, not a built-in project inside the core package.

## Current Scope

Sutra v1 provides:

- A flat Python package under `src/sutra`.
- A single-turn service entrypoint: `sutra.ask(...)` / `sutra.service.ask(...)`.
- External workspace configuration through `sutra.toml`.
- JSONL document loading.
- Lexical and BM25 retrieval.
- Evidence context construction.
- Prompt rendering.
- A llama.cpp `llama-server` HTTP client.
- Tool calling (live `fetch_*` tools + a `search_knowledge_base` tool) and a Task1-classifier forced-tool router (`mode="router"`).
- A CLI: `sutra ask`, `sutra batch`, `sutra llama`, `sutra ui`, `sutra doctor`, `sutra workspace`, `sutra docs`.

Sutra v1 does not provide:

- A vector database.
- Embedding or reranking.
- An autonomous multi-step agent runtime (tool calling is single-shot / router-forced, not an agent loop).
- Full OpenAI API compatibility.
- Streaming (outside the Chainlit UI adapter).
- A formal workspace plugin registry or Python hooks inside workspace config (**planned/deferred** — see below).
- llama.cpp build, installation, or daemon supervision (the CLI provides thin foreground launch wrappers, not a process manager).
- CUDA/XPU routing logic inside the answer service.

> **Current reality vs. the domain-agnostic goal**: Sutra is intended as a domain-agnostic RAG runtime where each use case is an external workspace. Today that separation is **incomplete**. The tool-calling layer and the forced-tool router currently carry CNU-specific implementation **inside the engine**, not in the workspace:
>
> - `src/sutra/tools.py` hardcodes CNU live tools and data: source URLs (`mobileadmin.cnu.ac.kr`, `plus.cnu.ac.kr`, `computer.cnu.ac.kr`), cafeteria constants (`CAFETERIAS`, `CAFETERIA_MENU_CHOICES`, `CAFETERIA_ENUM`), the notice-board registry/`SOURCE_REGISTRY`, the display↔internal board maps, and the `fetch_recent_notices` / `fetch_cafeteria_menu` / `fetch_academic_calendar` / `fetch_page_text` handlers with their HTML/OCL parsers.
> - `src/sutra/service.py` hardcodes the CNU router policy: `ROUTER_DOMAINS`, `ROUTER_FORCED_TOOLS`, the classifier path, and Korean user-facing strings.
> - `src/sutra/dining_router.py`, `src/sutra/menu_resolver.py`, and `src/sutra/dining_format.py` are CNU dining (학식) logic.
>
> A workspace-plugin boundary that moves this CNU implementation out of `src/sutra` (declarative data into `sutra.toml`, parsers/handlers into a trusted workspace plugin loaded through a config-keyed registry) is **planned and deferred**, gated behind frozen-grading-path compatibility. It does **not** exist yet: CNU data does **not** currently live in `sutra.toml` or a `plugin.py`. Characterization tests (`tests/sutra/test_characterization.py`) and an import inventory (`tests/sutra/test_import_inventory.py`) pin the current surface so the deferred move can prove zero regression.

> **Core vs. CLI distinction**: The answer service (`sutra.service.ask()`, `sutra.service.chat()`) is HTTP-client-only — it talks to an already-running llama-server. The CLI includes thin convenience commands (`sutra llama serve`, `sutra llama download`) for local development, evaluator convenience, and demo setup. These are not a daemon manager, process supervisor, or llama.cpp installer.

## Package Layout

The package uses Python's `src/` layout and a flat v1 package:

```text
src/sutra/
  __init__.py
  config.py
  models.py
  documents.py
  retrieval.py
  prompts.py
  llama.py
  service.py
  cli.py
  errors.py
  ui.py
  resources/
    ui/
      chainlit_config.toml
```

Flat does not mean one large file. Each module owns one narrow responsibility:

- `service.py`: orchestrates `ask()` and `chat()`.
- `models.py`: public response, document, evidence, prompt, and LLM result models.
- `config.py`: loads and validates `sutra.toml`.
- `documents.py`: loads workspace JSONL documents.
- `retrieval.py`: ranks documents and builds/renders evidence context.
- `prompts.py`: renders LLM messages.
- `llama.py`: calls an already-running llama-server over HTTP.
- `cli.py`: provides `sutra ask` and other subcommands.
- `ui.py`: Chainlit web UI adapter that calls `sutra.service.ask()` via `cl.make_async`.

Nested packages such as `core/`, `rag/`, `llm/`, or `workspace/` should wait until real module size or duplication proves the need.

Sutra uses package-absolute imports such as `from sutra.config import Config`. These are normal Python package imports, not filesystem absolute paths. Runtime file paths should come from `sutra.toml` and be resolved relative to the workspace config file.

## Data Models

Sutra uses `pydantic` for public and external boundaries:

- workspace config
- JSONL documents
- `Answer`
- `Evidence`
- llama-server response parsing

Use `dataclasses` only for lightweight internal values that do not need runtime validation.

The core document schema is domain-neutral:

```json
{
  "id": "doc-1",
  "title": "Document title",
  "text": "Document body",
  "source_url": "https://example.com",
  "source_name": "Example Source",
  "metadata": {
    "label": "optional-workspace-label"
  }
}
```

CNU labels and domains belong in `metadata`, not in Sutra core enums.

## Workspace Format

Each use case is an external workspace:

```text
workspace/
  sutra.toml
  data/
    index.jsonl
  prompts/
    system.md
    answer.md
  evals/
    smoke.json
```

Minimal config:

```toml
[workspace]
name = "example"
timezone = "Asia/Seoul"

[runtime]
backend = "llama-server"
base_url = "http://127.0.0.1:18080"
model = "qwen-local"
model_path = "model/generator/Qwen3.5-9B-Q4_K_M.gguf"
temperature = 0.2
max_tokens = 512

[rag]
index_path = "data/index.jsonl"
top_k = 8
max_fact_chars = 500

[prompts]
system = "prompts/system.md"
answer = "prompts/answer.md"
```

All relative paths resolve from the `sutra.toml` directory.

`runtime.model_path` is optional — if omitted, model storage defaults to the user cache directory (`~/.cache/sutra/models/` on Linux/macOS, `%LOCALAPPDATA%/sutra/models/` on Windows). `runtime.reasoning` is also optional; when set to `"on"`, `"off"`, or `"auto"` it controls the `--reasoning` flag passed to `llama-server`.

## Runtime

The first backend is llama.cpp `llama-server`.

The answer service talks to an already-running server through:

```text
GET  /health
POST /v1/chat/completions
```

`src/sutra/llama.py` provides `LlamaClient`, an HTTP client for these endpoints. It does not build, install, or supervise llama.cpp.

The CLI includes convenience commands for local development and evaluation:

- **`sutra llama serve`** — Locates an existing `llama-server` binary (via `PATH` or `LLAMA_SERVER_PATH`) and launches it in the foreground with the model from `runtime.model_path`. This is a thin wrapper: it does not build llama.cpp, install dependencies, or supervise the process. Logs appear in the terminal; Ctrl+C terminates both the wrapper and the child process. Supports `--dry-run`, `--port`, `--gpu-layers`, and `--reasoning on/off/auto`.
- **`sutra llama download`** — Downloads a GGUF model from Hugging Face via `huggingface_hub`. Requires the `rag` optional extra. Destination defaults to `runtime.model_path`; override with `--dest`.
- **`sutra llama health`** — Checks `GET /health` of the configured base URL.

`runtime.model_path` and `runtime.reasoning` are optional config fields. If `model_path` is unset, Sutra resolves the model path from `SUTRA_MODEL_PATH`, `SUTRA_MODEL_DIR`, or the system user cache (`~/.cache/sutra/models/`). Workspace config describes RAG docs and prompts; large model artifacts should not be committed to the repository.

CUDA and XPU support belong to llama.cpp build/runtime documentation and launch profiles. Sutra core speaks HTTP regardless of acceleration backend.

## API And UI

API and UI are thin wrappers over the service layer.

- **Chainlit UI** (`sutra ui`): A Chainlit web UI that calls `sutra.service.ask()` via `cl.make_async`. It formats the answer and evidence sources in Markdown without heavy Chainlit Elements. Supports echo mode (`--echo`) for smoke testing without a real LLM backend.
- **No REST API yet**: FastAPI integration is planned for translating the non-streaming `POST /v1/chat/completions` subset into `sutra.service.chat()`.
- Neither UI nor future API should contain retrieval, prompt, evidence, or llama-server logic.

`chat()` is currently a single-turn adapter: it accepts OpenAI-style messages, selects the latest user message, and delegates to `ask()`. Multi-turn history injection is intentionally out of scope until it has a tested prompt contract.

## CLI

Sutra provides several CLI commands for query answering, workspace diagnostics, and the web UI:

- `sutra ask "question"`: Ask a question against a resolved Sutra workspace.
- `sutra workspace validate`: Validate workspace configuration schema and verify all referenced files exist.
- `sutra docs check`: Load and check document index database for schema compliance, duplicates, or empty texts.
- `sutra llama health`: Check GET `/health` of the configured `llama-server`.
- `sutra llama serve`: Launch `llama-server` in the foreground using the configured model.
- `sutra llama download`: Download a GGUF model from Hugging Face.
- `sutra doctor`: Run workspace validate, docs check, and llama health checks, aggregating their statuses.
- `sutra ui`: Launch the Chainlit web UI. Accepts `--host`, `--port`, `--workspace`, and `--echo`. Requires the `ui` optional extra.

### Workspace Resolution

Commands requiring a workspace resolve the `sutra.toml` file in the following priority:
1. `--workspace path` CLI argument.
2. `SUTRA_WORKSPACE` environment variable.
3. Walk upward from the current working directory.
4. If not found, fail with exit code 2.

### JSON Output

All commands support `--json` which prints a stable, structured JSON payload:

```json
{
  "status": "ok" | "fail" | "skipped",
  "exit_code": number,
  "workspace_path": string | null,
  "errors": [...]
}
```

For `sutra doctor`, the payload also includes a `components` object mapping the status of each check.

