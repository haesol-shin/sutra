# Sutra

Sutra is a lightweight, local-first RAG runtime for building workspace-based question answering systems on top of a local `llama.cpp` server. It provides a Python package, a CLI, document-index checks, local model helpers, batch processing, and an optional Chainlit UI.

Sutra is developed and tested on Windows with PowerShell-first commands. The bundled CNU Campus workspace is an example of how to configure a real campus chatbot; see [examples/cnu-campus](examples/cnu-campus) for its data and workspace-specific notes.

## Install

Use Python 3.10.12 or newer and `uv`.

```powershell
uv python install 3.10.12
uv sync --extra rag
```

For local model serving on the Windows XPU development path:

```powershell
uv sync --extra xpu --extra rag
```

For the optional Chainlit UI:

```powershell
uv sync --extra xpu --extra rag --extra ui
```

Common runtime extras:

| Extra | Purpose |
| --- | --- |
| `rag` | BM25/tokenization dependencies used by retrieval |
| `xpu` | Windows local model serving path with XPU-oriented dependencies |
| `cuda` | CUDA-oriented local model serving path |
| `ui` | Chainlit web UI |
| `embeddings` | Optional sentence-transformers retrieval experiments |

## Quick Start

Start with the bundled example workspace and the echo client. This validates the workspace, checks the document index, and runs one question without starting a model server.

```powershell
uv run sutra workspace validate --workspace examples/cnu-campus/sutra.toml --json
uv run sutra docs check --workspace examples/cnu-campus/sutra.toml --json
uv run sutra ask --workspace examples/cnu-campus/sutra.toml --echo "수강신청은 언제 시작하나요?"
```

## Workspaces

Sutra runs against a `sutra.toml` workspace. A workspace points to the document index, prompts, runtime settings, evaluation files, and optional model configuration.

Workspace resolution order:

1. `--workspace <path>`
2. `SUTRA_WORKSPACE`
3. Search upward from the current directory for `sutra.toml`

You can also run commands from inside a workspace:

```powershell
cd examples/cnu-campus
uv run sutra ask --echo "수강신청은 언제 시작하나요?"
```

## Run With A Local Model

Download the default GGUF model, start `llama-server`, then ask without `--echo`.

```powershell
uv run sutra llama download --workspace examples/cnu-campus/sutra.toml
uv run sutra llama serve --workspace examples/cnu-campus/sutra.toml
```

In another terminal:

```powershell
uv run sutra ask --workspace examples/cnu-campus/sutra.toml "수강신청은 언제 시작하나요?"
```

Useful server checks:

```powershell
uv run sutra llama serve --workspace examples/cnu-campus/sutra.toml --dry-run
uv run sutra llama health --workspace examples/cnu-campus/sutra.toml --json
```

## CLI

| Command | Use |
| --- | --- |
| `sutra ask` | Ask one question against a workspace |
| `sutra batch` | Process a JSON question file and write JSON answers |
| `sutra workspace validate` | Validate workspace config and referenced paths |
| `sutra docs check` | Check document-index health and counts |
| `sutra llama download` | Download a GGUF model from Hugging Face |
| `sutra llama serve` | Start the local `llama-cpp-python` server |
| `sutra llama health` | Check the running model server |
| `sutra doctor` | Run workspace, docs, and server checks together |
| `sutra ui` | Launch the optional Chainlit UI |

Examples:

```powershell
uv run sutra batch --workspace examples/cnu-campus/sutra.toml --input data/test_chat.json --output outputs/chat_output.json --echo
uv run sutra doctor --workspace examples/cnu-campus/sutra.toml --json
uv run sutra ui --workspace examples/cnu-campus/sutra.toml --echo --port 8000
```

## Configuration

By default, Sutra stores downloaded models in the platform user cache. On Windows this is under `%LOCALAPPDATA%\sutra\models`.

Model path overrides:

| Setting | Use |
| --- | --- |
| `SUTRA_MODEL_PATH` | Exact GGUF file path |
| `SUTRA_MODEL_DIR` | Directory containing the default GGUF filename |
| `runtime.model_path` | Workspace-level model path in `sutra.toml` |

Common runtime fields live in the workspace config:

```toml
[runtime]
base_url = "http://127.0.0.1:18080"
model = "qwen-local"
```

## Development

Run focused checks before changing runtime behavior:

```powershell
uv run sutra workspace validate --workspace examples/cnu-campus/sutra.toml --json
uv run sutra docs check --workspace examples/cnu-campus/sutra.toml --json
uv run pytest -q
uv run ruff check
```

## Documentation

- [Sutra Architecture](docs/sutra_architecture.md): package boundaries, workspace format, and runtime design
- [Project State](docs/project_state.md): current project state and active directions
- [Document Index](docs/doc_index.md): source-of-truth document registry
- [CNU Campus Workspace](examples/cnu-campus/README.md): example workspace details
