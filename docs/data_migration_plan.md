# Revised Data Cleanup Migration Plan

> Generated: 2026-06-09
> Status: Plan (do not implement yet)

## Summary

The `dev` branch is becoming Sutra-focused; the old `nlp_term` implementation moves to `legacy/nlp-term`. The one artifact Sutra needs for its CNU RAG workspace is the processed knowledge corpus (2414 docs, 6.9 MB at `data/knowledge_seed.json`). Everything else — raw source snapshots, classifier training seeds, legacy eval gold sets, generated experiment reports, and runtime outputs — either belongs downstream (later commits), stays on the legacy branch, or is generated ephemera. The first migration converts only the knowledge corpus to Sutra-native JSONL and wires it into the existing workspace, with zero changes to legacy pipeline code or test paths.

---

## Key Decisions

1. **`dev` is Sutra-only.** The old `nlp_term` runtime, classifiers, and tests are not priorities here. They will live on the `legacy/nlp-term` branch.
2. **First commit is RAG-index-only.** No raw sources, no training seeds, no gold/probe/eval files, no admission PDFs, no experiment reports.
3. **Strict "gold" terminology.** Only `human-gold` if there is clear evidence of human-verified expected answers and evidence. Other files are `public-probe`, `regression-probe`, `task1-labels`, `experiment-report`, or `generated-run-output`.
4. **No dual-path maintenance.** Sutra reads from `examples/cnu-campus/`. The old `data/` files are left untouched for now but will be migrated to the legacy branch.
5. **Sutra tests are self-contained.** They create their own `tmp_path` fixtures and do not reference the real project data. No test updates are required for the first commit.
6. **Small, reviewable commits.** Each commit does exactly one thing — convert data OR update config OR update code OR clean up.

---

## Evaluation Artifact Classification

