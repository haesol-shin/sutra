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

## Phase 2.1 Classification Dataset Generation

- status: pass
- changed_files:
  - `src/nlp_term/prepare/cls_data.py`
  - `data/cls_train_seed.json`
  - `data/label_audit_seed.json`
  - `data/qa_seed.json`
- command:
  - `uv run python -m nlp_term.prepare.build_all --output-dir data`
  - `uv run python -m nlp_term.validators --dataset-quality --data-dir data --min-cls-rows 250 --min-cls-per-label 40 --min-ambiguous-per-label 5 --no-dry-run --require-validated`
  - `uv run python -m compileall src\nlp_term\prepare`
  - `uv run ruff check src\nlp_term\prepare`
  - `uv run python -m nlp_term.validators --seed-data --data-dir data`
- result:
  - initial numeric gate passed, but critic found conflicting duplicate questions; generator and validator were strengthened and data was regenerated
  - generated 476 classification rows
  - label distribution: `{0: 91, 1: 88, 2: 94, 3: 115, 4: 88}`
  - sample type distribution includes 25 ambiguous rows
  - ambiguous rows per label: `{0: 5, 1: 5, 2: 5, 3: 5, 4: 5}`
  - unique normalized questions: 476 of 476
  - conflicting normalized question labels: 0
  - dataset-quality and seed-data validators printed `validation-ok`
  - compileall exited 0
  - ruff reported `All checks passed!`
- gate:
  - pass: classification data exceeds row, per-label, ambiguity, no-dry-run, and validation thresholds

## Phase 2.2 QA Dataset Generation

- status: pass
- changed_files:
  - `src/nlp_term/prepare/parsers.py`
  - `src/nlp_term/prepare/from_sources.py`
  - `src/nlp_term/prepare/qa_data.py`
  - `src/nlp_term/validators.py`
  - `data/knowledge_seed.json`
  - `data/qa_seed.json`
  - `data/cls_train_seed.json`
  - `data/label_audit_seed.json`
  - `data/source_parse_failures.json`
- command:
  - `uv run python -m nlp_term.prepare.from_sources --source-probe data\sources\source_probe.json --output data\knowledge_seed.json --failures-output data\source_parse_failures.json`
  - `uv run python -m nlp_term.validators --knowledge-quality data\knowledge_seed.json --source-probe data\sources\source_probe.json --min-docs-per-label 3 --min-body-chars 80 --min-source-parse-ratio 0.8`
  - `uv run python -m nlp_term.prepare.build_all --output-dir data`
  - `uv run python -m nlp_term.validators --dataset-quality --data-dir data --min-qa-rows 50 --min-qa-per-label 8 --require-qa-source --require-validated --no-dry-run`
  - `uv run python -m nlp_term.validators --seed-data --data-dir data`
  - `uv run python -m compileall src\nlp_term\prepare src\nlp_term\validators.py`
  - `uv run ruff check src\nlp_term\prepare src\nlp_term\validators.py`
- result:
  - initial QA-only fixes passed scripted gates but failed critic review; meeting protocol opened a 5-agent meeting instead of stopping
  - first meeting selected positive evidence span selection plus hard validator gates
  - second meeting cycle found the blocker was upstream HTML extraction, so CNU HTML parsing now uses source-specific main-content selectors before chunking
  - generated 15 source-backed knowledge docs, 3 per label
  - generated 50 QA rows, 10 per label
  - generated 512 classification rows after source regeneration
  - `data/source_parse_failures.json` records `cnucoop_discovery` as excluded because no clean chunk passed quality gates; dining remains covered by 3 `cnu_mobile_food` docs
  - independent page-chrome scan reported 0 hits in `knowledge_seed.json` and `qa_seed.json`
  - Source/Data critic reviewed all 50 QA rows and returned `PASS`
  - knowledge-quality, dataset-quality, and seed-data validators printed `validation-ok`
  - compileall exited 0
  - ruff reported `All checks passed!`
- gate:
  - pass: QA data meets row, per-label, source grounding, no-dry-run, validation, page-chrome, and all-row Source/Data critic gates

## Phase 3.1 Source-Disjoint Classifier Evaluation

- status: pass
- changed_files:
  - `src/nlp_term/prepare/cls_data.py`
  - `src/nlp_term/classify/train.py`
  - `data/cls_train_seed.json`
  - `data/label_audit_seed.json`
  - `data/qa_seed.json`
  - `model/classifier.joblib`
  - `model/classifier_metrics.json`
