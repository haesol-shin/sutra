# Goal 2.3 Step 6 Evidence

작성일: 2026-06-07

## Meeting ID

`goal-2.3-step-06-to-07-2026-06-07`

## Transition

- from_state: `step-06-retrieval-bottleneck-diagnosis`
- to_state: `step-07-next-data-expansion-priority-report`
- trigger_type: `mandatory_step_transition`
- verdict_before_transition: `pass_no_reject`

## Evidence Packet

- Step 6 commit: `9cd71f4 test: add retrieval bottleneck diagnosis`
- Diagnosis module: `src/nlp_term/retrieve/diagnose.py`
- Test: `tests/test_retrieval_bottleneck_report.py`
- Evidence: `docs/evidence/retrieval-bottleneck-diagnosis-2026-06-07.json`
- Local ignored metrics: `model/metrics/retrieval_bottleneck_diagnosis.json`

## Commands Reviewed

```powershell
uv run pytest tests/test_retrieval_bottleneck_report.py tests/test_retrieval_diagnostics.py
uv run python -m nlp_term.retrieve.diagnose --facts data/gold/task2_fact_gold.json --knowledge data/knowledge_seed.json --output model/metrics/retrieval_bottleneck_diagnosis.json
uv run python -m nlp_term.validators --metric-claim model/metrics/retrieval_bottleneck_diagnosis.json --input data/gold/task2_fact_gold.json --require-dataset-origin task2_gold --require-claim-level sanity
uv run ruff check src tests
```

## Results

- Task 2 fact gold count: `25`
- current knowledge doc count: `53`
- fact-probe hit@1: `0.60`
- fact-probe hit@3: `1.0`
- source coverage gap count: `0`
- ranking failure count: `0`
- weakest top1 label: label `2`, hit@1 `0.4`
- no final RAG performance claim was made