| Path | Format | Count | Contains | Producer | Human-verified? | Correct category | Recommended location | Notes |
|---|---|---|---|---|---|---|---|---|
| `data/knowledge_seed.json` | JSON array | 2414 | Chunked knowledge docs with domain labels, body text, source metadata | `nlp_term.prepare.from_sources` | No (processed, not verified) | **rag-source** | `examples/cnu-campus/data/processed/knowledge-index.jsonl` | Primary RAG index. Convert to JSONL for Sutra. |
| `data/cls_train_seed.json` | JSON array | 1346 | Template-generated classifier training questions + domain labels | Synthetic pipeline | Partially (`validated: true` on some) | **task1-labels** | `legacy/nlp-term` branch | Legacy classifier training. No value to Sutra. |
| `data/label_audit_seed.json` | JSON array | 1346 | Human-reviewed label verdicts for classifier training items | Audit pipeline | Yes (human review) | **task1-labels** | `legacy/nlp-term` branch | Audit of classifier labels. Not RAG data. |
| `data/qa_seed.json` | JSON array | 50 | QA pairs: user question + model-generated answer | Synthetic gen | No | **task1-labels** / **regression-probe** | `legacy/nlp-term` branch | Used for Task 2 answer eval. Legacy only. |
| `data/gold/task1_human_gold.json` | JSON array | 50 | Human-labeled classification questions + labels, `annotator: human`, `validated: true` | Human annotators | Yes (human labels) | **task1-labels** (not gold for Sutra RAG) | `legacy/nlp-term` branch | Classifier evaluation gold. Not chatbot gold. |
| `data/gold/task2_answer_eval_gold.json` | JSON array | 25 | Questions with `expected_fact_ids`, `must_not_claim`; scores are null | Human template | Partially (human expected facts, but scores unfilled) | **human-gold** (intended, incomplete) | `legacy/nlp-term` branch | Has human-defined expected answers but scores not filled. Not ready. |
| `data/gold/task2_fact_gold.json` | JSON array | 25 | Fact ID + `claim` + `evidence_quote` + `source_url` | Human reviewers | Yes (human-verified facts) | **human-gold** | `legacy/nlp-term` branch | Human-verified fact corrections. Legacy eval. |
| `data/gold/task2_generalization_probe.json` | JSON array | 60 | Questions with `expected_label`, `expected_domain`, `expected_temporal_type` | Test authorship | No | **regression-probe** | `examples/cnu-campus/evals/` or `legacy/` | Generalization test questions. Useful as regression suite. |
| `data/gold/task2_probe39_eval.json` | JSON array | 39 | Questions with `expected_label`, `expected_domain`, `expected_temporal_type` | Experiment setup | No | **regression-probe** | `examples/cnu-campus/evals/` or `legacy/` | Probe 39 evaluation set. Used by experiment runner. |
| `data/gold/task2_public_probe_eval.json` | JSON array | 14 | Questions with `expected_label`, `expected_temporal_type`, `expected_behavior` | Assignment docs | No | **public-probe** | `examples/cnu-campus/evals/` | Public/user-facing example questions from assignment. |
| `data/harness_safety_questions.json` | JSON array | 30 | Safety scenario questions with `expected_label`, `expected_answer_kind` | Manual setup | No | **regression-probe** | `legacy/nlp-term` branch | Harness experiment. Legacy-only. |
| `data/model_shortlist.json` | JSON array | 9 | Model selection reference docs | Manual | No | **legacy-only** | `legacy/nlp-term` branch or `docs/` | Reference document, not consumed by code. |
| `data/collection_failures.json` | JSON array | 0 | Empty failure log | `run_collect.py` | No | **ignore/cache** | Delete or gitignore | Ephemeral diagnostic log. |
| `data/source_parse_failures.json` | JSON array | 14 | Source parse failure log | `from_sources.py` | No | **ignore/cache** | Delete or gitignore | Ephemeral diagnostic log. |
| `data/test_chat.json` | JSON array | 2 | Stub chat test questions | Manual | No | **legacy-only** | `legacy/nlp-term` branch | Assignment test fixture for Task 2. |
| `data/test_cls.json` | JSON array | 2 | Stub classifier test questions | Manual | No | **legacy-only** | `legacy/nlp-term` branch | Assignment test fixture for Task 1. |
| `data/test_realtime.json` | JSON array | 2 | Stub realtime test questions | Manual | No | **legacy-only** | `legacy/nlp-term` branch | Assignment test fixture for Task 3. |
| `data/raw/` (all subdirs) | HTML/PDF | 104 | Raw source snapshots from CNU websites | `run_collect.py` | No | **raw-source** | `examples/cnu-campus/data/raw/` (future) | Currently gitignored. Move after first commit. |
| `data/sources/source_probe.json` | JSON array | ~15 | Source collection inventory | `run_collect.py` | No | **legacy-only** | `legacy/nlp-term` branch | Source metadata for legacy pipeline. |
| `data/sources/source_probe_stage0_stub.json` | JSON array | ~10 | Smaller probe stub | Initial run | No | **legacy-only** | `legacy/nlp-term` branch | For CI tests in legacy pipeline. |
| `docs/evidence/*.json` (19 files) | JSON objects | N/A | Experiment run reports, audit manifests, harness outputs | Experiment runners | No | **experiment-report** | Stay in `docs/evidence/` | Not RAG source data. Evidence documentation. |
| `outputs/*.json` (8 files) | JSON | N/A | Runtime chat/classifier outputs | Runtime pipeline | No | **generated-run-output** | Keep gitignored | Runtime outputs. Already gitignored. |
| `model/*` (39 items) | Various | N/A | Runtime logs, classifier models, llama server output | Runtime | No | **generated-run-output** / **ignore/cache** | Keep gitignored | Runtime artifacts. Already gitignored. |
| `examples/cnu-campus/data/index.jsonl` | JSONL | 3 | Stub entries | Manual | No | **rag-source (stub)** | DELETE | Replace with real data. |
| `examples/cnu-campus/evals/smoke.json` | JSON | 2 | Smoke test questions | Manual | No | **public-probe** | Keep | Works correctly. 2 questions about graduation/sugang. |

