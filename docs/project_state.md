# Project State

Last updated: 2026-06-09

This file is the first project memory document to read in a new session. It owns the current project direction. Historical plans and reports are useful only when `docs/doc_index.md` says they are current or relevant.

## Current Task Focus

- Task 1: keep the classifier working, but do not let Task 1 routing over-control Task 2 generation.
- Task 2: simplify the active Qwen evidence path.
- Task 3: optional; do not prioritize tool-call or runtime fetch until Task 2 is stable.

## Active Direction

Active direction doc:
- `docs/task2_simplification_direction_2026_06_09.md`

Current implementation direction:
- Qwen should receive clean, official, relevant evidence.
- The active Task 2 path should stay simple: retrieve evidence -> build context -> prompt Qwen -> answer with trace.
- Keep useful source collection, explicit structured rows, plain chunks, evidence context, Qwen backend, and active probe runners.
- Do not restart the implementation from scratch unless the user explicitly requests it.

## Do Not Follow Without Review

- Full tool-call agent runtime plans.
- Single-tool experiment runtime plans.
- Mechanical answer-kind routing that blocks generation.
- Temporal confidence or retrieval-policy classifiers.
- Evidence sufficiency policy that blocks answers beyond empty or no-evidence cases.
- Graduation prose-to-structured-row extraction.
- Chunk confidence labels or keyword-derived quality labels.
- Old plans marked `Do Not Execute` in `docs/doc_index.md`.

## Next Action

- docs: keep `AGENTS.md`, `docs/project_state.md`, `docs/doc_index.md`, and `docs/decision_log.md` synchronized when the user makes a durable project-direction decision.

## Required Reading For Next Session

1. `docs/project_state.md`
2. `docs/doc_index.md`
3. `docs/term_project_requirements.md`
4. `docs/task2_simplification_direction_2026_06_09.md`
