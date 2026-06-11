# Project State

Last updated: 2026-06-12

This file is the primary memory document to read at the start of a new session. It outlines the active project direction and state.

## Active Project: Sutra

Sutra is a lightweight, local-first RAG runtime plus llama.cpp server client. 
- **Core Package**: [src/sutra](../src/sutra) is the main implementation surface. It is kept flat: `service.py`, `models.py`, `config.py`, `documents.py`, `retrieval.py`, `prompts.py`, `llama.py`, `cli.py`, `errors.py`, `ui.py` (+ `resources/ui/` for packaged Chainlit config).
- **Reference Workspace**: [examples/cnu-campus](../examples/cnu-campus) is an external workspace example implementing a CNU Campus Chatbot (referenced config is [sutra.toml](../examples/cnu-campus/sutra.toml)).
- **Legacy Packages**: The package [src/nlp_term](../src/nlp_term) is partially active: `nlp_term.classify.predict` (Task1 classifier) is reused as a domain router for retrieval/tool routing.
- For architectural guidelines, read [docs/sutra_architecture.md](sutra_architecture.md) before making core runtime changes.

## Current Workspace Data (CNU Campus Clean Corpus)

The active verified corpus consists of **94 clean documents** merged under [knowledge-index.jsonl](../examples/cnu-campus/data/processed/knowledge-index.jsonl):
- **Academic Calendar**: 50 documents
- **Notices**: 24 documents
- **Dining**: 12 documents (5 per-day menu docs with 아침/점심/저녁 labels, 1 dining_operating_info doc, 6 제1학생회관 food-court corner docs for 라면&간식/양식/스낵/한식/일식/중식)
- **Graduation**: 5 documents
- **Shuttle**: 3 documents

Raw source files are git-ignored, with raw provenance metadata tracked in `data/raw/**/*.meta.json`.

## Active Next Areas

1. **Retrieval Experiments**: Analyze Qwen embedding retrieval performance using [embedding_retrieval.py](../examples/cnu-campus/evals/embedding_retrieval.py).
2. **Docs Cleanup**: Complete Phase 1 documentation and metadata cleanups before uploading the project to GitHub.
3. **Live Tool Integration**: Real-time tools are now implemented in [src/sutra/tools.py](../src/sutra/tools.py):
   - `fetch_recent_notices`: Retrieves live notices
   - `fetch_cafeteria_menu`: Fetches live menus formatted via shared [src/sutra/dining_format.py](../src/sutra/dining_format.py) in same clean 아침/점심/저녁 format as corpus
   - `fetch_academic_calendar`: Retrieves calendar data
   - `fetch_page_text`: Fetches page content
   - `search_knowledge_base`: RAG exposed as a tool for equal footing with live tools
   - Relative-date query expansion: `retrieve()` appends KST date tokens for 오늘/내일/모레/어제 to BM25 query (original question preserved)
4. **Service Modes**: `service.ask()` supports `mode="default"` (RAG pre-injected + autonomous tools), `mode="tool_only"` (RAG and tools on equal footing), and `mode="router"` (Task1-classifier forced tool routing for dining/notices, RAG for calendar/graduation/shuttle; includes Option A — forced tools fire even on empty RAG). Default remains the byte-invariant grading path.
5. **Routing Decision (pending)**: A3 router is the chosen routing design. A large default-vs-router experiment (58 probes, n_ctx 8192, 94-doc corpus) is the basis for deciding whether to switch the grading path from default to router; the switch is the user's call from the report.
6. **Notices/Dining Tools**: `fetch_recent_notices` now covers 5 boards (학교 학사공지/새소식, 학부 학사공지/소식/사업단) with optional board, client-side keyword filtering, and body excerpts. `fetch_cafeteria_menu` blocks out-of-range dates via menu-body comparison.
7. **Future Work**:
   - Address CNU graduation requirements PDF OCR constraints (currently limited past page 3).
   - Hybrid BM25+embedding retrieval (50/50, decided but unimplemented).

## Legacy Reference Context (Assignment Tasks)

The old assignment-oriented task framing (Task 1 question classification, Task 2 chatbot simplification, and Task 3 real-time fetching) is kept for legacy context only. Development is unified under the Sutra RAG engine workspace layout. Do not follow old tool-call agent runtime plans or temporal/validator policy softening plans from earlier phases without a user request.

---

## Required Reading For Next Session

1. [README.md](../README.md)
2. [docs/project_state.md](project_state.md)
3. [docs/sutra_architecture.md](sutra_architecture.md)
4. [docs/doc_index.md](doc_index.md)
5. [examples/cnu-campus/README.md](../examples/cnu-campus/README.md)