---

## Proposed Target Layout

Final layout after all migration phases (not just the first commit):

```
examples/cnu-campus/
├── sutra.toml                     # index_path → data/processed/knowledge-index.jsonl
├── README.md                      # describes the workspace
├── .gitignore                     # optional: manage what gets tracked
├── data/
│   ├── processed/
│   │   └── knowledge-index.jsonl  # ← migrated in commit 1 (2414 docs)
│   └── raw/                       # ← migrated later (or not at all if sources stay gitignored)
│       ├── academic-calendar/
│       ├── dining/
│       ├── graduation/
│       ├── notices/
│       └── shuttle/
├── evals/
│   ├── smoke.json                 # keep as-is
│   ├── public-probes.jsonl        # ← from data/gold/task2_public_probe_eval.json (future)
│   └── regression-probes.jsonl    # ← from data/gold/task2_generalization_probe.json + probe39 (future)
└── prompts/
    ├── system.md                  # keep as-is
    └── answer.md                  # keep as-is
```

### First-commit layout (minimal)

```
examples/cnu-campus/
├── sutra.toml                     # updated index_path
├── README.md                      # updated
├── data/
│   └── processed/
│       └── knowledge-index.jsonl  # 2414 lines, ~6.9 MB
├── evals/
│   └── smoke.json                 # unchanged
└── prompts/
    ├── system.md                  # unchanged
    └── answer.md                  # unchanged
```

---

## Revised Commit Plan

### Commit 1: Convert RAG index and wire into workspace

**Type:** `feat(data): populate examples/cnu-campus/data/processed/knowledge-index.jsonl`

**Files affected:**
- `examples/cnu-campus/data/processed/knowledge-index.jsonl` — NEW (2414 lines)
- `examples/cnu-campus/data/index.jsonl` — DELETE (3-row stub)
- `examples/cnu-campus/sutra.toml` — EDIT (update `index_path`)
- `examples/cnu-campus/README.md` — EDIT (describe real data)
- `src/sutra/cli.py` — EDIT (line 435, update display path string)
- `.gitignore` — possibly EDIT (add negation for `examples/cnu-campus/data/processed/`)

**Actions:**
1. Run conversion script: read `data/knowledge_seed.json` (UTF-8), map fields per table below, write as JSONL to `examples/cnu-campus/data/processed/knowledge-index.jsonl`
2. Delete `examples/cnu-campus/data/index.jsonl`
3. In `examples/cnu-campus/sutra.toml`: change `index_path = "data/index.jsonl"` → `index_path = "data/processed/knowledge-index.jsonl"`
4. In `src/sutra/cli.py:435`: change `toml_path.parent / 'data/index.jsonl'` → `toml_path.parent / 'data/processed/knowledge-index.jsonl'`
5. Update `examples/cnu-campus/README.md` to describe the populated data
6. Verify `.gitignore` does not block the new path

**Field mapping (`knowledge_seed.json` → Sutra `Document` JSONL):**

| Source key | Target key | Notes |
|---|---|---|
| `doc_id` | `id` | Direct |
| `body` | `text` | Chunk content |
| `title` | `title` | Direct |
| `source_url` | `source_url` | Direct |
| `domain` | `source_name` | CNU domain (e.g., `dining`, `graduation`) |
| `label` | `metadata.label` | Classification label |
| `date` | `metadata.date` | If not null |
| `source_id` | `metadata.source_id` | Original source ID |
| `section` | `metadata.section` | Chunk section |
| All other `metadata` keys | `metadata.*` | Preserve verbatim |

