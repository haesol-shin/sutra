# Goal 2.3 Step 6 To Step 7 Meeting

작성일: 2026-06-07

## Meeting ID

`goal-2.3-step-06-to-07-2026-06-07`

## Roles Present

- Facilitator/Planner
- Source/Data Steward
- Runtime/Architecture Engineer
- Evaluation/Validator Engineer
- Red-Team Critic

## Round Summary

Facilitator/Planner:

- The final step should convert the diagnostics into a concrete expansion order.
- The report should be executable later without deciding every crawler detail now.

Source/Data Steward:

- Data volume and scope are still the main risk.
- Graduation requirements and curriculum PDFs/HWP should be prioritized because the user explicitly flagged them and Task 1 error analysis also points there.

Runtime/Architecture Engineer:

- Keep the next plan minimal: source inventory, parser target, validator gate, and expected metric movement.
- Do not add embeddings/rerankers before source expansion creates enough meaningful documents.

Evaluation/Validator Engineer:

- Each priority should have a measurable acceptance gate.
- Include current evidence numbers so future improvements can be compared against this baseline.

Red-Team Critic:

- Current high scores are small-set diagnostics and can be misleading.
- The report must say that current retrieval probes use fact-like text, not realistic user phrasing.

## Decision

- selected_option: `proceed`
- status: `closed`
- next_owner: `Facilitator/Planner`

## Commands To Run Next

```powershell
uv run pytest tests/test_data_expansion_priority_report.py tests/test_meeting_evidence.py
rg -n "Priority 1|졸업|PDF|HWP|acceptance gate|baseline" docs/next_data_expansion_priorities.md
uv run ruff check src tests
```
