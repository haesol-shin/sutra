# Data Inventory Report

> Generated: 2026-06-09
> Purpose: Pre-cleanup discovery for migrating CNU Campus ChatBot data into `examples/cnu-campus/`.

## Summary

The `data/` folder is a mixed bag of source, processed, evaluation, and diagnostic files with inconsistent naming. There are 5 distinct categories of content:

1. **Raw source snapshots** (`data/raw/`, `data/sources/`) — fetched HTML/PDF/text from CNU websites. These are CNU-specific.
2. **Processed RAG index** (`data/knowledge_seed.json`) — the main 2414-document knowledge corpus consumed by the chatbot. This is the single most important data artifact.
3. **Training/evaluation seeds** (`data/cls_train_seed.json`, `data/qa_seed.json`, `data/label_audit_seed.json`) — synthetic data used to train/evaluate the Task 1 classifier.
4. **Task 1/2 gold evaluation files** (`data/gold/`) — human-labeled evaluation sets and probe questions.
5. **Runtime artifacts** (`data/harness_safety_questions.json`, `data/collection_failures.json`, `data/source_parse_failures.json`, `data/model_shortlist.json`, `data/test_*.json`) — diagnostic logs, configuration references, and stub test data.

The existing `examples/cnu-campus/data/index.jsonl` is a 3-row stub — it was never populated with real data. The real processed RAG corpus is still in `data/knowledge_seed.json` and not yet mirrored into the Sutra workspace.

**Total: ~71 MB across ~180 files.**

---

## Directory Map

```
nlp-term/
├── data/
│   ├── cls_train_seed.json          (530 KB, 1346 items)
│   ├── collection_failures.json     (4 B, empty)
│   ├── harness_safety_questions.json (8 KB, 30 items)
│   ├── knowledge_seed.json          (6.9 MB, 2414 items)
│   ├── label_audit_seed.json        (502 KB, 1346 items)
│   ├── model_shortlist.json         (3 KB, 9 items)
│   ├── qa_seed.json                 (42 KB, 50 items)
│   ├── source_parse_failures.json   (3 KB, 14 items)
│   ├── test_chat.json               (146 B)
│   ├── test_cls.json                (166 B)
│   ├── test_realtime.json           (139 B)
│   ├── raw/
│   │   ├── academic_calendar/       (6 files, ~531 KB)
│   │   ├── admission/               (2 files, ~19 MB — large PDF)
│   │   ├── dining/                  (41 files, ~614 KB)
│   │   ├── graduation/              (8 files, ~19 MB — includes PDFs)
│   │   ├── notices/                 (47 files, ~4.6 MB)
│   │   ├── shuttle/                 (2 files, ~304 KB)
│   │   └── tmp/                     (2 files, ~1 MB)
│   ├── sources/
│   │   ├── source_probe.json        (158 KB)
│   │   └── source_probe_stage0_stub.json (12 KB)
│   └── gold/
│       ├── task1_human_gold.json    (50 items — human-labeled Task 1)
│       ├── task2_answer_eval_gold.json (25 items — human-labeled Task 2 answers)
│       ├── task2_fact_gold.json     (25 items — human-labeled facts)
│       ├── task2_generalization_probe.json (60 items — generalization questions)
│       ├── task2_probe39_eval.json  (39 items — probe 39-set)
│       └── task2_public_probe_eval.json (14 items — public probe 14-set)
├── examples/cnu-campus/
│   ├── sutra.toml                   (tiny — references data/index.jsonl)
│   ├── data/
│   │   └── index.jsonl              (3 lines — STUB, not populated)
│   ├── evals/
│   │   └── smoke.json               (2 questions)
│   ├── prompts/
│   │   ├── system.md
│   │   └── answer.md
│   └── README.md
├── docs/evidence/                   (19 JSON files, all experiment results)
├── outputs/                         (8 JSON files, runtime outputs)
└── model/                           (runtime logs and experiment artifacts)
```

---

## File Inventory Table

### A. Root-level `data/` files

