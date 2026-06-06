# Pre-Colab Goal Mode Execution Plan

작성일: 2026-06-06

이 문서는 Colab 실행 전까지의 목표 모드 작업을 작은 단계로 고정한다. 실행 순서는 항상 `Plan -> Architecture -> Evaluation`이며, 한 번에 하나의 단계만 구현한다.

## 0. Global Rules

- `src/classifier.ipynb`와 `chatbot.sh`는 평가 진입점으로 보존한다.
- Task 1/2를 Task 3보다 먼저 완료한다.
- Colab/T4, torch 2.5.1 실측, Qwen 로딩 실험은 이 계획의 바깥이다.
- 외부 LLM API, MCP, full tool-call agent는 최종 inference path에 넣지 않는다.
- seed data는 pipeline sanity 전용이며 최종 성능 주장에 사용하지 않는다.
- 각 step의 `max_attempts`는 3이다.
- 실패 시 `docs/pre_colab_failure_log.md`에 기록하고 같은 step을 재시도한다.
- `REQUEST CHANGES`가 나오거나 같은 step이 2회 실패하면 `docs/meeting_protocol.md`의 5-agent meeting을 연다.
- 3회 실패한 step은 바로 중단하지 않고 5-agent meeting의 handoff 또는 user escalation 결과에 따른다.
- 각 구현 step 뒤에는 critic 1회를 실행한다.
- 사용자가 완료 명령을 내리면 runtime critic, data/source critic, submission critic 3개를 순차 실행한다.

## 1. Sequential Review Loop

각 phase 시작 전 최대 3회까지 아래 순서를 따른다.

1. Plan: 이번 phase의 step, artifact, command, threshold를 확정한다.
2. Architecture: 파일 경계, 기존 entrypoint 보존, overengineering 여부를 검토한다.
3. Evaluation: 정량 gate, anti-gaming check, failure logging completeness를 검토한다.

pass 조건:
- Architecture verdict가 `PASS`.
- Evaluation verdict가 `PASS`.
- 둘 중 하나라도 reject하면 plan을 수정하고 다음 loop로 간다.

## 2. Phase 0: Baseline Inventory

### Step 0.1 Current State Snapshot

- work: 현재 repo 상태와 ignored/generated artifact를 기록한다.
- command:
  - `git status --short --ignored`
  - `git log --oneline -3`
- quantitative_gate:
  - tracked dirty files are only files intentionally modified by this step.
  - ignored generated dirs may include `.venv/`, `data/raw/`, `data/sources/`, `model/`, `outputs/`.
- artifact:
  - `docs/pre_colab_progress.md`
- critic: scope is pre-Colab only.

### Step 0.2 Current Contract Check

- work: 현재 entrypoint와 validators가 baseline에서 통과하는지 확인한다.
- command:
  - `uv run python -c "import nlp_term; print('import-ok')"`
  - `uv run python -m nlp_term.validators --inputs-only --data-dir data --require-realtime`
  - `uv run python -m nlp_term.validators --seed-data --data-dir data`
  - `uv run python -m nlp_term.validators --model-shortlist data/model_shortlist.json`
- quantitative_gate:
  - all commands exit 0.
- artifact:
  - `docs/pre_colab_progress.md`
- critic: fixed evaluator paths remain intact.

## 3. Phase 1: Source Parsers And Knowledge Docs

### Step 1.0 Machine-Checked Quality Gates

- work: implement validator flags that enforce the quantitative gates used later in this plan.
- files:
  - update `src/nlp_term/validators.py`
- boundary:
  - planned thresholds must be checked by commands, not by manual inspection.
  - validators must fail nonzero and print the failed threshold name.
  - validators must not silently skip missing artifacts unless the step explicitly marks the artifact optional.
- command:
  - `uv run python -m nlp_term.validators --help`
  - `uv run python -m compileall src\nlp_term\validators.py`
  - `uv run ruff check src\nlp_term\validators.py`
