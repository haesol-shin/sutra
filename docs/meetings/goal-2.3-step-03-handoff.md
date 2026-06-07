# Goal 2.3 Step 3 To Step 4 Handoff

작성일: 2026-06-07

## Handoff

Proceed from Task 1 improvement-candidate separation to Task 2 gold answer evaluation.

## Required Step 4 Deliverables

- `src/nlp_term/chat/evaluate_gold.py`
- `tests/test_task2_answer_eval_artifact.py`
- `docs/evidence/task2-gold-answer-eval-2026-06-07.json`
- local ignored artifact: `model/metrics/task2_gold_answer_eval.json`

## Guardrails

- Do not call an external LLM API.
- Do not use LLM judge scoring.
- Keep deterministic and llama backend claims separate.
- Naturalness score is a heuristic precheck only.
- Any `must_not_claim` exact match is a violation.

## Done When

- all 25 Task 2 gold prompts are evaluated
- expected fact ids are checked
- forbidden claim violations are counted
- source hint and naturalness heuristic rates are recorded
- no final chatbot quality claim is made
