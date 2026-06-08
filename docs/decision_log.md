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
