# Decision Log

This file records short rationale for important project decisions. It is append-only history and does not override `docs/project_state.md`.

## 2026-06-09

Type: docs
Decision: Do not restart Task 2 from scratch; simplify the active path from the current codebase.
Reason: Existing source collection, parsing, Qwen runtime, and probe assets are useful; the main issue is policy-heavy front-end logic.
Supersedes: Tool-use and single-tool experiment directions as active runtime plans.
Links: `docs/task2_simplification_direction_2026_06_09.md`

## 2026-06-09

Type: docs
Decision: Use `project_state.md` plus `doc_index.md` as the future-session memory router.
Reason: Chat history and old plans are too large and can conflict; future sessions need a small current-truth entrypoint.
Supersedes: Reading old plan files as implicit current direction.
Links: `docs/project_state.md`, `docs/doc_index.md`

## 2026-06-09

Type: docs
Decision: Mark stale or conflicting plans as `Do Not Execute` until explicitly reactivated.
Reason: Several older plans contain checklist-style implementation instructions that conflict with the current simplification direction.
Supersedes: Treating all files under `docs/superpowers/plans/` as executable.
Links: `docs/doc_index.md`

## 2026-06-09

Type: refactor
Decision: Simplify the Task 2 active path so retrieved evidence is passed to Qwen unless no evidence exists.
Reason: Policy-heavy sufficiency, answer-kind, temporal, and validator gates were suppressing or replacing generated answers before Qwen could use the evidence.
Supersedes: Harness behavior that fail-closed on current-fact, wrong-domain, temporal mismatch, or validator warning cases.
Links: `docs/task2_simplification_direction_2026_06_09.md`, `src/nlp_term/chat/orchestrator.py`

## 2026-06-09

Type: refactor
Decision: Treat the Task 1 route label as a Task 2 retrieval ordering preference instead of a strict evidence filter.
Reason: A strict route filter can erase useful evidence when Task 1 misclassifies an otherwise answerable question.
Consequence: Sufficiently scoring evidence is kept across labels, route-matching evidence is sorted first, and selected evidence remains visible in trace.
Links: `docs/task2_simplification_direction_2026_06_09.md`, `src/nlp_term/chat/orchestrator.py`

## 2026-06-09

Type: refactor
Decision: Adopt the next Task 2 retrieval simplification plan: demote route preference, remove label hints from active scoring, make `min_top_score` diagnostic only, keep aliases as search text, and keep temporal handling in prompt context.
Reason: The current project goal is simple evidence delivery to Qwen. Prior probe runs and reviewer analysis showed that score gates and routing-like boosts can suppress useful evidence or make behavior harder to reason about without proven isolated gains.
Consequence: Future retrieval changes should be small ablations with probe checks, starting with removing score-based fail-closed behavior from evidence pack selection.
Links: `docs/task2_simplification_direction_2026_06_09.md`, `docs/project_state.md`

## 2026-06-09

Type: refactor
Decision: Use a fixed Task 2 evidence pack size of 8 and remove score-positive and temporal pack-size selection rules.
Reason: The project direction is to give Qwen enough clean evidence and let the prompt handle relevance. Prior checks showed routing-like gates and arbitrary score thresholds made behavior harder to reason about without a measured benefit.
Consequence: Retrieved evidence is sorted by diagnostic score and passed through up to the fixed pack size. Date mismatch handling moves to prompt instructions and Qwen generation behavior.
Links: `src/nlp_term/chat/orchestrator.py`, `src/nlp_term/chat/prompts.py`, `docs/task2_simplification_direction_2026_06_09.md`

## 2026-06-09

Type: fix
Decision: Centralize retrieval ordering in `rank_docs` and preserve that order in the Task 2 harness.
Reason: Re-sorting retrieved evidence by score inside the harness undid source-native latest-notice ordering and made the behavior harder to reason about.
Consequence: Bare latest-notice queries put posted date first, topic-specific latest-notice queries put textual relevance first, and the harness no longer performs a second score sort.
Links: `src/nlp_term/retrieve/rank.py`, `src/nlp_term/chat/orchestrator.py`
