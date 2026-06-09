# Project State

Last updated: 2026-06-09

This file is the primary memory document to read at the start of a new session. It outlines the active project direction and state.

## Active Project: Sutra

Sutra is a lightweight, local-first RAG runtime plus llama.cpp server client. 
- **Core Package**: [src/sutra](../src/sutra) is the main implementation surface. It is kept flat: `service.py`, `models.py`, `config.py`, `documents.py`, `retrieval.py`, `prompts.py`, `llama.py`, `cli.py`, `errors.py`.
- **Reference Workspace**: [examples/cnu-campus](../examples/cnu-campus) is an external workspace example implementing a CNU Campus Chatbot (referenced config is [sutra.toml](../examples/cnu-campus/sutra.toml)).
- **Legacy Packages**: The package [src/nlp_term](../src/nlp_term) is no longer active.
- For architectural guidelines, read [docs/sutra_architecture.md](sutra_architecture.md) before making core runtime changes.

## Current Workspace Data (CNU Campus Clean Corpus)

The active verified corpus consists of **355 clean documents** merged under [knowledge-index.jsonl](../examples/cnu-campus/data/processed/knowledge-index.jsonl):
- **Dining**: 20 documents
- **Shuttle**: 4 documents
- **Academic Calendar**: 326 documents
- **Graduation**: 5 documents

Raw source files are git-ignored, with raw provenance metadata tracked in `data/raw/**/*.meta.json`.

## Active Next Areas

1. **Retrieval Experiments**: Analyze Qwen embedding retrieval performance using [embedding_retrieval.py](../examples/cnu-campus/evals/embedding_retrieval.py).
2. **Docs Cleanup**: Complete Phase 1 documentation and metadata cleanups before uploading the project to GitHub.
3. **Future Work**:
   - Address CNU graduation requirements PDF OCR constraints (currently limited past page 3).
   - Implement tool-use / real-time information retrieval agent paths once the base RAG pipeline is stable.

## Legacy Reference Context (Assignment Tasks)

The old assignment-oriented task framing (Task 1 question classification, Task 2 chatbot simplification, and Task 3 real-time fetching) is kept for legacy context only. Development is unified under the Sutra RAG engine workspace layout. Do not follow old tool-call agent runtime plans or temporal/validator policy softening plans from earlier phases without a user request.

---

## Required Reading For Next Session

1. [README.md](../README.md)
2. [docs/project_state.md](project_state.md)
3. [docs/sutra_architecture.md](sutra_architecture.md)
4. [docs/doc_index.md](doc_index.md)
5. [examples/cnu-campus/README.md](../examples/cnu-campus/README.md)