**Verification:**
```powershell
# Line count
python -c "print(len([l for l in open('examples/cnu-campus/data/processed/knowledge-index.jsonl', encoding='utf-8') if l.strip()]))"
# Expected: 2414

# Domain distribution
python -c "import json; from collections import Counter; d=[json.loads(l) for l in open('examples/cnu-campus/data/processed/knowledge-index.jsonl', encoding='utf-8') if l.strip()]; print(dict(Counter(x['source_name'] for x in d)))"
# Expected: {'academic_calendar': 480, 'dining': 1145, 'graduation': 85, 'notices': 648, 'shuttle': 56}

# Sutra Document validation
uv run python -c "from sutra.models import Document; import json; [Document.model_validate(json.loads(l)) for l in open('examples/cnu-campus/data/processed/knowledge-index.jsonl', encoding='utf-8')]; print('All 2414 documents valid')"

# Workspace validation
uv run sutra workspace validate --workspace examples/cnu-campus/sutra.toml

# Docs check
uv run sutra docs check --workspace examples/cnu-campus/sutra.toml

# Echo-mode smoke
uv run sutra ask --workspace examples/cnu-campus/sutra.toml --echo "수강신청은 언제 시작하나요?"

# Sutra tests still pass
uv run pytest tests/sutra -q

# Ruff check
uv run ruff check src/sutra tests/sutra
```

**Rollback risk:** Very low. Old `data/` files untouched. Only new file added. Delete `knowledge-index.jsonl` and revert `sutra.toml` + `cli.py` + `README.md` to undo.

**Required before GitHub push:** Yes.

---

### Commit 2: Add Sutra eval probes

**Type:** `feat(evals): add public probes and regression probes to examples/cnu-campus/evals/`

**Files affected:**
- `examples/cnu-campus/evals/public-probes.jsonl` — NEW (14 items from `data/gold/task2_public_probe_eval.json`)
- `examples/cnu-campus/evals/regression-probes.jsonl` — NEW (60+39 items from `data/gold/task2_generalization_probe.json` + `data/gold/task2_probe39_eval.json`)
- (optional) Update `sutra.toml` to reference eval probes

**Actions:**
1. Copy+convert public probe questions to JSONL in `examples/cnu-campus/evals/`
2. Copy+convert generalization probe + probe39 questions to JSONL in `examples/cnu-campus/evals/`
3. (Optional) Add `[evals]` section to `sutra.toml` if Sutra supports running evals

**Note:** Only do this commit if Sutra's eval runner (`sutra eval`) actually uses these files. If Sutra doesn't have an eval subcommand yet, skip this commit.

**Verification:** `uv run sutra workspace validate --workspace examples/cnu-campus/sutra.toml`

**Rollback risk:** Low. No code changes.

**Required before GitHub push:** No (can be deferred).

---

### Commit 3: Migrate raw source snapshots (optional)

**Type:** `feat(data): add raw source snapshots to examples/cnu-campus/data/raw/`

**Files affected:**
- `examples/cnu-campus/data/raw/` — populated from `data/raw/` (minus `admission/` and `tmp/`)
- `examples/cnu-campus/data/raw/README.md` — NEW (provenance doc)
- `.gitignore` — EDIT (add `!examples/cnu-campus/data/raw/` negation)

**Actions:**
1. Copy `data/raw/{academic_calendar,dining,graduation,notices,shuttle}` to `examples/cnu-campus/data/raw/` (kebab-case directory names)
2. Skip `data/raw/admission/` (19 MB PDFs, no consumer) and `data/raw/tmp/` (scratch)
3. Write `examples/cnu-campus/data/raw/README.md`
4. Update `.gitignore`

**Note:** `data/raw/` is currently gitignored. The raw files exist on disk but won't travel with git unless the gitignore rule is negated for the new path. Decide: if raw source files are useful for the Sutra workspace to be self-contained on GitHub, track them. If they are too large or too transient, keep them gitignored.

**Verification:** `git status` shows the new raw files as tracked.

**Rollback risk:** Low (new files only).

**Required before GitHub push:** Decide per size/completeness preference.

---

### Commit 4: Clean up Sutra test fixture strings (cosmetic)

**Type:** `chore(tests): update test toml templates to use data/processed/ paths`

