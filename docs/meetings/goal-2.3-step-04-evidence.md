# Goal 2.3 Step 4 Evidence

작성일: 2026-06-07

## Meeting ID

`goal-2.3-step-04-to-05-2026-06-07`

## Transition

- from_state: `step-04-task2-gold-answer-evaluator`
- to_state: `step-05-deterministic-llama-backend-comparison`
- trigger_type: `mandatory_step_transition`
- verdict_before_transition: `pass_no_reject`

## Evidence Packet

- Step 4 commit: `d63ea2e test: add task2 gold answer evaluation`
- Evaluator: `src/nlp_term/chat/evaluate_gold.py`
- Test: `tests/test_task2_answer_eval_artifact.py`
- Evidence: `docs/evidence/task2-gold-answer-eval-2026-06-07.json`
- Local ignored metrics: `model/metrics/task2_gold_answer_eval.json`

## Commands Reviewed

```powershell
uv run pytest tests/test_task2_answer_eval_artifact.py tests/test_chat_provenance.py tests/test_gold_contracts.py
uv run python -m nlp_term.chat.evaluate_gold --gold data/gold/task2_answer_eval_gold.json --facts data/gold/task2_fact_gold.json --knowledge data/knowledge_seed.json --output model/metrics/task2_gold_answer_eval.json --backend deterministic
uv run python -m nlp_term.validators --metric-claim model/metrics/task2_gold_answer_eval.json --input data/gold/task2_answer_eval_gold.json --require-dataset-origin task2_gold --require-claim-level qualitative_check
uv run ruff check src tests
```

## Results

- 25 Task 2 gold answer prompts were evaluated.
- deterministic backend fact recall: `0.80`
- forbidden claim violations: `0`
- source hint rate: `0.76`
- naturalness heuristic pass rate: `0.24`
- primary naturalness failure: internal document/source IDs exposed in 19 answers
- no final chatbot quality claim was made