- quantitative_gate:
  - help output includes `--knowledge-quality`, `--dataset-quality`, `--classifier-metrics`, `--retrieval-metrics`, `--chat-quality`, and `--runtime-knowledge-consistency`.
  - validators expose thresholds for minimum rows, per-label counts, body length, source-parse ratio, dry-run exclusion, validation status, ambiguous rows, QA source evidence, answer length, source hints, source-disjoint metrics, and retrieval hit rates.
  - metric validators bind reported metrics back to original artifacts through input paths and/or checksums.
- artifact:
  - validator CLI contract.
- critic: no later quantitative gate relies only on prose.

### Step 1.1 Parser Utilities

- work: add parser utility functions for HTML/PDF/HWP/HWPX text extraction, whitespace normalization, title/body clipping, and source-backed doc creation.
- files:
  - create `src/nlp_term/prepare/normalize.py`
  - create `src/nlp_term/prepare/parsers.py`
  - create `src/nlp_term/prepare/document_parsers.py`
  - update `pyproject.toml`
- dependency_boundary:
  - add `pymupdf` for PDF text extraction.
  - add `olefile` for legacy `.hwp` OLE container reads.
  - use Python stdlib `zipfile`/XML parsing for `.hwpx`.
  - do not add OCR or external document conversion tools before Colab.
- command:
  - `uv run python -m compileall src\nlp_term\prepare`
  - `uv run ruff check src\nlp_term\prepare`
- quantitative_gate:
  - commands exit 0.
  - no parser returns empty body for non-empty raw HTML.
  - PDF parser extracts at least 1,000 normalized characters from `graduation_curriculum_pdf`.
  - HWP/HWPX parser has deterministic unit fixtures or sample raw files before any HWP/HWPX source is counted.
- artifact:
  - parser modules.
- critic: parser does not hardcode final answer text.

### Step 1.2 Domain Parser Coverage

- work: parse fetched raw snapshots into source-backed `KnowledgeDoc` rows.
- files:
  - create `src/nlp_term/prepare/from_sources.py`
  - update `src/nlp_term/prepare/build_all.py`
  - update `src/nlp_term/schemas.py`
- boundary:
  - `from_sources.py` reads `data/sources/source_probe.json`.
  - for each `raw_file`, it loads the saved raw snapshot and dispatches by `content_type` and file suffix.
  - HTML/text sources use `parsers.py`.
  - PDF/HWP/HWPX sources use `document_parsers.py`.
  - unsupported document formats are recorded as parse failures and are not silently converted to hardcoded seed rows.
  - `build_all.py` consumes parsed knowledge docs when present, then builds classification and QA rows from that source-backed knowledge.
  - hardcoded seed rows are allowed only as fallback sanity examples and must not be counted toward source-backed gates.
  - source parsing provenance is stored as `KnowledgeDoc.metadata.generation_method`.
- command:
  - `uv run python -m nlp_term.collect.run_collect --fetch --output data/sources/source_probe.json`
  - `uv run python -m nlp_term.validators --source-probe data/sources/source_probe.json --require-raw-files`
  - `uv run python -m nlp_term.prepare.from_sources --source-probe data/sources/source_probe.json --output data/knowledge_seed.json`
  - `uv run python -m nlp_term.prepare.build_all --output-dir data`
  - `uv run python -m nlp_term.validators --knowledge-provenance data/sources/source_probe.json --data-dir data`
  - `uv run python -m nlp_term.validators --knowledge-quality data/knowledge_seed.json --source-probe data/sources/source_probe.json --min-docs-per-label 3 --min-body-chars 80 --min-source-parse-ratio 0.8`
- quantitative_gate:
  - source probe exits 0.
  - each label 0-4 has at least 3 `KnowledgeDoc` rows.
  - each `KnowledgeDoc.body` length is at least 80 characters.
  - each `KnowledgeDoc.source_id` exists in `source_probe`.
  - at least 80% of `KnowledgeDoc` rows have `metadata.generation_method="source_parse"`.
  - `graduation_curriculum_pdf` contributes at least one source-parsed `KnowledgeDoc`.
  - if any `.hwp` or `.hwpx` source is present in `source_probe`, it must either produce at least one source-parsed `KnowledgeDoc` or be listed in a parse-failure report.
