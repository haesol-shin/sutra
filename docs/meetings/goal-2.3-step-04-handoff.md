# Goal 2.3 Step 4 To Step 5 Handoff

작성일: 2026-06-07

## Handoff

Proceed from Task 2 deterministic answer evaluation to backend comparison.

## Required Step 5 Deliverables

- `src/nlp_term/chat/compare_backends.py`
- `tests/test_backend_evidence_separation.py`
- `docs/evidence/task2-backend-comparison-2026-06-07.json`
- local ignored artifact: `model/metrics/task2_backend_comparison.json`

## Guardrails

- Do not call an external LLM API.
- Do not mask llama unavailability with deterministic fallback.
- Do not claim llama quality unless a llama backend actually ran.
- Keep backend quality and retrieval quality separated.
- Naturalness heuristics remain a precheck only.

## Done When

- deterministic evidence is recorded
- llama evidence is either recorded or explicitly marked unavailable
- fallback status is visible per backend
- Task 2 gold metrics can be compared without mixing backend outputs
