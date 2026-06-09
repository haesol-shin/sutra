# Sutra Architecture

Sutra is a lightweight local RAG runtime. The CNU Campus ChatBot is the first workspace that uses it, not a built-in project inside the core package.

## Current Scope

Sutra v1 provides:

- A flat Python package under `src/sutra`.
- A single-turn service entrypoint: `sutra.ask(...)` / `sutra.service.ask(...)`.
- External workspace configuration through `sutra.toml`.
- JSONL document loading.
- Lightweight lexical retrieval.
- Evidence context construction.
- Prompt rendering.
- A llama.cpp `llama-server` HTTP client.
- A CLI smoke path: `sutra ask`.

Sutra v1 does not provide:

- A vector database.
- Embedding or reranking.
- Tool calling or an agent runtime.
- Full OpenAI API compatibility.
- Streaming.
- A plugin registry.
- Python hooks inside workspace config.
- llama.cpp process management from Python.
- `sutra llama run` or any server launcher.
- CUDA/XPU routing logic inside the answer service.

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
```

Flat does not mean one large file. Each module owns one narrow responsibility:

- `service.py`: orchestrates `ask()` and `chat()`.
- `models.py`: public response, document, evidence, prompt, and LLM result models.
- `config.py`: loads and validates `sutra.toml`.
- `documents.py`: loads workspace JSONL documents.
- `retrieval.py`: ranks documents and builds/renders evidence context.
- `prompts.py`: renders LLM messages.
- `llama.py`: calls an already-running llama-server over HTTP.
- `cli.py`: provides `sutra ask`.

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

## Runtime

The first backend is llama.cpp `llama-server`.

Sutra talks to it through:

```text
GET  /health
POST /v1/chat/completions
```

`src/sutra/llama.py` is an HTTP client only. It does not build, install, start, stop, or supervise llama.cpp.

CUDA and XPU support belong to llama.cpp build/runtime documentation and launch profiles. Sutra core should keep speaking HTTP regardless of acceleration backend.

## API And UI

API and UI are later thin wrappers.

When added:

- FastAPI should translate the non-streaming `POST /v1/chat/completions` subset into `sutra.service.chat()`.
- Gradio should call `sutra.service.ask()` or `chat()`.
- Neither API nor UI should contain retrieval, prompt, evidence, or llama-server logic.

`chat()` is currently a single-turn adapter: it accepts OpenAI-style messages, selects the latest user message, and delegates to `ask()`. Multi-turn history injection is intentionally out of scope until it has a tested prompt contract.

## CLI

Sutra provides several CLI commands for query answering and workspace diagnostics:

- `sutra ask "question"`: Ask a question against a resolved Sutra workspace.
- `sutra workspace validate`: Validate workspace configuration schema and verify all referenced files exist.
- `sutra docs check`: Load and check document index database for schema compliance, duplicates, or empty texts.
- `sutra llama health`: Check GET `/health` of the configured `llama-server`.
- `sutra doctor`: Run workspace validate, docs check, and llama health checks, aggregating their statuses.

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

