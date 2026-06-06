# Pre-Colab Progress

작성일: 2026-06-06

이 문서는 `docs/pre_colab_goal_plan.md`의 단계별 실행 결과를 기록한다.

## Phase 0.1 Current State Snapshot

- status: pass
- command:
  - `git status --short --ignored`
  - `git log --oneline -3`
- result:
  - tracked dirty files: none
  - ignored/generated artifacts observed: `.omx/`, `.ruff_cache/`, `.venv/`, `data/raw/`, `data/sources/`, `model/`, `outputs/`, `tmp/`, Python cache directories
  - latest commits:
    - `4694204 docs: define pre-colab execution gates`
    - `98da8bf feat: add source-backed data pipeline scaffolding`
    - `129ed3a feat: add submission skeleton and validators`
- gate:
  - pass: tracked dirty files are only files intentionally modified by this step

## Phase 0.2 Current Contract Check

- status: pass
- command:
  - `uv run python -c "import nlp_term; print('import-ok')"`
  - `uv run python -m nlp_term.validators --inputs-only --data-dir data --require-realtime`
  - `uv run python -m nlp_term.validators --seed-data --data-dir data`
  - `uv run python -m nlp_term.validators --model-shortlist data/model_shortlist.json`
- result:
  - import check printed `import-ok`
  - all validator commands printed `validation-ok`
- gate:
  - pass: all commands exited 0

## Phase 1.0 Machine-Checked Quality Gates

- status: pass
- changed_files:
  - `src/nlp_term/validators.py`
  - `src/nlp_term/schemas.py`
- command:
  - `uv run python -m nlp_term.validators --help`
  - `uv run python -m compileall src\nlp_term\validators.py src\nlp_term\schemas.py`
  - `uv run ruff check src\nlp_term\validators.py src\nlp_term\schemas.py`
- additional_sanity:
  - `uv run python -m nlp_term.validators --seed-data --data-dir data`
  - `uv run python -m nlp_term.validators --dataset-quality --data-dir data --no-dry-run --require-validated --require-qa-source`
- result:
  - help output includes the planned validator modes
  - compileall exited 0
  - ruff reported `All checks passed!`
  - additional seed/dataset validator sanity checks printed `validation-ok`
  - after critic feedback, classifier metrics validation now requires `split_strategy`, `label_distribution`, and source id or source hash evidence
  - after critic feedback, runtime knowledge consistency now fails unless composer, batch, and UI expose the planned shared knowledge path boundary
- gate:
  - pass: validator CLI now exposes machine-checkable quality modes for later phases

## Phase 1.1 Parser Utilities

- status: pass
- changed_files:
  - `pyproject.toml`
  - `uv.lock`
  - `src/nlp_term/prepare/normalize.py`
  - `src/nlp_term/prepare/parsers.py`
  - `src/nlp_term/prepare/document_parsers.py`
- command:
  - `uv sync`
  - `uv run python -m compileall src\nlp_term\prepare`
  - `uv run ruff check src\nlp_term\prepare`
  - `uv run python -c "from pathlib import Path; from nlp_term.prepare.document_parsers import pdf_to_text; text=pdf_to_text(Path('data/raw/graduation/graduation_curriculum_pdf.pdf')); print(len(text)); raise SystemExit(0 if len(text) >= 1000 else 1)"`
- result:
  - `olefile==0.47` and `pymupdf==1.27.2.3` installed by `uv sync`
  - compileall exited 0
  - ruff reported `All checks passed!`
  - graduation PDF extraction returned 1,497,628 normalized characters
- gate:
  - pass: parser utilities exist for HTML/PDF/HWP/HWPX, and the known graduation PDF extracts more than 1,000 characters