- artifact:
  - `data/knowledge_seed.json`
  - `data/source_parse_failures.json`
- critic: no final-facing factual claim is based only on `official_chain_ok=false`.

## 4. Phase 2: Source-Backed Classification And QA Data

### Step 2.1 Classification Dataset Generation

- work: generate accepted classification rows from source-backed docs using templates and ambiguity sets.
- command:
  - `uv run python -m nlp_term.prepare.build_all --output-dir data`
  - `uv run python -m nlp_term.validators --seed-data --data-dir data`
  - `uv run python -m nlp_term.validators --dataset-quality --data-dir data --min-cls-rows 250 --min-cls-per-label 40 --min-ambiguous-per-label 5 --no-dry-run --require-validated`
- quantitative_gate:
  - at least 250 accepted classification rows.
  - at least 40 rows per label.
  - zero rows with `generation_method="dry_run"`.
  - zero rows with `validated=false`.
  - at least 5 ambiguous/adversarial rows per label.
- artifact:
  - `data/cls_train_seed.json`
  - `data/label_audit_seed.json`
- critic: seed-only/keyword-like questions are not enough to pass.

### Step 2.2 QA Dataset Generation

- work: generate source-grounded QA rows.
- command:
  - `uv run python -m nlp_term.prepare.build_all --output-dir data`
  - `uv run python -m nlp_term.validators --seed-data --data-dir data`
  - `uv run python -m nlp_term.validators --dataset-quality --data-dir data --min-qa-rows 50 --min-qa-per-label 8 --require-qa-source`
- quantitative_gate:
  - at least 50 QA rows total.
  - at least 8 QA rows per label.
  - every answer includes a source URL or source title.
  - no answer contains banned placeholder terms from `BANNED_OUTPUT_TERMS`.
- artifact:
  - `data/qa_seed.json`
- critic: answers are useful and not just category disclaimers.

## 5. Phase 3: Task 1 Classifier Performance

### Step 3.1 Source-Disjoint Evaluation

- work: update training/evaluation so metrics are not random seed-only split.
- command:
  - `uv run python -m nlp_term.classify.train --input data/cls_train_seed.json --model-output model/classifier.joblib --metrics-output model/classifier_metrics.json`
  - `uv run python -m nlp_term.validators --classifier-metrics model/classifier_metrics.json --input data/cls_train_seed.json --require-source-disjoint --min-macro-f1 0.70 --min-weighted-f1 0.70 --min-class-f1 0.55`
- quantitative_gate:
  - metrics include `evaluation_scope="source_disjoint"`.
  - metrics include `split_strategy`.
  - metrics include train/eval source id lists or hashes.
  - metrics include `source_overlap_count=0`.
  - metrics include `input_checksum`, and validator recomputes it from `data/cls_train_seed.json`.
  - metrics include label distribution and per-class F1.
  - macro F1 >= 0.70.
  - weighted F1 >= 0.70.
  - no class F1 below 0.55.
- artifact:
  - `model/classifier.joblib`
  - `model/classifier_metrics.json`
- critic: test fixtures were not used for training or threshold tuning.

### Step 3.2 Grading Entrypoint Check

- work: prove classifier entrypoint still produces valid outputs.
- command:
  - `uv run jupyter nbconvert --execute src/classifier.ipynb --to notebook --inplace`
  - `uv run python -m nlp_term.validators --check-all --data-dir data --outputs-dir outputs`
- quantitative_gate:
  - `outputs/cls_output.json` row count equals `data/test_cls.json` row count.
  - all labels are integers in 0-4.
- artifact:
  - `outputs/cls_output.json`
- critic: entrypoint still works without hidden external services.

## 6. Phase 4: Task 2 Retrieval And Deterministic Composer

### Step 4.0 Shared Knowledge Runtime

- work: make retrieval evaluation, batch answers, and UI answers load the same generated knowledge artifact.
- files:
  - create `src/nlp_term/retrieve/knowledge.py`
  - update `src/nlp_term/chat/composer.py`
  - update `src/nlp_term/ui/app.py` if needed
