# Project Memory Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make future Codex sessions load the current project direction without rereading the whole chat history or accidentally following stale plans.

**Architecture:** `AGENTS.md` acts only as the session router. `docs/project_state.md` owns the current truth, `docs/doc_index.md` owns document status, and `docs/decision_log.md` records short append-only rationale. If old docs conflict, `project_state.md` plus `doc_index.md` win over stale in-document claims.

**Tech Stack:** Markdown documentation, existing repository docs, no runtime dependency changes.

---

## Critic-Stabilized Rules

The critic rejected the first draft because it could duplicate "current truth" across multiple documents. This plan fixes that with explicit ownership and conflict rules.

- `docs/project_state.md` is the only current-state snapshot.
- `docs/doc_index.md` is the only document status registry.
- `docs/decision_log.md` is append-only history and never owns current state.
- `docs/term_project_requirements.md` remains the assignment authority, not the implementation direction authority.
- Old plans under `docs/superpowers/plans/` must not be executed unless `docs/doc_index.md` marks them `Current`.
- If documents conflict, use `docs/project_state.md` and `docs/doc_index.md` first.

---

## File Structure

- Create `docs/project_state.md`
  - Future-session first screen.
  - Contains only living decisions, current focus, active direction doc, next action, and do-not-follow list.
- Create `docs/doc_index.md`
  - Registry of important docs and status.
  - Owns status enum: `Current`, `Reference`, `Evidence`, `Historical`, `Superseded`, `Do Not Execute`.
- Create `docs/decision_log.md`
  - Append-only short decision records.
  - Provides rationale links but never overrides `project_state.md`.
- Modify `AGENTS.md`
  - Add a short "Session Bootstrap" section.
  - Do not paste long history into `AGENTS.md`.

---

## Templates

### `docs/project_state.md`

```markdown
# Project State

Last updated: YYYY-MM-DD

## Current Task Focus

- Task 1:
- Task 2:
- Task 3:

## Active Direction

Active direction doc:
- `docs/task2_simplification_direction_2026_06_09.md`

Current implementation direction:
- Qwen receives clean, official, relevant evidence.
- Active Task 2 path should stay simple: retrieve evidence -> build context -> prompt Qwen -> answer with trace.

## Do Not Follow Without Review

- Full tool-call agent runtime plans.
- Mechanical answer-kind routing that blocks generation.
- Temporal confidence or retrieval-policy classifiers.
- Graduation prose-to-structured-row extraction.
- Old plans marked `Do Not Execute` in `docs/doc_index.md`.

## Next Action

- [type]: concise next concrete action.

## Required Reading For Next Session

1. `docs/project_state.md`
2. `docs/doc_index.md`
3. `docs/term_project_requirements.md`
4. Active direction doc listed above
```

### `docs/doc_index.md`

```markdown
# Document Index

Status enum:
- `Current`: active direction or required current state.
- `Reference`: stable background information.
- `Evidence`: experiment result, audit, or raw finding.
- `Historical`: useful past context, not active instruction.
- `Superseded`: replaced by another document.
- `Do Not Execute`: old plan or experiment that must not be run unless reactivated.

| Document | Status | Purpose | Read When | Superseded By |
| --- | --- | --- | --- | --- |
| `docs/project_state.md` | Current | Current project state and next action | Every session start |  |
| `docs/term_project_requirements.md` | Reference | Assignment requirements | Before changing scope or evaluation behavior |  |
| `docs/task2_simplification_direction_2026_06_09.md` | Current | Current Task 2 simplification direction | Before Task 2/RAG/Qwen work |  |
| `docs/project_architecture_plan.md` | Historical | Earlier architecture baseline | Only for background | `docs/project_state.md` |
| `docs/superpowers/plans/2026-06-09-simple-evidence-units.md` | Do Not Execute | Earlier detailed plan needing revision | Only for historical reference | `docs/task2_simplification_direction_2026_06_09.md` |
```

### `docs/decision_log.md`

```markdown
# Decision Log

## YYYY-MM-DD

Type: docs|env|feat|fix|test|refactor|chore
Decision:
Reason:
Supersedes:
Links:
```

### `AGENTS.md` Session Bootstrap Section

```markdown
## Session Bootstrap

- Read `docs/project_state.md` first.
- Read `docs/doc_index.md` for document status.
- Read `docs/term_project_requirements.md` for assignment constraints.
- Read only task-specific docs marked `Current` or `Reference`.
- Do not execute old plans unless `docs/doc_index.md` marks them `Current`.
- If docs conflict, `docs/project_state.md` and `docs/doc_index.md` override old in-document "current" claims.
```

---

### Task 1: Create `docs/project_state.md`

**Files:**
- Create: `docs/project_state.md`

- [ ] **Step 1: Create the current-state snapshot**

Add this initial content:

```markdown
# Project State

Last updated: 2026-06-09

## Current Task Focus

- Task 1: keep classifier working, but do not let Task 1 routing over-control Task 2 generation.
- Task 2: simplify the active Qwen evidence path.
- Task 3: optional; do not prioritize tool-call/runtime fetch unless Task 2 is stable.

## Active Direction

Active direction doc:
- `docs/task2_simplification_direction_2026_06_09.md`

Current implementation direction:
- Qwen should receive clean, official, relevant evidence.
- The active Task 2 path should stay simple: retrieve evidence -> build context -> prompt Qwen -> answer with trace.
- Keep useful source collection, explicit structured rows, plain chunks, evidence context, Qwen backend, and active probe runners.

## Do Not Follow Without Review

- Full tool-call agent runtime plans.
- Single-tool experiment runtime plans.
- Mechanical answer-kind routing that blocks generation.
- Temporal confidence or retrieval-policy classifiers.
- Evidence sufficiency policy that blocks answers beyond empty/no-evidence cases.
- Graduation prose-to-structured-row extraction.
- Chunk confidence labels or keyword-derived quality labels.
- Old plans marked `Do Not Execute` in `docs/doc_index.md`.

## Next Action

- docs: create the memory-router docs and update `AGENTS.md`.

## Required Reading For Next Session

1. `docs/project_state.md`
2. `docs/doc_index.md`
3. `docs/term_project_requirements.md`
4. `docs/task2_simplification_direction_2026_06_09.md`
```

- [ ] **Step 2: Verify the file exists**

Run:

```powershell
Test-Path docs\project_state.md
```

Expected: `True`

---

### Task 2: Create `docs/doc_index.md`

**Files:**
- Create: `docs/doc_index.md`

- [ ] **Step 1: Create the document registry**

Add this initial content:

```markdown
# Document Index

Status enum:
- `Current`: active direction or required current state.
- `Reference`: stable background information.
- `Evidence`: experiment result, audit, or raw finding.
- `Historical`: useful past context, not active instruction.
- `Superseded`: replaced by another document.
- `Do Not Execute`: old plan or experiment that must not be run unless reactivated.

Conflict rule:
- If documents conflict, `docs/project_state.md` and this index override old in-document "current" claims.
- Do not execute old plans unless this index marks them `Current`.

| Document | Status | Purpose | Read When | Superseded By |
| --- | --- | --- | --- | --- |
| `docs/project_state.md` | Current | Current project state and next action | Every session start |  |
| `docs/doc_index.md` | Current | Document status registry | Every session start |  |
| `docs/term_project_requirements.md` | Reference | Assignment requirements | Before changing scope or evaluation behavior |  |
| `docs/task2_simplification_direction_2026_06_09.md` | Current | Current Task 2 simplification direction | Before Task 2/RAG/Qwen work |  |
| `docs/qwen_runtime.md` | Reference | Local Qwen runtime notes | Before model execution changes |  |
| `docs/project_architecture_plan.md` | Historical | Earlier architecture baseline | Only for background | `docs/project_state.md` |
| `docs/task2_task3_harness_architecture.md` | Historical | Earlier harness architecture | Only for background | `docs/task2_simplification_direction_2026_06_09.md` |
| `docs/superpowers/plans/2026-06-09-simple-evidence-units.md` | Do Not Execute | Earlier detailed plan needing revision | Only for historical reference | `docs/task2_simplification_direction_2026_06_09.md` |
```

- [ ] **Step 2: Verify critical statuses are present**

Run:

```powershell
Select-String -Path docs\doc_index.md -Pattern "Do Not Execute","task2_simplification_direction"
```

Expected: both patterns appear.

---

### Task 3: Create `docs/decision_log.md`

**Files:**
- Create: `docs/decision_log.md`

- [ ] **Step 1: Create the append-only decision log**

Add this initial content:

```markdown
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
```

- [ ] **Step 2: Verify the log states it is not current truth**

Run:

```powershell
Select-String -Path docs\decision_log.md -Pattern "does not override"
```

Expected: one matching line.

---

### Task 4: Update `AGENTS.md`

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Add session bootstrap after Current Scope**

Insert this section after `## Current Scope`:

```markdown
## Session Bootstrap

- Read `docs/project_state.md` first.
- Read `docs/doc_index.md` for document status.
- Read `docs/term_project_requirements.md` for assignment constraints.
- Read only task-specific docs marked `Current` or `Reference`.
- Do not execute old plans unless `docs/doc_index.md` marks them `Current`.
- If docs conflict, `docs/project_state.md` and `docs/doc_index.md` override old in-document "current" claims.
```

- [ ] **Step 2: Verify bootstrap was added**

Run:

```powershell
Select-String -Path AGENTS.md -Pattern "Session Bootstrap","project_state.md","doc_index.md"
```

Expected: all three patterns appear.

---

### Task 5: Verify The Memory Router

**Files:**
- Read: `AGENTS.md`
- Read: `docs/project_state.md`
- Read: `docs/doc_index.md`
- Read: `docs/decision_log.md`

- [ ] **Step 1: Check required files**

Run:

```powershell
Test-Path AGENTS.md; Test-Path docs\project_state.md; Test-Path docs\doc_index.md; Test-Path docs\decision_log.md
```

Expected: four `True` lines.

- [ ] **Step 2: Check conflict rules**

Run:

```powershell
Select-String -Path AGENTS.md,docs\doc_index.md -Pattern "If docs conflict","Do not execute old plans"
```

Expected: conflict and old-plan rules appear in both the session router and the document index.

- [ ] **Step 3: Commit**

Run:

```powershell
git add AGENTS.md docs/project_state.md docs/doc_index.md docs/decision_log.md docs/superpowers/plans/2026-06-09-project-memory-docs.md
git commit -m "docs: add project memory router plan"
```

Expected: commit succeeds if the user has approved committing.