| Path | Purpose | Format | Producer | Consumer | Count | Category | Keep/Move | Notes |
|------|---------|--------|----------|----------|-------|----------|-----------|-------|
| `data/knowledge_seed.json` | Processed RAG knowledge corpus — chunked+structured docs from source HTML/PDF | JSON (array of objects) | `nlp_term.prepare.from_sources.build_knowledge_from_probe` | Sutra RAG retrieval, Task 2 chat, classifier training | 2414 docs | **Processed RAG data** — CNU-specific | **→ Move** to `examples/cnu-campus/data/processed/` | This is the primary RAG index. Should be converted to JSONL for Sutra compatibility. 5 domains: academic_calendar (480), dining (1145), graduation (85), notices (648), shuttle (56). |
| `data/cls_train_seed.json` | Training seed for Task 1 classifier — questions with label=domain | JSON array | Synthetic generation pipeline | Classifier training, label audit | 1346 items | **Training data** — CNU-specific (questions about CNU) | **→ Move** to `examples/cnu-campus/data/training/` | Used by `nlp_term.classify` and `validators`. |
| `data/label_audit_seed.json` | Label audit records — human review of classifier training labels | JSON array | Audit pipeline | Validators | 1346 items | **Evaluation artifact** — CNU-specific | **→ Move** to `examples/cnu-campus/data/eval/` | Parallel to cls_train_seed, same count. |
| `data/qa_seed.json` | QA pairs for Task 2 answer evaluation | JSON array | Synthetic/seed generation | Task 2 tests, answer eval | 50 items | **Training/eval data** — CNU-specific | **→ Move** to `examples/cnu-campus/data/eval/` | |
| `data/harness_safety_questions.json` | Safety scenario questions for harness experiment | JSON array | Manual/experiment setup | `test_harness_safety_experiment.py` | 30 items | **Experiment artifact** — CNU-specific | **→ Review** | Used by one test. Could move to `examples/cnu-campus/data/eval/`. |
| `data/model_shortlist.json` | Model selection reference — lists candidate LLMs | JSON array | Manual/decision doc | Reference only | 9 items | **Reference document** — generic | **→ Keep in docs** or move to `examples/cnu-campus/` | Not actually consumed by code. Decision rationale. |
| `data/collection_failures.json` | Log of source fetch failures | JSON array | `run_collect.py` | Debugging only | 0 items (empty) | **Diagnostic log** — ephemeral | **→ Ignore** (.gitignore candidate) | Empty when run succeeds. |
| `data/source_parse_failures.json` | Log of source parse failures | JSON array | `from_sources.py` | Debugging only | 14 items | **Diagnostic log** — ephemeral | **→ Ignore** (.gitignore candidate) | |
| `data/test_chat.json` | Test fixture for chat pipeline | JSON array | Manual | `test_*` | 2 items | **Test data** | **→ Review** | Stub/sample for CI. Keep if tests need it. |
| `data/test_cls.json` | Test fixture for classifier | JSON array | Manual | `test_*` | 2 items | **Test data** | **→ Review** | Stub/sample for CI. Keep if tests need it. |
| `data/test_realtime.json` | Test fixture for realtime (Task 3) | JSON array | Manual | `test_*` | 2 items | **Test data** | **→ Review** | Stub/sample for CI. Keep if tests need it. |

### B. `data/raw/` subdirectories — CNU Source Snapshots

| Path | Purpose | Format | Producer | Consumer | Count | Category | Keep/Move | Notes |
|------|---------|--------|----------|----------|-------|----------|-----------|-------|
| `data/raw/academic_calendar/*` | CNU academic calendar HTML snapshots (2023–2026) | HTML | `run_collect.py` fetch | `from_sources.py` parser, `test_calendar_adapter.py` | 6 files | **Source data** — CNU-specific | **→ Move** to `examples/cnu-campus/data/raw/` | Already gitignored by `.gitignore` pattern `data/raw/`. |
| `data/raw/admission/*` | CNU admission megastudy PDF | PDF, TXT | `run_collect.py` fetch | Potential source parser | 2 files (~19 MB) | **Source data** — CNU-specific | **→ Move** to `examples/cnu-campus/data/raw/` | Very large PDF. Already gitignored. |
| `data/raw/dining/*` | CNU cafeteria menu HTML snapshots (daily+weekly, June 2026) | HTML | `run_collect.py` fetch | `from_sources.py` parser, `test_dining_adapter.py` | 41 files | **Source data** — CNU-specific | **→ Move** to `examples/cnu-campus/data/raw/` | Already gitignored. |
| `data/raw/graduation/*` | Graduation requirement HTML + PDF snapshots | HTML, PDF | `run_collect.py` fetch | `from_sources.py` parser, `test_graduation_requirement_adapter.py` | 8 files | **Source data** — CNU-specific | **→ Move** to `examples/cnu-campus/data/raw/` | Already gitignored. |
| `data/raw/notices/*` | Academic notice board HTML snapshots | HTML | `run_collect.py` fetch | `from_sources.py` parser, `test_notice_adapter.py` | 47 files | **Source data** — CNU-specific | **→ Move** to `examples/cnu-campus/data/raw/` | Already gitignored. |
| `data/raw/shuttle/*` | Shuttle bus HTML snapshots | HTML | `run_collect.py` fetch | `from_sources.py` parser, `test_shuttle_adapter.py` | 2 files | **Source data** — CNU-specific | **→ Move** to `examples/cnu-campus/data/raw/` | Already gitignored. |
| `data/raw/tmp/*` | Temporary/exploratory files | PDF, PNG | Ad-hoc collection | None (exploratory) | 2 files | **Scratch** — temporary | → Delete from tracking | Already gitignored. |