**Files affected:**
- `tests/sutra/test_cli.py` — template string `"data/index.jsonl"` → `"data/processed/knowledge-index.jsonl"`
- `tests/sutra/test_cli_diagnostics.py` — same
- `tests/sutra/test_config_docs.py` — same
- `tests/sutra/test_service.py` — same

**Actions:**
Replace all occurrences of `index_path = "data/index.jsonl"` with `index_path = "data/processed/knowledge-index.jsonl"` in test toml template strings.

**Note:** These tests create their own temp data at the path specified in the template. They do NOT read from the real project data. This change is purely cosmetic — making test fixtures consistent with the new convention. The tests would pass either way because the fixture creates `data/index.jsonl` or `data/processed/knowledge-index.jsonl` relative to `tmp_path`.

**Verification:** `uv run pytest tests/sutra -q`

**Rollback risk:** Minimal.

**Required before GitHub push:** No (cosmetic), but recommended for consistency.

---

### Commit 5: Archive legacy data to `legacy/nlp-term` branch

**Type:** `chore: move legacy data files to legacy/nlp-term branch`

**Actions:**
1. Create `legacy/nlp-term` branch at the pre-migration commit
2. On `dev`, remove legacy-only files:
   - `data/cls_train_seed.json`
   - `data/label_audit_seed.json`
   - `data/qa_seed.json`
   - `data/gold/` (entire directory)
   - `data/harness_safety_questions.json`
   - `data/model_shortlist.json`
   - `data/test_*.json`
   - `data/collection_failures.json`
   - `data/source_parse_failures.json`
   - `data/sources/` (entire directory)
3. Keep `data/knowledge_seed.json` as a source-of-truth reference (or delete if no longer needed)
4. Keep `data/raw/` gitignored (or migrate as in Commit 3)

**Verification:** `git status` shows only expected deletes. No Sutra functionality breaks.

**Rollback risk:** Medium (file deletes). Recoverable from git.

**Required before GitHub push:** Yes (to avoid pushing 71 MB of legacy data).

---

## First Commit Executor Brief

### Input
- Source: `data/knowledge_seed.json` (UTF-8 JSON array, 2414 items)
- Field mapping per table above

### Output
- `examples/cnu-campus/data/processed/knowledge-index.jsonl` (UTF-8 JSONL, exactly 2414 non-blank lines)

### Conversion constraints
1. Read with `encoding="utf-8"` (CP949 will fail on Korean text)
2. Do NOT import `sutra.models.Document` to generate rows — write raw JSON lines with the correct keys
3. May use `Document.model_validate()` only as a POST-CONVERSION verification step
4. Preserve all metadata keys from the source item's `metadata` dict
5. Add `label`, `date`, `source_id`, `section`, `domain` from the top-level item into `metadata` (they are top-level in `knowledge_seed.json` but belong in `metadata` for Sutra)
6. Fail if line count ≠ 2414
7. Fail if domain distribution differs
8. Write one JSON object per line, no trailing comma, no enclosing array

### Expected domain distribution
```
academic_calendar: 480
dining: 1145
graduation: 85
notices: 648
shuttle: 56
Total: 2414
```

### File edits
1. `examples/cnu-campus/sutra.toml` line 15: change from `index_path = "data/index.jsonl"` to `index_path = "data/processed/knowledge-index.jsonl"`
2. Delete `examples/cnu-campus/data/index.jsonl`
3. `src/sutra/cli.py` line 435: change `toml_path.parent / 'data/index.jsonl'` to `toml_path.parent / 'data/processed/knowledge-index.jsonl'`
4. `examples/cnu-campus/README.md`: update to reflect that the workspace now has a processed knowledge index with 2414 documents

### Verification commands (run ALL)
```powershell
uv run pytest tests/sutra -q
uv run ruff check src\sutra tests\sutra
uv run sutra workspace validate --workspace examples/cnu-campus/sutra.toml
uv run sutra docs check --workspace examples/cnu-campus/sutra.toml
uv run sutra ask --workspace examples/cnu-campus/sutra.toml --echo "수강신청은 언제 시작하나요?"
```

