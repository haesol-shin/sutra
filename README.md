# Sutra

Sutra is a lightweight, local-first RAG (Retrieval-Augmented Generation) runtime designed for running question-answering pipelines on top of local llama.cpp server backends.

This repository is organized as follows:
- **Core Engine ([src/sutra](src/sutra))**: The active, clean Python package implementation containing RAG services, retrieval scoring, CLI, prompts, llama.cpp client interfaces, and a Chainlit web UI adapter.
- **Example Workspace ([examples/cnu-campus](examples/cnu-campus))**: A complete reference workspace implementing a Campus Chatbot helper for Chungnam National University (CNU) students.
- **Legacy Code ([src/nlp_term](src/nlp_term))**: The original, legacy package layout which is no longer active.

---

## Environment Setup

Use `uv` and Python 3.10.12.

```powershell
uv python install 3.10.12
uv sync --extra xpu
```

For the Chainlit web UI, also install the `ui` extra:
```powershell
uv sync --extra xpu --extra ui
```

This installs the local XPU development PyTorch build through the PyTorch XPU index:
```text
torch 2.9.1+xpu
pytorch-triton-xpu 3.5.0
```

### Verification
```powershell
uv run python --version
uv run python -c "import torch; print(torch.__version__); print(torch.xpu.is_available())"
```

> [!NOTE]
> **PyTorch XPU Version Note:**
> - The original assignment document lists `torch 2.5.1`.
> - However, `torch 2.5.1+xpu` failed to import locally due to a missing `c10_xpu.dll` dependency.
> - `torch 2.9.1+xpu` is the current local development default because it correctly imports and detects XPU. Revisit this if strict version matching is required before final submission.

---

## Workspace & Data Policy

The CNU Campus ([examples/cnu-campus](examples/cnu-campus)) workspace operates under these rules:
- **Clean Corpus**: The active index contains **94 clean documents** merged under [knowledge-index.jsonl](examples/cnu-campus/data/processed/knowledge-index.jsonl) (dining: 12 docs, shuttle: 3 docs, academic calendar: 50 docs, graduation: 5 docs, notices: 24 docs). This is separate from the legacy, noisy 2414-document `knowledge_seed.json` corpus.
- **Raw Data Policy**: Raw source files are ignored by Git. Raw provenance metadata is tracked via `data/raw/**/*.meta.json` (such as [computer_ai_2026_graduation_requirements.meta.json](data/raw/graduation/computer_ai_2026_graduation_requirements.meta.json)).

---

## Useful Commands

### 1. Synchronize Dependencies
```powershell
uv sync --extra xpu
```

### 2. Workspace Document Validation (Docs Check)
Validate the integrity and counts of the workspace corpus:
```powershell
uv run python -m sutra.cli docs check --workspace examples/cnu-campus/sutra.toml --json
```

### 3. Run Embedding Retrieval Experiment
Run the optional embedding retrieval experiment using sentence-transformers:
```powershell
# Sync optional RAG dependencies first
uv sync --extra xpu --extra rag
# Run retrieval evaluation
uv run python examples/cnu-campus/evals/embedding_retrieval.py
```
*Note: Embeddings caches are stored under `examples/cnu-campus/.cache/` and are git-ignored.*

### 4. Download a GGUF Model
```powershell
uv run sutra llama download --workspace examples/cnu-campus/sutra.toml
```
*Requires the `rag` optional extra for `huggingface_hub`.*

### 5. Launch llama-server (Foreground)
```powershell
# Preview the command without executing
uv run sutra llama serve --workspace examples/cnu-campus/sutra.toml --dry-run
# Start serving
uv run sutra llama serve --workspace examples/cnu-campus/sutra.toml
```

### 6. Check Server Health
```powershell
uv run sutra llama health --workspace examples/cnu-campus/sutra.toml
```

### 7. Ask a Question (Echo Smoke Test)
```powershell
uv run sutra ask --workspace examples/cnu-campus/sutra.toml --echo "수강신청은 언제 시작하나요?"
```

### 8. Launch the Chainlit Web UI
```powershell
# Requires the ui extra: uv sync --extra ui
uv run sutra ui --workspace examples/cnu-campus/sutra.toml --echo --port 8000
```

The UI wraps `sutra.service.ask()` in a Chainlit chat interface. Use `--echo` to test without a real llama-server backend.

---

## Model Path Resolution

When no explicit model path is configured, Sutra stores and looks for models in the user cache directory:
- **Linux/macOS**: `~/.cache/sutra/models/Qwen3.5-9B-Q4_K_M.gguf`
- **Windows**: `%LOCALAPPDATA%/sutra/models/Qwen3.5-9B-Q4_K_M.gguf`

The resolution precedence is:

1. **`SUTRA_MODEL_PATH`** — Exact GGUF model file path (highest priority, overrides everything)
2. **`runtime.model_path`** — Path from workspace config (resolved relative to workspace root if relative)
3. **`SUTRA_MODEL_DIR`** — Directory containing the default GGUF filename (only when no exact path is set)
4. **User cache default** — Platform-appropriate cache directory

> [!NOTE]
> Do not confuse `SUTRA_MODEL_PATH` (file path) with `SUTRA_MODEL` (llama-server model label). The latter only controls the `model` field in the OpenAI-compatible API request body.

---

## Workspace Selection Shortcuts

Sutra resolves the workspace config (`sutra.toml`) in this order:
1. `--workspace <path>` CLI argument
2. `SUTRA_WORKSPACE` environment variable
3. Walk upward from the current directory

To avoid repeating `--workspace examples/cnu-campus/sutra.toml`:

**Set the environment variable (PowerShell):**
```powershell
$env:SUTRA_WORKSPACE = "examples/cnu-campus/sutra.toml"
uv run sutra ask --echo "수강신청은 언제 시작하나요?"
```

**Set the environment variable (cmd):**
```cmd
set SUTRA_WORKSPACE=examples\cnu-campus\sutra.toml
uv run sutra ask --echo "수강신청은 언제 시작하나요?"
```

**Run from the workspace directory:**
```powershell
cd examples/cnu-campus
uv run sutra ask --echo "수강신청은 언제 시작하나요?"
```

These shortcuts work with any command that accepts `--workspace`, including `sutra ask`, `sutra ui`, `sutra docs check`, `sutra workspace validate`, `sutra doctor`, and all `sutra llama` subcommands.

---

## Project Documentation
- [Sutra Architecture](docs/sutra_architecture.md): Deep dive into the RAG package boundaries, config, and runtime.
- [Project State](docs/project_state.md): Active next areas, corpus counts, and legacy status.
- [Document Index](docs/doc_index.md): Source-of-truth document registry.
- [CNU Campus README](examples/cnu-campus/README.md): Details about the CNU example workspace.
