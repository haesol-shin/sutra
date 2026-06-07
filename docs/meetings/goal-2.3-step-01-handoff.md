# Goal 2.3 Step 1 To Step 2 Handoff

작성일: 2026-06-07

## Handoff

Proceed from `.omc/` hygiene to Task 1 gold error analysis.

## Required Step 2 Deliverables

- `src/nlp_term/classify/analyze_gold_errors.py`
- `tests/test_task1_gold_error_report.py`
- `docs/evidence/task1-gold-error-analysis-2026-06-07.json`
- local ignored artifact: `model/metrics/task1_gold_error_analysis.json`

## Guardrails

- Do not change gold labels.
- Do not change classifier training data.
- Do not tune model behavior in Step 2.
- Use the current prediction path and report observed errors only.
- Keep small-gold wording bounded: not final generalization evidence.

## Done When

- Step 2 tests pass.
- Error report covers every mismatch.
- Durable evidence records checksum and current metric boundary.
- Step 2 commit is created.
