# Meeting Room Dashboard

작성일: 2026-06-06

## phase-2.2-qa-data-2026-06-06

- meeting_id: `phase-2.2-qa-data-2026-06-06`
- opened_at: `2026-06-06`
- trigger_type: `REQUEST_CHANGES_AFTER_MAX_CRITIC_LOOP`
- phase: `Phase 2.2 QA Dataset Generation`
- step_id: `phase-2.2-qa-dataset-generation`
- request_changes_source: Source/Data critic final recheck
- attempt_count: 3 critic loops
- status: `closed`
- current_blocker: resolved; final Source/Data critic passed all regenerated QA rows
- research_used:
  - `docs/meeting_protocol.md` research grounding
  - `docs/meetings/phase-2.2-qa-data-2026-06-06-meeting.md`
  - local artifacts: `data/qa_seed.json`, `data/knowledge_seed.json`, `docs/pre_colab_failure_log.md`
- candidate_options:
  - A: exclude polluted chunks before QA generation
  - B: add positive evidence span selection
  - C: re-chunk source docs and backfill clean sections
- selected_option: B first, with A inside B and C as recovery if row gates fail
- second_cycle_selected_option: source-specific DOM main-content extraction for CNU HTML sources, plus knowledge-body chrome gates
- decision_rule_used: source-backed evidence and deterministic validators outrank numeric-only pass
- validator_gate:
  - `uv run python -m nlp_term.validators --dataset-quality --data-dir data --min-qa-rows 50 --min-qa-per-label 8 --require-qa-source --require-validated --no-dry-run`
  - deterministic checks for generic fallback evidence, case-insensitive boilerplate, mojibake/private-use glyphs, evidence length, Korean density, label keywords, and source grounding
- review_gate: Source/Data critic must pass all generated QA rows
- commands_to_run:
  - `uv run python -m nlp_term.prepare.build_all --output-dir data`
  - `uv run python -m nlp_term.validators --dataset-quality --data-dir data --min-qa-rows 50 --min-qa-per-label 8 --require-qa-source --require-validated --no-dry-run`
  - `uv run python -m nlp_term.validators --seed-data --data-dir data`
  - `uv run python -m compileall src\nlp_term\prepare src\nlp_term\validators.py`
  - `uv run ruff check src\nlp_term\prepare src\nlp_term\validators.py`
- artifacts_to_update:
  - `src/nlp_term/prepare/qa_data.py`
  - `src/nlp_term/prepare/parsers.py`
  - `src/nlp_term/prepare/from_sources.py`
  - `src/nlp_term/validators.py`
  - `data/knowledge_seed.json`
  - `data/qa_seed.json`
  - `data/source_parse_failures.json`
  - `docs/pre_colab_progress.md`
  - `docs/pre_colab_failure_log.md`
- failure_log_entry_required: yes
- next_owner: Source/Data Steward
- handoff_path: `docs/meetings/phase-2.2-qa-data-2026-06-06-handoff.md`
- closed_at: `2026-06-06`
- outcome: final regenerated data has 15 knowledge docs, 50 QA rows, 10 QA rows per label, zero page-chrome scan hits, and all-row Source/Data critic `PASS`
