# Goal 2.3 Step 5 Evidence

작성일: 2026-06-07

## Meeting ID

`goal-2.3-step-05-to-06-2026-06-07`

## Transition

- from_state: `step-05-deterministic-llama-backend-comparison`
- to_state: `step-06-retrieval-bottleneck-diagnosis`
- trigger_type: `mandatory_step_transition`
- verdict_before_transition: `pass_no_reject`

## Evidence Packet

- Step 5 commit: `57f2baf test: separate task2 backend evidence`
- Comparison module: `src/nlp_term/chat/compare_backends.py`
- Test: `tests/test_backend_evidence_separation.py`
- Evidence: `docs/evidence/task2-backend-comparison-2026-06-07.json`
- Local ignored metrics: `model/metrics/task2_backend_comparison.json`

## Commands Reviewed

```powershell
uv run pytest tests/test_backend_evidence_separation.py tests/test_task2_answer_eval_artifact.py tests/test_chat_provenance.py
uv run python -m nlp_term.chat.compare_backends --gold data/gold/task2_answer_eval_gold.json --facts data/gold/task2_fact_gold.json --knowledge data/knowledge_seed.json --output model/metrics/task2_backend_comparison.json --llama-limit 3
uv run python -m nlp_term.validators --metric-claim model/metrics/task2_backend_comparison.json --input data/gold/task2_answer_eval_gold.json --require-dataset-origin task2_gold --require-claim-level qualitative_check
uv run ruff check src tests
```

## Results

- deterministic backend evaluated all 25 Task 2 gold rows.
- llama backend evaluated 3 Task 2 gold rows.
- llama backend was available and no deterministic fallback was counted as llama.
- deterministic naturalness heuristic pass rate: `0.24`
- llama sample naturalness heuristic pass rate: `1.0`
- deterministic source hint rate: `0.76`
- llama sample source hint rate: `0.0`
- final Task 2 quality was not claimed.
