# Goal 2.3 Step 2 To Step 3 Handoff

작성일: 2026-06-07

## Handoff

Proceed from Task 1 gold error observation to improvement-candidate separation.

## Required Step 3 Deliverables

- `docs/task1_error_improvement_candidates.md`
- optional update to `docs/evidence/task1-gold-error-analysis-2026-06-07.json` only if the evidence needs a small candidate pointer

## Guardrails

- Do not change classifier code.
- Do not change gold data.
- Do not create training rows from gold questions.
- Every observed error must have exactly one primary category.
- Rejected candidates must be documented when they risk gold overfitting.

## Done When

- Each of the eight observed errors is categorized.
- Label 2 weakness is explained.
- The report proposes the smallest next experiment without claiming improvement.
