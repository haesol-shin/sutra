# Sutra

Sutra is a lightweight, local-first RAG (Retrieval-Augmented Generation) runtime designed for running question-answering pipelines on top of local llama.cpp server backends.

This repository is organized as follows:
- **Core Engine ([src/sutra](src/sutra))**: The active, clean Python package implementation containing RAG services, retrieval scoring, CLI, prompts, and llama.cpp client interfaces.
- **Example Workspace ([examples/cnu-campus](examples/cnu-campus))**: A complete reference workspace implementing a Campus Chatbot helper for Chungnam National University (CNU) students.
- **Legacy Code ([src/nlp_term](src/nlp_term))**: The original, legacy package layout which is no longer active.

---

## Environment Setup

Use `uv` and Python 3.10.12.

```powershell
uv python install 3.10.12
uv sync --extra xpu
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
- **Clean Corpus**: The active index contains **355 clean documents** merged under [knowledge-index.jsonl](examples/cnu-campus/data/processed/knowledge-index.jsonl) (dining: 20 docs, shuttle: 4 docs, academic calendar: 326 docs, graduation: 5 docs). This is separate from the legacy, noisy 2414-document `knowledge_seed.json` corpus.
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

---

## Project Documentation
- [Sutra Architecture](docs/sutra_architecture.md): Deep dive into the RAG package boundaries, config, and runtime.
- [Project State](docs/project_state.md): Active next areas, corpus counts, and legacy status.
- [Document Index](docs/doc_index.md): Source-of-truth document registry.
- [CNU Campus README](examples/cnu-campus/README.md): Details about the CNU example workspace.
