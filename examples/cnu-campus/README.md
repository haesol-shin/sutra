# CNU Campus Workspace

A reference Sutra workspace implementing the CNU Campus ChatBot use case.

## Clean Corpus Counts

The active checked-in clean index is compiled into [data/processed/knowledge-index.jsonl](data/processed/knowledge-index.jsonl), containing a total of **355 clean documents**:
- **Dining**: 20 documents
- **Shuttle**: 4 documents
- **Academic Calendar**: 326 documents
- **Graduation**: 5 documents

This is separate from the legacy, noisy 2414-document `knowledge_seed.json` corpus, which is no longer active.

## Raw Source Files & Metadata

Raw data sources are kept git-ignored under `data/raw/` directories. Provenance tracking metadata is checked in and tracked under `data/raw/**/*.meta.json`.

> [!WARNING]
> **Graduation OCR Constraint:** Graduation requirements source parsing is currently limited past page 3 of the source PDF due to OCR extraction boundaries.

---

## Workspace Build & Eval Scripts

The workspace contains the following scripts:

### Build Scripts
- `examples/cnu-campus/scripts/build_dining_index.py`: Parses raw dining HTML and builds the dining index.
- `examples/cnu-campus/scripts/build_shuttle_index.py`: Parses shuttle schedule tables and builds the shuttle index.
- `examples/cnu-campus/scripts/build_calendar_index.py`: Parses the CNU academic calendar and builds the calendar index.
- `examples/cnu-campus/scripts/build_graduation_index.py`: Parses graduation requirements and builds the graduation index.
- `examples/cnu-campus/scripts/build_clean_index.py`: Merges all individual domain indexes into the single `knowledge-index.jsonl`.

### Evaluation Runners
- [run_probe39.py](evals/run_probe39.py): Runs the evaluation runner over 39 diagnostic questions.
- [embedding_retrieval.py](evals/embedding_retrieval.py): Conducts embedding retrieval experiments using sentence-transformers (requires the `rag` optional extra; local cache is git-ignored under `examples/cnu-campus/.cache/`).

---

## Model Setup

The workspace is configured to use `Qwen3.5-9B-Q4_K_M.gguf` (see `runtime.model_path` in [sutra.toml](sutra.toml)). Download it and launch the server:

```powershell
# Requires the `rag` optional extra
uv run sutra llama download --workspace examples/cnu-campus/sutra.toml
# Dry-run to verify the command
uv run sutra llama serve --workspace examples/cnu-campus/sutra.toml --dry-run
# Start llama-server in the foreground
uv run sutra llama serve --workspace examples/cnu-campus/sutra.toml
```

## Quick Start

Ask a question using the echo backend to verify the workspace is parsed correctly:
```powershell
uv run sutra ask --workspace examples/cnu-campus/sutra.toml --echo "수강신청은 언제 시작하나요?"
```