- boundary:
  - `retrieve/knowledge.py` is the only runtime loader for `data/knowledge_seed.json`.
  - batch/UI/evaluation may pass a path, but they must call the same loader and ranking path.
  - hardcoded seed docs are allowed only when the generated artifact is missing, and that fallback must be visible in validation output.
- command:
  - `uv run python -m nlp_term.validators --runtime-knowledge-consistency --knowledge data/knowledge_seed.json`
  - `uv run python -m compileall src\nlp_term\retrieve src\nlp_term\chat src\nlp_term\ui`
  - `uv run ruff check src\nlp_term\retrieve src\nlp_term\chat src\nlp_term\ui`
- quantitative_gate:
  - runtime consistency validator reports the same document count and checksum for retrieval evaluation, batch composer, and UI composer.
  - fallback-to-hardcoded count is zero when `data/knowledge_seed.json` exists.
- artifact:
  - shared runtime knowledge loader.
- critic: evaluator cannot pass on a different knowledge corpus than batch/UI.

### Step 4.1 Retrieval Evaluation

- work: evaluate retrieval over generated knowledge docs and QA rows.
- files:
  - create `src/nlp_term/retrieve/evaluate.py`
- boundary:
  - `evaluate.py` loads `data/knowledge_seed.json` and `data/qa_seed.json`.
  - it uses the same ranking function as batch/UI answers.
  - it writes deterministic metrics only; it does not call external APIs, vector DBs, or inference-time LLMs.
- command:
  - `uv run python -m nlp_term.retrieve.evaluate --knowledge data/knowledge_seed.json --qa data/qa_seed.json --output model/retrieval_metrics.json`
  - `uv run python -m nlp_term.validators --retrieval-metrics model/retrieval_metrics.json --knowledge data/knowledge_seed.json --qa data/qa_seed.json --min-top1-label-accuracy 0.80 --min-top3-source-hit-rate 0.70`
- quantitative_gate:
  - top-1 label accuracy >= 0.80.
  - top-3 source hit rate >= 0.70.
  - metrics include per-label failure counts.
  - metrics include `knowledge_checksum` and `qa_checksum`, and validator recomputes both.
- artifact:
  - `model/retrieval_metrics.json`
- critic: retrieval works without vector DB or external API.

### Step 4.2 Chat Batch Quality Gate

- work: produce Task 2 batch answers from the same path as UI.
- command:
  - `bash chatbot.sh batch`
  - `uv run python -m nlp_term.validators --check-all --data-dir data --outputs-dir outputs`
  - `uv run python -m nlp_term.validators --chat-quality outputs/chat_output.json --input data/test_chat.json --min-answer-chars 80 --require-source-hint`
- quantitative_gate:
  - row count equals `data/test_chat.json`.
  - every `model` length >= 80 characters.
  - every answer contains source hint text.
  - no banned placeholder term.
- artifact:
  - `outputs/chat_output.json`
- critic: answer is source-grounded and not a fake latest/current claim.

### Step 4.3 UI Smoke

- work: prove UI still launches through Gradio path.
- command:
  - `uv run python -m nlp_term.ui.app --host 127.0.0.1 --port 7860 --smoke-test`
- quantitative_gate:
  - command prints `ui-smoke-ok`.
- artifact:
  - none.
- critic: UI path and batch path share answer logic.

## 7. Phase 5: Optional Task 3 Minimal Local Realtime

### Step 5.1 Realtime Scope Gate

- work: select only verified local realtime domains.
- command:
  - `uv run python -m nlp_term.validators --source-probe data/sources/source_probe.json --require-raw-files`
  - `uv run python -m nlp_term.validators --knowledge-provenance data/sources/source_probe.json --data-dir data`
- quantitative_gate:
  - at least one source-backed domain can answer with cached fallback.
  - no source with `official_chain_ok=false` is used for definitive latest/current claim.
- artifact:
  - `docs/model_decisions.md`
- critic: optional Task 3 does not block Task 1/2.

### Step 5.2 Realtime Output Gate