### C. `data/sources/` — Source Probe Metadata

| Path | Purpose | Format | Producer | Consumer | Count | Category | Keep/Move | Notes |
|------|---------|--------|----------|----------|-------|----------|-----------|-------|
| `data/sources/source_probe.json` | Source collection inventory — URLs, checksums, parser assignments, stage status | JSON array | `run_collect.py --fetch` | `source_audit.py`, `from_sources.py`, `validators.py`, tests | ~15 entries | **Source metadata** — CNU-specific | **→ Move** to `examples/cnu-campus/data/` | Ties raw files to parsers. Critical for pipeline. Already gitignored. |
| `data/sources/source_probe_stage0_stub.json` | Stage 0 stub for offline testing | JSON array | Initial probe run | Tests | ~10 entries | **Source metadata** — CNU-specific | **→ Move** to `examples/cnu-campus/data/` | Smaller, for CI. |

### D. `data/gold/` — Gold Evaluation Sets

| Path | Purpose | Format | Producer | Consumer | Count | Category | Keep/Move | Notes |
|------|---------|--------|----------|----------|-------|----------|-----------|-------|
| `data/gold/task1_human_gold.json` | Human-labeled Task 1 classification gold set | JSON array | Human annotators | `test_classify_gold_eval.py`, `test_task1_hard_gates.py` | 50 items | **Gold evaluation** — CNU-specific | **→ Move** to `examples/cnu-campus/data/eval/` | Final evaluation set for Task 1. |
| `data/gold/task2_answer_eval_gold.json` | Human-evaluated Task 2 answer quality | JSON array | Human evaluators | `test_task2_answer_eval_artifact.py` | 25 items | **Gold evaluation** — CNU-specific | **→ Move** to `examples/cnu-campus/data/eval/` | |
| `data/gold/task2_fact_gold.json` | Human-verified fact corrections | JSON array | Human evaluators | `test_gold_contracts.py` | 25 items | **Gold evaluation** — CNU-specific | **→ Move** to `examples/cnu-campus/data/eval/` | |
| `data/gold/task2_generalization_probe.json` | Generalization test questions (60 items) | JSON array | Manual/test authorship | `test_probe39_experiment.py`, `test_task2_generalization_probe_contract.py` | 60 items | **Probe questions** — CNU-specific | **→ Move** to `examples/cnu-campus/data/eval/` | |
| `data/gold/task2_probe39_eval.json` | 39-set probe evaluation results | JSON array | Experiment run | `test_probe39_experiment.py` | 39 items | **Evaluation results** | **→ Move** to `examples/cnu-campus/data/eval/` | |
| `data/gold/task2_public_probe_eval.json` | 14 public probe evaluation results | JSON array | Experiment run | `test_probe39_experiment.py`, `test_task2_public_probe_contract.py` | 14 items | **Evaluation results** | **→ Move** to `examples/cnu-campus/data/eval/` | |

### E. `docs/evidence/` — Experiment Evidence (JSON)

All 19 files in `docs/evidence/` are **experiment/audit/diagnostic JSON outputs** — timestamped snapshots of experiment runs. They are CNU-specific and should stay in `docs/evidence/` as documentation evidence. Examples:

| Path | Purpose | Category |
|------|---------|----------|
| `docs/evidence/data-readiness-2026-06-09.json` | Data readiness audit manifest | **Evidence report** |
| `docs/evidence/gold-eval-2026-06-07.json` | Gold evaluation run results | **Evidence report** |
| `docs/evidence/harness-safety-experiment-2026-06-07.json` | Safety harness experiment | **Evidence report** |
| `docs/evidence/task2-probe39-harness-*-*.json` | Probe39 harness runs | **Evidence report** |
| `docs/evidence/task2-public-probe-harness-*-*.json` | Public probe harness runs | **Evidence report** |
| `docs/evidence/task2-public-probe-qwen-baseline-*-*.json` | Qwen answer baseline runs | **Evidence report** |

These are **NOT RAG source data**. Do not move them into `examples/cnu-campus/data/`.

### F. `examples/cnu-campus/` — Existing Stub

| Path | Purpose | Format | Category | Keep/Move | Notes |
|------|---------|--------|----------|-----------|-------|
| `examples/cnu-campus/data/index.jsonl` | RAG knowledge index (stub) | JSONL | **Stub** — only 3 fake rows | → Replace with real data from `knowledge_seed.json` | Never populated with real content. |
| `examples/cnu-campus/evals/smoke.json` | 2 smoke-test questions | JSON | **Eval fixture** | Keep | Works correctly. |
| `examples/cnu-campus/prompts/system.md` | System prompt template | MD | **Prompt** | Keep | Good. |
| `examples/cnu-campus/prompts/answer.md` | Answer prompt template | MD | **Prompt** | Keep | Good. |
| `examples/cnu-campus/sutra.toml` | Workspace config | TOML | **Config** | Keep | References `data/index.jsonl`. Will need path update if structure changes. |

---

## Current Code References

### References from `src/nlp_term/` (legacy pipeline)

| File | Line | Reference |
|------|------|-----------|
| `src/nlp_term/collect/base.py` | 47 | `raw_path=f"data/raw/{domain}/{source_id}.{raw_suffix}"` |
| `src/nlp_term/collect/run_collect.py` | 137 | `default=Path("data/sources/source_probe.json")` |
| `src/nlp_term/collect/run_collect.py` | 146 | `default=Path("data/collection_failures.json")` |
| `src/nlp_term/collect/source_audit.py` | 213 | `default=Path("data/sources/source_probe.json")` |
| `src/nlp_term/prepare/from_sources.py` | 248 | `default=Path("data/source_parse_failures.json")` |
| `src/nlp_term/paths.py` | 10–11 | `default = PROJECT_ROOT / "data"` (via `NLP_TERM_DATA_DIR` env) |

### References from `src/sutra/` (new package)

| File | Line | Reference |
|------|------|-----------|
| `src/sutra/cli.py` | 435 | Reports `toml_path.parent / 'data/index.jsonl'` — workspace-relative, so it uses the example workspace path |

### References from `tests/`

| File | Line | Reference |
|------|------|-----------|
| `tests/test_calendar_adapter.py` | 13 | `RAW_PATH = Path("data/raw/academic_calendar/academic_calendar.html")` |
| `tests/test_dining_adapter.py` | 11, 108, 150 | `RAW_PATH = Path("data/raw/dining/cnu_mobile_food.html")` |
| `tests/test_graduation_requirement_adapter.py` | 13 | `RAW_PATH = Path("data/raw/graduation/graduation_english_requirements.html")` |
| `tests/test_harness_safety_experiment.py` | 106 | `Path("data/harness_safety_questions.json")` |
| `tests/test_notice_adapter.py` | 12 | `RAW_PATH = Path("data/raw/notices/academic_notice_board.html")` |
| `tests/test_prepare_from_sources.py` | 60, 114 | `raw_path: "data/raw/shuttle/shuttle_bus.html"` |
| `tests/test_shuttle_adapter.py` | 12 | `RAW_PATH = Path("data/raw/shuttle/shuttle_bus.html")` |
| `tests/test_source_audit.py` | 13, 25, 36 | `source_probe_path=Path("data/sources/source_probe.json")` |
| `tests/test_structured_row_contract.py` | 20 | `raw_path="data/raw/dining/cnu_mobile_food.html"` |
| `tests/test_tier1_coverage_validator.py` | 33 | `` `raw_path`: f"data/raw/{domain}/{source_id}.html" `` |
| `tests/test_probe39_experiment.py` | 11–12 | `PUBLIC_PROBE_PATH`, `GENERALIZATION_PROBE_PATH` → `data/gold/` |
| `tests/test_task2_generalization_probe_contract.py` | 7 | `PROBE_PATH = Path("data/gold/task2_generalization_probe.json")` |
| `tests/test_task2_public_probe_contract.py` | 7 | `PROBE_PATH = Path("data/gold/task2_public_probe_eval.json")` |
| `tests/test_cli_diagnostics.py` | 76, 115, 153, 185, 217 | `index_path = "data/index.jsonl"` |
| `tests/test_cli.py` | 36 | `index_path = "data/index.jsonl"` |
| `tests/test_config_docs.py` | 28, 65, 92 | `index_path = "data/index.jsonl"` |
| `tests/test_service.py` | 117 | `index_path = "data/index.jsonl"` |

