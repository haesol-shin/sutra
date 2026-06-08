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
