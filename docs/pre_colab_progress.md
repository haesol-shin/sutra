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

## Phase 1.2 Domain Parser Coverage

- status: pass
- changed_files:
  - `src/nlp_term/prepare/from_sources.py`
  - `src/nlp_term/prepare/build_all.py`
  - `data/knowledge_seed.json`
  - `data/cls_train_seed.json`
  - `data/label_audit_seed.json`
  - `data/qa_seed.json`
  - `data/source_parse_failures.json`
- command:
  - `uv run python -m nlp_term.collect.run_collect --fetch --output data/sources/source_probe.json`
  - `uv run python -m nlp_term.validators --source-probe data/sources/source_probe.json --require-raw-files`
  - `uv run python -m nlp_term.prepare.from_sources --source-probe data/sources/source_probe.json --output data/knowledge_seed.json`
  - `uv run python -m nlp_term.prepare.build_all --output-dir data`
  - `uv run python -m nlp_term.validators --knowledge-provenance data/sources/source_probe.json --data-dir data`
  - `uv run python -m nlp_term.validators --knowledge-quality data/knowledge_seed.json --source-probe data/sources/source_probe.json --min-docs-per-label 3 --min-body-chars 80 --min-source-parse-ratio 0.8`
  - `uv run python -m compileall src\nlp_term\prepare`
  - `uv run ruff check src\nlp_term\prepare`
- failure_notes:
  - first source fetch attempt timed out on the graduation PDF; retry succeeded
  - first knowledge quality attempt produced only 2 dining docs; chunk size was reduced and regeneration passed
- result:
  - source probe/raw file validation printed `validation-ok`
  - generated 17 source-backed knowledge docs
  - label distribution: `{0: 3, 1: 3, 2: 3, 3: 5, 4: 3}`
  - `metadata.generation_method="source_parse"` rows: 17 of 17
  - `data/source_parse_failures.json` contains `[]`
  - provenance and knowledge-quality validators printed `validation-ok`
  - compileall exited 0
  - ruff reported `All checks passed!`
- gate:
  - pass: each label has at least 3 docs, each doc is source-backed, and no parse failures were recorded
