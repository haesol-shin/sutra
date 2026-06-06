# Data Expansion Progress

작성일: 2026-06-07

## Phase 0 + Phase 1.1: Stage 0 Serial Source Loop

- status: pass
- changed_files:
  - `src/nlp_term/collect/source_inventory.py`
  - `src/nlp_term/collect/run_collect.py`
  - `src/nlp_term/prepare/from_sources.py`
  - `src/nlp_term/validators.py`
  - `docs/source_inventory.md`
  - `docs/data_expansion_failure_log.md`
  - `docs/data_expansion_progress.md`
  - regenerated data/model/output artifacts

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
  - `uv run python -m nlp_term.validators --source-probe data/sources/source_probe.json --require-raw-files --source-stage-coverage data/sources/source_probe.json --stage stage0 --min-stage-sources 8 --max-stage-sources 12 --require-stage-labels --require-graduation-departments 2`
- result:
  - all 10 Stage 0 sources returned HTTP 200.
  - raw file checksum validation printed `validation-ok`.
- gate:
  - pass: every active Stage 0 source has a saved raw snapshot and matching checksum.

## Parse And Knowledge Build

- command:
  - `uv run python -m nlp_term.prepare.from_sources --source-probe data/sources/source_probe.json --output data/knowledge_seed.json --failures-output data/source_parse_failures.json --chunks-per-source 9`
  - `uv run python -m nlp_term.validators --knowledge-quality data/knowledge_seed.json --source-probe data/sources/source_probe.json --min-total-docs 50 --min-docs-per-label 1 --min-body-chars 80 --min-source-parse-ratio 0.9`
- result:
  - generated 53 knowledge docs.
  - label distribution: `{0: 27, 1: 6, 2: 9, 3: 3, 4: 8}`
  - `data/source_parse_failures.json`: `[]`
  - knowledge quality validator printed `validation-ok`
- gate:
  - pass: total source-backed docs exceed 50 and every label has accepted chunks.
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
  - `uv run python -m nlp_term.validators --retrieval-metrics model/retrieval_metrics.json --knowledge data/knowledge_seed.json --qa data/qa_seed.json --min-top1-label-accuracy 0.80 --min-top3-source-hit-rate 0.75`
- result:
  - row count: 50
  - top-1 label accuracy: 1.0
  - top-3 source hit rate: 0.78
  - per-label failure counts: `{0: 7, 1: 3, 2: 1, 3: 0, 4: 0}`
  - validator printed `validation-ok`
- gate:
  - pass: retrieval smoke exceeded the Stage 0 thresholds.
- bottleneck:
  - graduation source hit failures are the largest retrieval weakness and should be examined before broad graduation expansion.

## Chatbot Batch Smoke

- command:
  - `bash ./chatbot.sh batch`
  - `uv run python -m nlp_term.validators --chat-quality outputs/chat_output.json --input data/test_chat.json --min-answer-chars 30`
- result:
  - `outputs/chat_output.json` was generated.
  - chat quality validator printed `validation-ok`
- gate:
  - pass: grading batch path produced valid JSON with non-empty answers.

## Final Verification

- command:
  - `uv run python -m compileall src\nlp_term\collect src\nlp_term\prepare\from_sources.py src\nlp_term\validators.py`
  - `uv run ruff check src\nlp_term\collect src\nlp_term\prepare\from_sources.py src\nlp_term\validators.py`
- result:
  - compileall exited 0.
  - ruff reported `All checks passed!`
- gate:
  - pass: modified code compiles and passes lint.