**Key finding:** Most test paths are hard-coded relative to project root (`data/...`). These will all need updating after migration.

---

## Proposed Target Layout

```
examples/cnu-campus/
├── sutra.toml                            # (update index_path)
├── README.md                             # (already exists, update content)
├── prompts/
│   ├── system.md                         # (keep)
│   └── answer.md                         # (keep)
├── seed/
│   ├── cls_train_seed.jsonl              # ← from data/cls_train_seed.json
│   ├── qa_seed.jsonl                     # ← from data/qa_seed.json
│   └── label_audit_seed.jsonl            # ← from data/label_audit_seed.json
├── data/
│   ├── raw/                              # ← from data/raw/*
│   │   ├── academic-calendar/
│   │   ├── admission/
│   │   ├── dining/
│   │   ├── graduation/
│   │   ├── notices/
│   │   └── shuttle/
│   ├── processed/
│   │   ├── knowledge-index.jsonl         # ← from data/knowledge_seed.json (converted to JSONL)
│   │   └── source-probe.json             # ← from data/sources/source_probe.json
│   ├── eval/
│   │   ├── task1-human-gold.json         # ← from data/gold/task1_human_gold.json
│   │   ├── task2-answer-eval-gold.json   # ← from data/gold/task2_answer_eval_gold.json
│   │   ├── task2-fact-gold.json          # ← from data/gold/task2_fact_gold.json
│   │   ├── task2-generalization-probe.json # ← from data/gold/task2_generalization_probe.json
│   │   ├── task2-probe39-eval.json       # ← from data/gold/task2_probe39_eval.json
│   │   ├── task2-public-probe-eval.json  # ← from data/gold/task2_public_probe_eval.json
│   │   ├── harness-safety-questions.json # ← from data/harness_safety_questions.json
│   │   └── smoke.json                    # (keep existing)
│   └── failures/ (optional — for logs)
│       └── source-parse-failures.json    # ← from data/source_parse_failures.json
```

**Rationale for changes from the initial strawman:**
- `seed/` added: `cls_train_seed.json` and friends are not RAG index data and not eval results — they are synthetic training material for Task 1. A separate `seed/` directory makes this clear.
- `eval/` keeps the existing `smoke.json` plus all gold/probe sets.
- `failures/` is optional; can be `.gitignore`d instead.
- The stub `data/index.jsonl` is replaced by `data/processed/knowledge-index.jsonl`.
- `knowledge_seed.json` (JSON array) → `knowledge-index.jsonl` (JSONL) for Sutra-native streaming.

### Recommended naming conventions

| Old (inconsistent) | New (preferred) |
|---|---|
| `knowledge_seed.json` | `knowledge-index.jsonl` |
| `cls_train_seed.json` | `cls-train-seed.jsonl` |
| `label_audit_seed.json` | `label-audit-seed.jsonl` |
| `task1_human_gold.json` | `task1-human-gold.json` |
| `task2_generalization_probe.json` | `task2-generalization-probe.json` |
| `source_probe.json` | `source-probe.json` |
| `academic_calendar_2026.html` | `academic-calendar-2026.html` |
| `cnu_mobile_food_2026_06_09.html` | `dining-2026-06-09.html` |

Rules:
- lowercase
- kebab-case
- domain prefix for raw source files (e.g., `dining-`, `academic-calendar-`)
- `.jsonl` for line-delimited JSON (stream-friendly), `.json` only for small/structured files
- date stamps in ISO-ish format: `YYYY-MM-DD` or `YYYY` as appropriate

---

## Migration Plan

### Phase 1: Conversion and staging (no code changes)

1. **Convert `knowledge_seed.json` to JSONL** and write to `examples/cnu-campus/data/processed/knowledge-index.jsonl`
   - One JSON object per line
   - Validate that all 2414 lines are valid JSON
   - Verify the existing Sutra `documents.py` parser can read it