### Test backstop
The Sutra test suite creates its own temporary workspaces in `tmp_path` with their own `data/index.jsonl` files. These tests do NOT read from the real project data. They should continue passing as long as the Sutra CLI logic hasn't changed. The `cli.py` display string change is cosmetic and won't break any test assertions — the tests check exit codes and stdout content, not the display path.

### Rollback
```powershell
git checkout -- examples/cnu-campus/sutra.toml src/sutra/cli.py examples/cnu-campus/README.md
Remove-Item -Recurse examples/cnu-campus/data/processed/
git checkout -- examples/cnu-campus/data/index.jsonl
```

---

## GitHub Policy

### What should be tracked on `dev`
| Item | Track? | Rationale |
|---|---|---|
| `examples/cnu-campus/data/processed/knowledge-index.jsonl` | **Track** (6.9 MB) | The primary RAG index. Needed for workspace to function. |
| `examples/cnu-campus/evals/smoke.json` | Already tracked | Keep. |
| `examples/cnu-campus/prompts/` | Already tracked | Keep. |
| `examples/cnu-campus/sutra.toml` | Already tracked | Keep. |
| `examples/cnu-campus/README.md` | Already tracked | Keep. |
| `examples/cnu-campus/data/raw/` (optional) | **Track** if sources should travel with repo | Raw HTML snapshots (~5 MB without admission PDFs). |
| `src/sutra/` | Already tracked | Sutra core. Domain-neutral. |
| `tests/sutra/` | Already tracked | Sutra tests. |

### What should be ignored or on legacy branch
| Item | Disposition | Rationale |
|---|---|---|
| `data/` root files (except `knowledge_seed.json`) | **Legacy branch** | Classifier seeds, gold sets, test fixtures, probes, ephemeral logs. |
| `data/knowledge_seed.json` | **Keep or legacy** | Keep on `dev` as source-of-truth reference until the JSONL is proven stable, then delete. |
| `data/raw/` | **Gitignored** (stay ignored) | Raw sources remain on disk but not in git. Move to `examples/cnu-campus/data/raw/` if tracking is desired. |
| `data/sources/` | **Gitignored** (stay ignored) | Source probe metadata for legacy pipeline. |
| `docs/evidence/` | **Keep on dev** | Experiment documentation, not RAG source data. Small JSON files. |
| `docs/superpowers/` | **Keep on dev** | Historical plans and reference. |
| `outputs/` | **Keep gitignored** | Runtime outputs. |
| `model/` | **Keep gitignored** | Runtime logs and model artifacts. |
| `src/nlp_term/` | **Legacy branch** | Old implementation. |
| Legacy tests (`tests/test_*.py` not in `tests/sutra/`) | **Legacy branch** | ~43 test files that reference old `nlp_term` code paths. |

### `.gitignore` amendments
| Change | Reason |
|---|---|
| Add `!examples/cnu-campus/data/processed/` | Ensure the new processed data is not caught by `data/` ignores |
| Keep `data/raw/` | Old location stays ignored |
| Add `data/collection_failures.json` | Ephemeral log |
| Add `data/source_parse_failures.json` | Ephemeral log |

---

## Risks and Open Questions

