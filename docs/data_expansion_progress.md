# Data Expansion Progress

작성일: 2026-06-07

## Phase 0 + Phase 1.1: Stage 0 Serial Source Loop

- status: pass
- changed_files:
  - `src/nlp_term/collect/source_inventory.py`
  - `src/nlp_term/collect/run_collect.py`
  - `src/nlp_term/prepare/from_sources.py`
  - `src/nlp_term/retrieve/rank.py`
  - `src/nlp_term/retrieve/evaluate.py`
  - `src/nlp_term/chat/composer.py`
  - `src/nlp_term/validators.py`
  - `docs/source_inventory.md`
  - `docs/evidence/stage0-review-repair-2026-06-07.json`
  - `docs/data_expansion_failure_log.md`
  - `docs/data_expansion_progress.md`
  - regenerated tracked data artifacts
- local_ignored_evidence:
  - `data/sources/source_probe.json`
  - `model/retrieval_metrics.json`
  - `outputs/chat_output.json`
- durable_evidence_manifest:
  - `docs/evidence/stage0-review-repair-2026-06-07.json`

## Source Coverage

- command:
  - `uv run python -m nlp_term.collect.run_collect --output data/sources/source_probe_stage0_stub.json`
  - `uv run python -m nlp_term.validators --source-probe data/sources/source_probe_stage0_stub.json --source-stage-coverage data/sources/source_probe_stage0_stub.json --stage stage0 --min-stage-sources 8 --max-stage-sources 12 --require-stage-labels --require-graduation-departments 2`
- result:
  - Stage 0 stub probe rows: 10
  - label distribution: `{0: 3, 1: 4, 2: 1, 3: 1, 4: 1}`
  - source-stage coverage validator printed `validation-ok`
- gate:
  - pass: Stage 0 has 8-12 active sources, covers labels 0-4, and includes two graduation departments plus the central curriculum PDF.

## Raw Fetch

- command:
  - `uv run python -m nlp_term.collect.run_collect --fetch --output data/sources/source_probe.json`
  - `uv run python -m nlp_term.validators --source-probe data/sources/source_probe.json --require-raw-files --require-official-chain-evidence`
  - `uv run python -m nlp_term.validators --source-stage-coverage data/sources/source_probe.json --stage stage0 --min-stage-sources 8 --max-stage-sources 12 --require-stage-labels --require-graduation-departments 2`
- result:
  - 10 Stage 0 sources are represented in the local source probe.
  - `graduation_curriculum_pdf` reused an existing raw snapshot after a `ReadTimeout`; this is recorded in verification warnings.
  - `cnu_mobile_food` is marked `official_chain_ok=false` until explicit official-chain verification is added.
  - raw file checksum validation printed `validation-ok`.
- gate:
  - pass: every active Stage 0 source has a saved raw snapshot and matching checksum.

## Parse And Knowledge Build

- command:
  - `uv run python -m nlp_term.prepare.from_sources --source-probe data/sources/source_probe.json --output data/knowledge_seed.json --failures-output data/source_parse_failures.json --chunks-per-source 9`
  - `uv run python -m nlp_term.validators --knowledge-provenance data/sources/source_probe.json --data-dir data --require-raw-provenance`
  - `uv run python -m nlp_term.validators --knowledge-quality data/knowledge_seed.json --source-probe data/sources/source_probe.json --min-total-docs 50 --min-docs-per-label 1 --min-body-chars 80 --min-source-parse-ratio 0.9`
- result:
  - generated 53 knowledge docs.
  - label distribution: `{0: 27, 1: 6, 2: 9, 3: 3, 4: 8}`
  - `data/source_parse_failures.json`: `[]`
  - knowledge quality validator printed `validation-ok`
- gate:
  - pass: total source-backed docs exceed 50, every label has accepted chunks, and every knowledge row carries raw checksum/probe provenance metadata.
- bottleneck:
  - dining produced only 3 clean chunks, so freshness-specific parsing remains a likely next bottleneck.

## Dataset Build

- command:
  - `uv run python -m nlp_term.prepare.build_all --output-dir data`
  - `uv run python -m nlp_term.validators --seed-data --data-dir data`
  - `uv run python -m nlp_term.validators --dataset-quality --data-dir data --min-cls-rows 700 --min-cls-per-label 40 --min-qa-rows 50 --min-qa-per-label 8 --require-qa-source --require-validated --no-dry-run`
- result:
  - generated 1,346 classification rows.
  - classification label distribution: `{0: 736, 1: 151, 2: 154, 3: 112, 4: 193}`
  - generated 50 QA rows.
  - QA label distribution: `{0: 10, 1: 10, 2: 10, 3: 10, 4: 10}`
  - validators printed `validation-ok`
- gate:
  - pass: Stage 0 source-backed dataset gates passed.

## Retrieval Smoke