2. **Convert training seeds** (`cls_train_seed.json`, `label_audit_seed.json`, `qa_seed.json`) to JSONL in `examples/cnu-campus/seed/`

3. **Copy gold evaluation files** (unchanged format) to `examples/cnu-campus/data/eval/`

4. **Copy source-probe metadata** to `examples/cnu-campus/data/processed/`

5. **Update `examples/cnu-campus/sutra.toml`** to point `index_path` to `data/processed/knowledge-index.jsonl`

6. **Update `examples/cnu-campus/README.md`** to describe the data layout

### Phase 2: Update code references

7. **Update `src/nlp_term/paths.py`**: Optionally accept `SUTRA_EXAMPLE_DATA_DIR` or change behavior when `NLP_TERM_DATA_DIR` points to the example workspace

8. **Update `src/nlp_term/collect/` defaults**: Change default output paths or add `--data-dir` parameter (but see note below)

9. **Update test files** that hard-code `data/...` paths:
   - Adapter tests: `RAW_PATH` → point to `examples/cnu-campus/data/raw/...`
   - Probe/eval tests: gold paths → `examples/cnu-campus/data/eval/...`
   - CLI tests: `index_path` → `examples/cnu-campus/data/processed/knowledge-index.jsonl`
   - Source audit tests: `source_probe_path` → `examples/cnu-campus/data/processed/source-probe.json`

### Phase 3: Clean up `data/` in the old location

10. **Update `.gitignore`** to ignore the old `data/` patterns more explicitly, or remove data files from `.gitignore` and let git status show what would be removed

11. **After confirming everything works from `examples/cnu-campus/`**, archive or delete the old `data/` root files

### Phase 4: What should NOT be migrated

- `docs/evidence/*.json` — keep in place as experiment documentation
- `model/*` — runtime artifacts and logs; already gitignored
- `outputs/*` — runtime output; already gitignored
- `data/test_*.json` — small test stubs; can be kept or replaced with inline test fixtures
- `data/collection_failures.json`, `data/source_parse_failures.json` — ephemeral logs; should be `.gitignore`d
- `data/raw/tmp/*` — scratch files; should be deleted

---

## Risks / Open Questions

| # | Risk / Question | Impact |
|---|---|---|
| 1 | **`data/raw/` is already in `.gitignore`** — the raw HTML/PDF files are not tracked by git. The migration plan must account for the fact that the real raw files live on disk but not in the repo. The `.gitignore` entry will need to be adjusted for `examples/cnu-campus/data/raw/`. | Medium |
| 2 | **`knowledge_seed.json` is a JSON array (2414 items in memory)** — converting to JSONL is straightforward but changes the reading pattern from `json.load()` to line-by-line iteration. Sutra's `documents.py` already expects JSONL, so this is a safe change. | Low (verified by Sutra's JSONL parser) |
| 3 | **Test files use hard-coded relative paths `data/...`** — ~15 test files need path updates. These will break until phase 2. | High (coordinate with test migration) |
| 4 | **`nlp_term.prepare.from_sources.py` defaults** write to `data/source_parse_failures.json` — still a legacy path. If the pipeline still runs, failures will end up in the old location. Decide: update the default or require `--failures-output`. | Low |
| 5 | **`admission/` raw data (~19 MB PDF)** — large and not yet consumed by any parser. Consider whether to keep in raw/ or omit from the example workspace. | Low (if not used, can stay gitignored and ignored) |
| 6 | **What about `data/sources/source_probe_stage0_stub.json`?** — a smaller stub for offline testing. Potentially useful for CI. Move to `examples/cnu-campus/data/`. | Low |
| 7 | **`data/harness_safety_questions.json` is CNU-specific** but the harness experiment lives in the old pipeline. If the experiment is superseded, this file may become obsolete. | Low |
| 8 | **Dual-path issue**: After migration, does the old `nlp_term` pipeline still read from `data/` or switch to `examples/cnu-campus/`? If both paths work temporarily, there will be duplication. Clarify whether the legacy pipeline is being retired. | Medium |
| 9 | **Sutra `config.py` and `documents.py` reference `index_path` from `sutra.toml`** — if the toml path is updated, Sutra will automatically pick up the new location. This is the cleanest dependency point for the migration. | Low (good design) |
