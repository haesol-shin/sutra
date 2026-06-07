# Goal 2.3 Step 3 To Step 4 Meeting

작성일: 2026-06-07

## Meeting ID

`goal-2.3-step-03-to-04-2026-06-07`

## Roles Present

- Facilitator/Planner
- Source/Data Steward
- Runtime/Architecture Engineer
- Evaluation/Validator Engineer
- Red-Team Critic

## Round Summary

Facilitator/Planner:

- Task 1 diagnosis is now sufficiently separated for the current goal.
- Proceed to Task 2 answer evaluation because naturalness and grounding are still unmeasured.

Source/Data Steward:

- Task 2 evaluator must bind answers to `data/gold/task2_fact_gold.json`.
- Fact coverage should be reported separately from source hint and naturalness.

Runtime/Architecture Engineer:

- Reuse `nlp_term.chat.batch` and the existing deterministic backend first.
- Do not introduce external LLM API evaluation.

Evaluation/Validator Engineer:

- The artifact must use `dataset_origin=task2_gold` and `claim_level=qualitative_check`.
- `must_not_claim` violations should be deterministic string checks in this step.

Red-Team Critic:

- Do not score llama if deterministic fallback is used.
- Naturalness heuristics are only a precheck and must not be presented as human evaluation.

## Decision

- selected_option: `proceed`
- status: `closed`
- next_owner: `Evaluation/Validator Engineer`

## Commands To Run Next

```powershell
uv run pytest tests/test_task2_answer_eval_artifact.py tests/test_chat_provenance.py tests/test_gold_contracts.py
uv run python -m nlp_term.chat.evaluate_gold --gold data/gold/task2_answer_eval_gold.json --facts data/gold/task2_fact_gold.json --knowledge data/knowledge_seed.json --output model/metrics/task2_gold_answer_eval.json --backend deterministic
uv run ruff check src tests
```
