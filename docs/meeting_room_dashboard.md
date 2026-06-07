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

## goal-2.3-step-01-to-02-2026-06-07

- meeting_id: `goal-2.3-step-01-to-02-2026-06-07`
- opened_at: `2026-06-07`
- trigger_type: `mandatory_step_transition`
- phase: `Goal 2.3 Evaluation Diagnostics`
- step_id: `step-01-to-step-02`
- verdict_before_transition: `pass_no_reject`
- roles_present:
  - Facilitator/Planner
  - Source/Data Steward
  - Runtime/Architecture Engineer
  - Evaluation/Validator Engineer
  - Red-Team Critic
- status: `closed`
- selected_option: proceed to Task 1 gold error analysis
- evidence_path: `docs/meetings/goal-2.3-step-01-evidence.md`
- meeting_path: `docs/meetings/goal-2.3-step-01-meeting.md`
- handoff_path: `docs/meetings/goal-2.3-step-01-handoff.md`
- commands_to_run:
  - `uv run pytest tests/test_task1_gold_error_report.py tests/test_classify_gold_eval.py tests/test_gold_contracts.py`
  - `uv run python -m nlp_term.classify.analyze_gold_errors --input data/gold/task1_human_gold.json --output model/metrics/task1_gold_error_analysis.json`
  - `uv run ruff check src tests`
- closed_at: `2026-06-07`

## goal-2.3-step-02-to-03-2026-06-07

- meeting_id: `goal-2.3-step-02-to-03-2026-06-07`
- opened_at: `2026-06-07`
- trigger_type: `mandatory_step_transition`
- phase: `Goal 2.3 Evaluation Diagnostics`
- step_id: `step-02-to-step-03`
- verdict_before_transition: `pass_no_reject`
- roles_present:
  - Facilitator/Planner
  - Source/Data Steward
  - Runtime/Architecture Engineer
  - Evaluation/Validator Engineer
  - Red-Team Critic
- status: `closed`
- selected_option: proceed to Task 1 improvement-candidate separation
- evidence_path: `docs/meetings/goal-2.3-step-02-evidence.md`
- meeting_path: `docs/meetings/goal-2.3-step-02-meeting.md`
- handoff_path: `docs/meetings/goal-2.3-step-02-handoff.md`
- commands_to_run:
  - `rg -n "label 2|학사일정|no model improvement|data coverage|boundary|classifier" docs/task1_error_improvement_candidates.md`
  - `uv run ruff check src tests`
- closed_at: `2026-06-07`

## goal-2.3-step-03-to-04-2026-06-07

- meeting_id: `goal-2.3-step-03-to-04-2026-06-07`
- opened_at: `2026-06-07`
- trigger_type: `mandatory_step_transition`
- phase: `Goal 2.3 Evaluation Diagnostics`
- step_id: `step-03-to-step-04`
- verdict_before_transition: `pass_no_reject`
- roles_present:
  - Facilitator/Planner
  - Source/Data Steward
  - Runtime/Architecture Engineer
  - Evaluation/Validator Engineer
  - Red-Team Critic
- status: `closed`
- selected_option: proceed to Task 2 gold answer evaluator
- evidence_path: `docs/meetings/goal-2.3-step-03-evidence.md`
- meeting_path: `docs/meetings/goal-2.3-step-03-meeting.md`
- handoff_path: `docs/meetings/goal-2.3-step-03-handoff.md`
- commands_to_run:
  - `uv run pytest tests/test_task2_answer_eval_artifact.py tests/test_chat_provenance.py tests/test_gold_contracts.py`
  - `uv run python -m nlp_term.chat.evaluate_gold --gold data/gold/task2_answer_eval_gold.json --facts data/gold/task2_fact_gold.json --knowledge data/knowledge_seed.json --output model/metrics/task2_gold_answer_eval.json --backend deterministic`
  - `uv run ruff check src tests`
- closed_at: `2026-06-07`

## goal-2.3-step-04-to-05-2026-06-07

- meeting_id: `goal-2.3-step-04-to-05-2026-06-07`
- opened_at: `2026-06-07`
- trigger_type: `mandatory_step_transition`
- phase: `Goal 2.3 Evaluation Diagnostics`
- step_id: `step-04-to-step-05`
- verdict_before_transition: `pass_no_reject`
- roles_present:
  - Facilitator/Planner
  - Source/Data Steward
  - Runtime/Architecture Engineer
  - Evaluation/Validator Engineer
  - Red-Team Critic
- status: `closed`
- selected_option: proceed to deterministic/llama backend comparison
- evidence_path: `docs/meetings/goal-2.3-step-04-evidence.md`
- meeting_path: `docs/meetings/goal-2.3-step-04-meeting.md`
- handoff_path: `docs/meetings/goal-2.3-step-04-handoff.md`
- commands_to_run:
  - `uv run pytest tests/test_backend_evidence_separation.py tests/test_task2_answer_eval_artifact.py tests/test_chat_provenance.py`
  - `uv run python -m nlp_term.chat.compare_backends --gold data/gold/task2_answer_eval_gold.json --facts data/gold/task2_fact_gold.json --knowledge data/knowledge_seed.json --output model/metrics/task2_backend_comparison.json`
  - `uv run ruff check src tests`
- closed_at: `2026-06-07`
