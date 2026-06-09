# Project State

Last updated: 2026-06-09

This file is the first project memory document to read in a new session. It owns the current project direction. Historical plans and reports are useful only when `docs/doc_index.md` says they are current or relevant.

## Current Task Focus

- Task 1: keep the classifier working, but do not let Task 1 routing over-control Task 2 generation.
- Task 2: simplify the active Qwen evidence path.
- Task 3: optional; do not prioritize tool-call or runtime fetch until Task 2 is stable.

## Active Direction

Sutra package direction:
- The project is shifting toward `Sutra`: a lightweight local RAG runtime plus llama.cpp server client.
- `src/sutra/` is the new package-first implementation surface. Keep it flat for v1: `service.py`, `models.py`, `config.py`, `documents.py`, `retrieval.py`, `prompts.py`, `llama.py`, `cli.py`, `errors.py`.
- CNU is an external workspace example, not a core package project. See `examples/cnu-campus/sutra.toml`.
- Read `docs/sutra_architecture.md` before changing Sutra package, workspace, API/UI, or llama-server boundaries.

Active direction doc:
- `docs/task2_simplification_direction_2026_06_09.md`

Current implementation direction:
- Qwen should receive clean, official, relevant evidence.
- The active Task 2 path should stay simple: retrieve evidence -> build context -> prompt Qwen -> answer with trace.
- Keep useful source collection, explicit structured rows, plain chunks, evidence context, Qwen backend, and active probe runners.
- Do not restart the implementation from scratch unless the user explicitly requests it.
- Generation-blocking sufficiency and validation gates have been removed from the normal Task 2 path; evidence absence remains the minimal pre-generation block.
- Retrieval ranking no longer calls the Task 1 classifier internally.
- Task 2 route/domain should be demoted further: labels may be weak hints, but they should not override textual relevance or prevent Qwen from seeing useful evidence.
- `min_top_score` is not used as a generation or evidence-selection gate. Keep score values for trace/debugging unless an ablation proves benefit.
- Label hints have been removed from active retrieval scoring.
- Alias handling should support search/normalization, not separate priority boosting unless measured later.
- Temporal handling should stay in prompt context with exact current date/resolved date expressions; avoid temporal retrieval gates except source-native ordering such as notice posted dates.
- Evidence pack size is fixed at 8 for the active Task 2 path; do not vary it by temporal type unless a later ablation proves benefit.
- Qwen prompt rules now carry the relevance policy: prefer directly related evidence, prefer matching date/place/department, avoid asserting facts when requested and evidence dates differ, and explain limits naturally when evidence is insufficient.
- Retrieval ordering is owned by `rank_docs`; the Task 2 harness should preserve ranker order instead of re-sorting by score.
- Bare latest-notice questions use notice posted date as the primary ordering signal. Topic-specific latest-notice questions keep textual relevance first and use posted date only as a secondary signal.
- Graduation prose is no longer promoted into structured rows.
- Source chunks are plain recursive/plain-window chunks without confidence labels.

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

- data: fix the remaining evidence coverage gaps before adding more runtime policy. Public probe 01 still lacks a general graduation-credit source, and public probes 08/13 correctly expose missing next-week dining data.
- experiment: after adding the missing source coverage, rerun the 14 public probes, selected 39-set probes, and Qwen public probe with the same fixed evidence-pack path.

## Required Reading For Next Session

1. `docs/project_state.md`
2. `docs/doc_index.md`
3. `docs/term_project_requirements.md`
4. `docs/task2_simplification_direction_2026_06_09.md`