- command:
  - `uv run python -m nlp_term.retrieve.evaluate --knowledge data/knowledge_seed.json --qa data/qa_seed.json --output model/retrieval_metrics.json`
  - `uv run python -m nlp_term.validators --retrieval-metrics model/retrieval_metrics.json --knowledge data/knowledge_seed.json --qa data/qa_seed.json --require-metadata-aware --min-top1-label-accuracy 0.80 --min-top3-source-hit-rate 0.75`
- result:
  - row count: 50
  - top-1 label accuracy: 1.0
  - top-3 source hit rate: 0.78
  - per-label failure counts: `{0: 9, 1: 0, 2: 2, 3: 0, 4: 0}`
  - retrieval strategy: `lexical_metadata_label_hint`
  - validator printed `validation-ok`
- gate:
  - pass: retrieval smoke exceeded the Stage 0 thresholds.
- bottleneck:
  - graduation source hit failures are the largest retrieval weakness and should be examined before broad graduation expansion.

## Chatbot Batch Smoke

- command:
  - `uv run python -m nlp_term.chat.batch --input data/test_chat.json --output outputs/chat_output.json --knowledge data/knowledge_seed.json --backend deterministic`
  - `uv run python -m nlp_term.validators --chat-quality outputs/chat_output.json --input data/test_chat.json --knowledge data/knowledge_seed.json --min-answer-chars 30 --require-source-hint --require-evidence-alignment`
- result:
  - `outputs/chat_output.json` was generated.
  - chat quality validator printed `validation-ok`
- gate:
  - pass: batch module produced valid JSON with source hints and quoted evidence aligned to the ranked knowledge source.
- known_runtime_gap:
  - `bash ./chatbot.sh batch` timed out under the local PowerShell/bash bridge when `NLP_TERM_CHAT_BACKEND=auto`; backend/script reliability remains a separate backend decision task.

## Final Verification

- command:
  - `uv run python -m compileall src\nlp_term\collect src\nlp_term\prepare\from_sources.py src\nlp_term\retrieve src\nlp_term\chat src\nlp_term\validators.py`
  - `uv run ruff check src\nlp_term\collect src\nlp_term\prepare\from_sources.py src\nlp_term\retrieve src\nlp_term\chat src\nlp_term\validators.py`
- result:
  - compileall exited 0.
  - ruff reported `All checks passed!`
- gate:
  - pass: modified code compiles and passes lint.

## 2026-06-08 Work Unit A: Source Freeze And Fetch Audit

- status: pass
- rationale:
  - Data expansion is now prioritized before Qwen prompt tuning, embedding retrieval, reranking, or exact-calendar harness hardening.
  - Critic review rejected the earlier broad plan because Stage 0 already has 10 active sources.
  - The revised Work Unit A freezes Stage 0 first and audits source reliability before promoting more sources.
- artifacts:
  - `docs/evidence/source-fetch-audit-2026-06-08.json`
  - `docs/source_fetch_audit_2026_06_08.md`
  - `docs/superpowers/plans/2026-06-08-source-data-expansion-first.md`
- command:
  - `uv run python -X utf8 -m nlp_term.collect.run_collect --fetch --stage stage0 --output data/sources/source_probe.json`
  - `uv run python -X utf8 -m nlp_term.collect.source_audit --source-probe data/sources/source_probe.json --output docs/evidence/source-fetch-audit-2026-06-08.json --markdown docs/source_fetch_audit_2026_06_08.md`
  - `uv run python -m nlp_term.validators --source-probe data/sources/source_probe.json --require-raw-files`
  - `uv run python -m nlp_term.validators --source-stage-coverage data/sources/source_probe.json --stage stage0 --min-stage-sources 8 --max-stage-sources 12 --require-stage-labels --require-graduation-departments 2`
  - `uv run pytest tests/test_source_audit.py -q`
- result:
  - baseline knowledge docs: 53
  - Stage 0 active sources: 10
  - audit rows: 21
  - decisions: 10 `retain`, 11 `defer`
  - official status: 9 `verified`, 1 `official_linked`, 11 `unverified`
  - `cnu_mobile_food` is `official_linked` because CNU `plus.cnu.ac.kr/html/kr/sub05/sub05_050401.html` links to `mobileadmin.cnu.ac.kr/food/index.jsp`.
  - several Stage 0 fetch attempts reused cached raw snapshots because of `ReadTimeout` or `ConnectionError`; the audit preserves those warnings instead of hiding them.
- gate:
  - pass: Stage 0 remained frozen at 10 active sources.
  - pass: every active Stage 0 source has a raw snapshot and checksum.
  - pass: inactive candidates stayed deferred.
  - pass: the next implementation unit can parse existing active sources before any promotion.
- next:
  - Work Unit B: structured parsers for already-active dining, academic calendar, and shuttle sources using saved raw snapshots.