| # | Risk / Question | Impact | Resolution |
|---|---|---|---|
| 1 | **`data/raw/` gitignore pattern** `data/raw/` matches both `data/raw/` and `examples/cnu-campus/data/raw/`. The negation `!examples/cnu-campus/data/raw/` must be added if raw sources are tracked under the example workspace. | Medium | Test with `git add --dry-run` before committing. |
| 2 | **`knowledge_seed.json` to JSONL field fidelity.** The `source_name` field (=domain) is now the domain name (e.g., `dining`), not a human-readable source name. Sutra's retrieval and prompt rendering may display this to the user. | Low | Verify with `--echo` mode that evidence source_name is reasonable. |
| 3 | **Sutra test fixture string mismatch.** If `tests/sutra/test_config_docs.py` asserts `config.rag.index_path == (tmp_path / "data" / "index.jsonl").resolve()` (line 40), this assertion would fail if we change only the template string. But we are NOT changing test fixtures in Commit 1 — only the real `sutra.toml`. The test creates its own temp config, so the strings are independent. | None | No impact. Tests use their own tmp data. |
| 4 | **`sutra docs check` CLI display path** — line 435 of `cli.py` constructs `toml_path.parent / 'data/index.jsonl'` for a display string. If this is updated in Commit 1 to `data/processed/knowledge-index.jsonl`, the display will be correct. If not updated, the display will show the old stub path but the actual `check_docs` function reads from `config.rag.index_path` which comes from the TOML. | Low | Cosmetic display mismatch. Fix in Commit 1. |
| 5 | **Dual-path for `knowledge_seed.json`.** After Commit 1, both `data/knowledge_seed.json` and `examples/cnu-campus/data/processed/knowledge-index.jsonl` exist. Nothing reads the old path anymore (Sutra reads from TOML, legacy pipeline is de-prioritized). | Low | Acceptable until Commit 5 (cleanup). |
| 6 | **Should `admission/` PDFs (~19 MB) ever be tracked?** They are large, not consumed by any parser, and would bloat the repo. | Medium | Keep gitignored permanently. Document in raw README. |
| 7 | **What about `data/gold/task2_answer_eval_gold.json`?** It has human-defined `expected_fact_ids` but null scores. It is a human-gold *template* but not yet completed. Should it move to `examples/cnu-campus/` for future evaluation use? | Low | Defer until Sutra has an eval runner. Leave on legacy branch. |
| 8 | **Should `data/gold/task2_public_probe_eval.json` stay as a probe file?** It has `expected_behavior` strings that describe what the answer should do. This is the closest thing to a Sutra eval probe. | Low | Move to `examples/cnu-campus/evals/public-probes.jsonl` in Commit 2. |

---

## Acceptance Criteria

The first commit (RAG index migration) is safe when all of the following pass:

1. **`examples/cnu-campus/data/processed/knowledge-index.jsonl` has exactly 2414 non-blank lines**, each being valid JSON with the keys: `id`, `text`, `title`, `source_url`, `source_name`, `metadata`.

2. **Domain distribution matches original:**
   - `academic_calendar`: 480
   - `dining`: 1145
   - `graduation`: 85
   - `notices`: 648
   - `shuttle`: 56

3. **No data loss in metadata:** Every item in `knowledge_seed.json` has its full `metadata` dict preserved (including nested keys like `parser`, `chunking_strategy`, `raw_path`, `raw_checksum`, etc.).

4. **`models.Document.model_validate()` passes for all 2414 lines** (one-liner verification).

5. **Workspace validation passes:**
   ```powershell
   uv run sutra workspace validate --workspace examples/cnu-campus/sutra.toml
   # → "Workspace configuration is valid."
   ```

6. **Document index check passes with correct counts:**
   ```powershell
   uv run sutra docs check --workspace examples/cnu-campus/sutra.toml
   # → "Document index check passed. Total documents: 2414"
   ```

7. **Echo-mode query returns expected evidence:**
   ```powershell
   uv run sutra ask --workspace examples/cnu-campus/sutra.toml --echo "수강신청은 언제 시작하나요?"
   # → Returns a non-error answer with evidence containing 'academic_calendar' source_name
   ```

8. **Sutra test suite passes:**
   ```powershell
   uv run pytest tests/sutra -q
   # → All tests pass
   ```

9. **Ruff check passes on sutra code:**
   ```powershell
   uv run ruff check src/sutra tests/sutra
   # → No errors
   ```

10. **Old `data/knowledge_seed.json` is unchanged** (not moved or deleted).

11. **`examples/cnu-campus/data/index.jsonl` is deleted** (the 3-row stub).

12. **Git does not ignore the new files:**
    ```powershell
    git check-ignore examples/cnu-campus/data/processed/knowledge-index.jsonl
    # → (no output — file is NOT ignored)
    ```
