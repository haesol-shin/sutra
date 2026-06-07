# Goal 2.3 Step 1 To Step 2 Meeting

작성일: 2026-06-07

## Meeting ID

`goal-2.3-step-01-to-02-2026-06-07`

## Roles Present

- Facilitator/Planner
- Source/Data Steward
- Runtime/Architecture Engineer
- Evaluation/Validator Engineer
- Red-Team Critic

## Round Summary

Facilitator/Planner:

- Step 1 was intentionally small and should remain separate from evaluation code.
- Proceed to Task 1 gold error analysis with no classifier tuning.

Source/Data Steward:

- Gold data must stay evaluation-only.
- No generated training rows may be derived from gold questions in Step 2.

Runtime/Architecture Engineer:

- Step 2 should reuse the existing classifier prediction path instead of introducing a new runtime path.
- The local ignored metrics directory may be used, but durable summaries must live under `docs/evidence/`.

Evaluation/Validator Engineer:

- The Step 2 artifact must include input checksum, row count, per-label confusion, per-difficulty failures, and complete error rows.
- The metric claim boundary must remain `dataset_origin=human_gold` and `claim_level=heldout_eval`.

Red-Team Critic:

- Do not tune to the 50 gold rows.
- Do not report the 50-row gold metric as final generalization performance.

## Decision

- selected_option: `proceed`
- status: `closed`
- next_owner: `Evaluation/Validator Engineer`

## Commands To Run Next

```powershell
uv run pytest tests/test_task1_gold_error_report.py tests/test_classify_gold_eval.py tests/test_gold_contracts.py
uv run python -m nlp_term.classify.analyze_gold_errors --input data/gold/task1_human_gold.json --output model/metrics/task1_gold_error_analysis.json
uv run ruff check src tests
```
