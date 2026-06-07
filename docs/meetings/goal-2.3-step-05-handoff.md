# Goal 2.3 Step 5 To Step 6 Handoff

작성일: 2026-06-07

## Handoff

Proceed from backend evidence separation to retrieval bottleneck diagnosis.

## Required Step 6 Deliverables

- `src/nlp_term/retrieve/diagnose.py`
- `tests/test_retrieval_bottleneck_report.py`
- `docs/evidence/retrieval-bottleneck-diagnosis-2026-06-07.json`
- local ignored artifact: `model/metrics/retrieval_bottleneck_diagnosis.json`

## Guardrails

- Do not introduce a new retrieval backend in this step.
- Do not claim embedding RAG performance.
- Do not alter knowledge or gold data.
- Separate source coverage gaps from ranking failures.

## Done When

- every Task 2 fact has a retrieval probe
- hit@1 and hit@3 are reported
- missing source-doc IDs are listed
- label/domain-level bottlenecks are summarized
