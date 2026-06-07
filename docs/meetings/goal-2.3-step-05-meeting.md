# Goal 2.3 Step 5 To Step 6 Meeting

작성일: 2026-06-07

## Meeting ID

`goal-2.3-step-05-to-06-2026-06-07`

## Roles Present

- Facilitator/Planner
- Source/Data Steward
- Runtime/Architecture Engineer
- Evaluation/Validator Engineer
- Red-Team Critic

## Round Summary

Facilitator/Planner:

- Backend separation is now explicit enough for the current goal.
- Move to retrieval diagnosis because missing facts and source hints depend on retrieved evidence.

Source/Data Steward:

- Current knowledge has too few source documents to represent graduation, curriculum, notices, meals, and shuttle coverage.
- Diagnose which gold facts are missing because retrieval misses existing docs versus because source coverage is absent.

Runtime/Architecture Engineer:

- Keep retrieval diagnosis deterministic and fast.
- Do not introduce embeddings or reranking inside this step; first measure current keyword/BM25-like rank behavior.

Evaluation/Validator Engineer:

- Report hit@1, hit@3, missing source-doc IDs, and label-level misses.
- Keep the claim boundary as retrieval diagnostics only.

Red-Team Critic:

- Do not treat high answer fact recall as proof that retrieval is good.
- A fact can be counted if the expected source doc appears in top 3, while the answer may still be awkward or omit URLs.

## Decision

- selected_option: `proceed`
- status: `closed`
- next_owner: `Source/Data Steward`

## Commands To Run Next

```powershell
uv run pytest tests/test_retrieval_bottleneck_report.py tests/test_retrieval_diagnostics.py
uv run python -m nlp_term.retrieve.diagnose --facts data/gold/task2_fact_gold.json --knowledge data/knowledge_seed.json --output model/metrics/retrieval_bottleneck_diagnosis.json
uv run ruff check src tests
```