- command:
  - `uv run python -m compileall src\nlp_term\prepare\cls_data.py src\nlp_term\classify\train.py`
  - `uv run ruff check src\nlp_term\prepare\cls_data.py src\nlp_term\classify\train.py`
  - `uv run python -m nlp_term.prepare.build_all --output-dir data`
  - `uv run python -m nlp_term.validators --dataset-quality --data-dir data --min-cls-rows 250 --min-cls-per-label 40 --min-ambiguous-per-label 5 --no-dry-run --require-validated --min-qa-rows 50 --min-qa-per-label 8 --require-qa-source`
  - `uv run python -m nlp_term.classify.train --input data/cls_train_seed.json --model-output model/classifier.joblib --metrics-output model/classifier_metrics.json`
  - `uv run python -m nlp_term.validators --classifier-metrics model/classifier_metrics.json --input data/cls_train_seed.json --require-source-disjoint --min-macro-f1 0.70 --min-weighted-f1 0.70 --min-class-f1 0.55`
- result:
  - classification generation now adds source phrase questions so each label has at least two source docs represented in `cls_train_seed.json`
  - generated 657 classification rows
  - label distribution: `{0: 148, 1: 131, 2: 112, 3: 112, 4: 154}`
  - source-disjoint split used 618 train rows and 39 eval rows
  - eval sources: `academic_calendar_chunk_2`, `academic_notice_board_chunk_3`, `cnu_mobile_food_chunk_2`, `graduation_curriculum_pdf_chunk_3`, `shuttle_bus_chunk_2`
  - `source_overlap_count=0`
  - `input_checksum` in `model/classifier_metrics.json` matches `data/cls_train_seed.json`
  - macro F1: `1.0`
  - weighted F1: `1.0`
  - class F1: `{0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}`
- interpretation:
  - this is a source-disjoint generated-data sanity baseline, not final held-out real-user performance
  - the score is high because the current generated seed contains strong label cues; later Task 1 performance work should add harder human-like questions before making any final performance claim
- gate:
  - pass: classifier metrics are source-disjoint, checksum-bound, cover all labels, and exceed the advisory F1 thresholds

## Phase 3.2 Grading Entrypoint Check

- status: pass
- changed_files:
  - `src/classifier.ipynb`
  - `docs/pre_colab_progress.md`
- command:
  - `uv run jupyter nbconvert --execute src/classifier.ipynb --to notebook --inplace`
  - `uv run python -m nlp_term.validators --check-all --data-dir data --outputs-dir outputs`
- result:
  - notebook execution completed and wrote `outputs/cls_output.json`
  - Windows emitted a ZMQ selector-thread runtime warning during nbconvert, but the command exited 0
  - `data/test_cls.json` rows: 2
  - `outputs/cls_output.json` rows: 2
  - output labels: `[0, 3]`
- gate:
  - pass: classifier grading entrypoint produces valid output rows with labels in 0-4

## Phase 4.0 Shared Knowledge Runtime

- status: pass
- changed_files:
  - `src/nlp_term/retrieve/knowledge.py`
  - `src/nlp_term/retrieve/rank.py`
  - `src/nlp_term/chat/composer.py`
  - `src/nlp_term/chat/batch.py`
  - `src/nlp_term/ui/app.py`
  - `src/nlp_term/validators.py`
  - `docs/pre_colab_progress.md`
- command:
  - `uv run python -m compileall src\nlp_term\retrieve src\nlp_term\chat src\nlp_term\ui src\nlp_term\validators.py`
  - `uv run ruff check src\nlp_term\retrieve src\nlp_term\chat src\nlp_term\ui src\nlp_term\validators.py`
  - `uv run python -m nlp_term.validators --runtime-knowledge-consistency --knowledge data/knowledge_seed.json`
  - `uv run python -m nlp_term.chat.batch --input data/test_chat.json --output outputs/chat_output.json --knowledge data/knowledge_seed.json`
  - `uv run python -m nlp_term.ui.app --host 127.0.0.1 --port 7860 --knowledge data/knowledge_seed.json --smoke-test`
- result:
  - added `nlp_term.retrieve.knowledge` as the shared runtime loader for generated knowledge docs
  - `rank_docs`, batch composer, and UI answers now use the same loaded `KnowledgeDoc` list
  - batch and UI expose a `--knowledge` path with `data/knowledge_seed.json` as the local default
  - runtime consistency validator rejects hardcoded fallback use when the generated knowledge artifact exists
  - critic requested one code fix: explicit `docs=[]` should not fall back to default knowledge in `rank_docs`
  - fix applied: `rank_docs` now falls back only when `docs is None`
  - compileall exited 0
  - ruff reported `All checks passed!`
  - runtime consistency validator printed `validation-ok`
  - batch command wrote `outputs/chat_output.json`
  - UI smoke printed `ui-smoke-ok`
- gate:
  - pass: retrieval, batch, and UI now share the same knowledge-loading boundary