- work: generate optional realtime outputs honestly.
- command:
  - `bash chatbot.sh realtime`
  - `uv run python -m nlp_term.validators --check-all --data-dir data --outputs-dir outputs --require-realtime --final-readiness`
- quantitative_gate:
  - row count equals `data/test_realtime.json`.
  - no banned placeholder term.
  - no unverified "latest/current" claim.
- artifact:
  - `outputs/realtime_output.json`
- critic: fallback wording is honest.

## 8. Phase 6: Final Local Pre-Colab Readiness

### Step 6.1 Full Local Suite

- work: run all deterministic local checks.
- command:
  - `uv run python -c "import nlp_term; print('import-ok')"`
  - `uv run python -m nlp_term.collect.run_collect --fetch --output data/sources/source_probe.json`
  - `uv run python -m nlp_term.validators --source-probe data/sources/source_probe.json --require-raw-files`
  - `uv run python -m nlp_term.prepare.from_sources --source-probe data/sources/source_probe.json --output data/knowledge_seed.json`
  - `uv run python -m nlp_term.validators --knowledge-provenance data/sources/source_probe.json --data-dir data`
  - `uv run python -m nlp_term.validators --knowledge-quality data/knowledge_seed.json --source-probe data/sources/source_probe.json --min-docs-per-label 3 --min-body-chars 80 --min-source-parse-ratio 0.8`
  - `uv run python -m nlp_term.prepare.build_all --output-dir data`
  - `uv run python -m nlp_term.validators --seed-data --data-dir data`
  - `uv run python -m nlp_term.validators --dataset-quality --data-dir data --min-cls-rows 250 --min-cls-per-label 40 --min-ambiguous-per-label 5 --min-qa-rows 50 --min-qa-per-label 8 --no-dry-run --require-validated --require-qa-source`
  - `uv run python -m nlp_term.classify.train --input data/cls_train_seed.json --model-output model/classifier.joblib --metrics-output model/classifier_metrics.json`
  - `uv run python -m nlp_term.validators --classifier-metrics model/classifier_metrics.json --input data/cls_train_seed.json --require-source-disjoint --min-macro-f1 0.70 --min-weighted-f1 0.70 --min-class-f1 0.55`
  - `uv run python -m nlp_term.validators --runtime-knowledge-consistency --knowledge data/knowledge_seed.json`
  - `uv run python -m nlp_term.retrieve.evaluate --knowledge data/knowledge_seed.json --qa data/qa_seed.json --output model/retrieval_metrics.json`
  - `uv run python -m nlp_term.validators --retrieval-metrics model/retrieval_metrics.json --knowledge data/knowledge_seed.json --qa data/qa_seed.json --min-top1-label-accuracy 0.80 --min-top3-source-hit-rate 0.70`
  - `uv run jupyter nbconvert --execute src/classifier.ipynb --to notebook --inplace`
  - `bash chatbot.sh batch`
  - `uv run python -m nlp_term.validators --chat-quality outputs/chat_output.json --input data/test_chat.json --min-answer-chars 80 --require-source-hint`
  - `bash chatbot.sh realtime`
  - `uv run python -m nlp_term.ui.app --smoke-test`
  - `uv run python -m nlp_term.validators --check-all --data-dir data --outputs-dir outputs --require-realtime --final-readiness`
  - `uv run ruff check src\nlp_term pyproject.toml src\classifier.ipynb`
  - `uv run python -m compileall src\nlp_term`
- quantitative_gate:
  - all commands exit 0.
  - no unresolved blocker in `docs/pre_colab_failure_log.md`.
- artifact:
  - `model/classifier.joblib`
  - `model/classifier_metrics.json`
  - `outputs/*.json`
- critic: one runtime critic, then data/source critic, then submission-readiness critic if user asks completion.

## 9. Explicit Non-Goals Before Colab

- Do not run T4/Colab validation.
- Do not claim Qwen3.5-9B is usable on T4 until measured.
- Do not add vector DB or full RAG framework.
- Do not add tool-calling agent.
- Do not use external LLM API in final inference path.
