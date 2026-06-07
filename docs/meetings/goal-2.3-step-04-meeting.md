# Goal 2.3 Step 4 To Step 5 Meeting

작성일: 2026-06-07

## Meeting ID

`goal-2.3-step-04-to-05-2026-06-07`

## Roles Present

- Facilitator/Planner
- Source/Data Steward
- Runtime/Architecture Engineer
- Evaluation/Validator Engineer
- Red-Team Critic

## Round Summary

Facilitator/Planner:

- Step 4 now gives a concrete Task 2 quality precheck.
- The next step should separate answer backend behavior from retrieval behavior.

Source/Data Steward:

- Current fact recall is useful, but it depends on a small 25-row gold set.
- Missing facts should not trigger data edits until backend comparison confirms whether the issue is answer generation or retrieval coverage.

Runtime/Architecture Engineer:

- Compare deterministic and llama modes as separate evidence lanes.
- If the llama model is unavailable, record `unavailable` rather than using deterministic output as a substitute.

Evaluation/Validator Engineer:

- Preserve `task2_gold` and `qualitative_check` metadata.
- Backend comparison must expose `backend_requested`, `backend_used`, `fallback_used`, and availability status.

Red-Team Critic:

- The naturalness pass rate is low because internal IDs are exposed.
- This is a current-system defect signal, not a reason to claim llama is better before measuring it.

## Decision

- selected_option: `proceed`
- status: `closed`
- next_owner: `Runtime/Architecture Engineer`

## Commands To Run Next

```powershell
uv run pytest tests/test_backend_evidence_separation.py tests/test_task2_answer_eval_artifact.py tests/test_chat_provenance.py
uv run python -m nlp_term.chat.compare_backends --gold data/gold/task2_answer_eval_gold.json --facts data/gold/task2_fact_gold.json --knowledge data/knowledge_seed.json --output model/metrics/task2_backend_comparison.json
uv run ruff check src tests
```
