# Goal 2.3 Step 2 Evidence

작성일: 2026-06-07

## Meeting ID

`goal-2.3-step-02-to-03-2026-06-07`

## Transition

- from_state: `step-02-task1-gold-error-analysis`
- to_state: `step-03-task1-improvement-candidate-separation`
- trigger_type: `mandatory_step_transition`
- verdict_before_transition: `pass_no_reject`

## Evidence Packet

- Step 2 commit: `03ebb28 test: add task1 gold error analysis`
- Durable evidence: `docs/evidence/task1-gold-error-analysis-2026-06-07.json`
- Local ignored artifact: `model/metrics/task1_gold_error_analysis.json`

## Metrics Reviewed

- row_count: `50`
- macro_f1: `0.8385026737967914`
- weighted_f1: `0.8385026737967913`
- error_count: `8`
- false_negative_counts: `{0: 0, 1: 3, 2: 2, 3: 0, 4: 3}`
- false_positive_counts: `{0: 2, 1: 0, 2: 4, 3: 2, 4: 0}`
- per_difficulty_failure_counts: `{natural: 5, short: 2, boundary: 1}`

## Commands Reviewed

```powershell
uv run pytest tests/test_task1_gold_error_report.py tests/test_classify_gold_eval.py tests/test_gold_contracts.py
uv run python -m nlp_term.classify.evaluate_gold --input data/gold/task1_human_gold.json --output model/metrics/gold_classifier_metrics.json
uv run python -m nlp_term.classify.analyze_gold_errors --input data/gold/task1_human_gold.json --output model/metrics/task1_gold_error_analysis.json
uv run python -m nlp_term.validators --metric-claim model/metrics/task1_gold_error_analysis.json --input data/gold/task1_human_gold.json --require-dataset-origin human_gold --require-claim-level heldout_eval
uv run ruff check src tests
```

## Results

- tests: pass
- metric-claim validator: pass
- lint: pass
- claim boundary: diagnostic only, not final generalization evidence
