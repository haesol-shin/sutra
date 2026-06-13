# Agent Instructions

This repository is for Sutra, a lightweight local-first RAG runtime, with an example workspace for the Chungnam National University (CNU) Campus ChatBot.

## Current Scope

- **Active package**: [src/sutra](src/sutra) is the active engine core.
- **Example workspace**: [examples/cnu-campus](examples/cnu-campus) contains the reference configuration and data indexes.
- **Removed legacy package**: `src/nlp_term/` was removed on 2026-06-13. All active code lives under [src/sutra](src/sutra) for the engine and [examples/cnu-campus](examples/cnu-campus) for the CNU workspace.
- Treat the original assignment constraints in [docs/term_project_requirements.md](docs/term_project_requirements.md) as reference context. The active default task priorities (Task 1, 2, 3) are de-prioritized/legacy; development is centered on Sutra RAG capabilities.
- The distribution package is named `sutra` (`pyproject.toml`), the import package is `sutra` (`src/sutra/`), and the CLI entrypoint is `sutra` / `python -m sutra.cli`.

## Session Bootstrap

- Read [docs/project_state.md](docs/project_state.md) first.
- Read [docs/doc_index.md](docs/doc_index.md) for document status.
- Use [docs/doc_index.md](docs/doc_index.md) `Read When` guidance for task-specific `Current`, `Reference`, or `Evidence` docs.
- Do not execute old plans unless [docs/doc_index.md](docs/doc_index.md) marks them `Current`.
- If docs conflict, [docs/project_state.md](docs/project_state.md) and [docs/doc_index.md](docs/doc_index.md) override old in-document "current" claims.

## Project Conventions

- Use `uv` for environment management and command execution.
- Use Python 3.10.12.
- Use the package-root layout [src/sutra](src/sutra).
- Keep reusable project code under `sutra`, not directly under `src`.
- Prefer Windows-compatible code paths.
- For local XPU development, use the `xpu` extra unless the user asks for a different environment.

## Work Types

Use an explicit type when describing, planning, or committing changes.

- `docs`: documentation-only changes.
- `env`: dependency, `uv`, Python, XPU, or packaging changes.
- `feat`: new user-facing or project-facing behavior.
- `fix`: bug fixes or broken behavior corrections.
- `test`: tests, fixtures, or verification-only changes.
- `refactor`: internal restructuring without behavior changes.
- `chore`: maintenance that does not affect runtime behavior.

Prefer conventional commit-style subjects when committing, for example `env: configure uv xpu environment` or `docs: summarize project requirements`.

## Dependency Policy

- Keep base dependencies small.
- Add optional extras only when they are needed by implemented code.
- `torch 2.9.1+xpu` is the current local development default because it imports and detects XPU on this machine.
- The assignment document lists `torch 2.5.1`; keep that mismatch documented and revisit before final submission.

## Behavioral Guidelines

- Think before coding. State assumptions when they matter, surface tradeoffs, and ask before acting if the request can be interpreted in materially different ways.
- Keep solutions simple. Do not add speculative features, one-off abstractions, or configurability that was not requested.
- Make surgical changes. Touch only files needed for the request, preserve existing style, and do not refactor adjacent code unless it directly supports the task.
- Clean up only changes introduced by the current work. Mention unrelated issues instead of fixing or deleting them opportunistically.
- Define success criteria for multi-step work before editing. Tie each step to a concrete check such as a test, import check, CLI command, or file inspection.
- Verify before completion. Run the smallest relevant command that proves the change works, and report any verification that could not be run.

## Delegation Policy

The orchestrating agent keeps design judgment, planning, review, gating, merges, and user-facing reporting. Bounded implementation is delegated to GJC bundled subagents via the `task`/`subagent` tools; multi-step or risky work goes through the GJC workflow skills.

- **Workflow skills** (use the `/skill:<name>` entrypoints):
  - `ralplan`: consensus planning (Planner → Architect → Critic) for non-trivial architecture/sequencing. Stops at a `pending-approval` plan under `.gjc/plans/ralplan/<run-id>/`; never edits product source before approval.
  - `ultragoal`: durable goal-tracked execution of an approved plan, with a mandatory completion gate (ai-slop sweep + architect review + executor QA) before checkpointing; ledger at `.gjc/ultragoal/`.
  - `team`: tmux-backed coordinated workers — only when interactive parallel worker sessions are actually needed.
- **Role agents** (via the `task` tool, run as detached subagents): `executor` (bounded implementation/fix slices), `planner` (read-only sequencing), `architect` (read-only architecture/code review, CLEAR/WATCH/BLOCK), `critic` (read-only plan critique). Front-load each assignment with verified facts, explicit file scope, acceptance criteria, and a "skip gates/formatters — orchestrator runs them once" instruction.
- **Delegation contract**: every delegated task is self-contained (verified facts, explicit deliverables, file-scope constraints, required focused verification, stop-condition report). Subagents do NOT run project-wide gates/formatters or commit; the orchestrator runs the union gate and owns commits.
- **Review/gate loop**: after implementation, the orchestrator runs the slop sweep, focused + full verification, then a fresh `architect` review (and `executor` QA/red-team for behavioral changes). Non-`APPROVE`/non-`CLEAR` verdicts block completion and are iterated until clean.
- **Commit convention**: strictly `type: message` (feat/fix/test/docs/env/refactor/chore). No scope prefixes. Commit with the **actual current date** — do NOT backdate commits. Branch merges into `dev` use **squash merge** (`git merge --squash <branch>` then one `type: message` commit carrying gate evidence).
- **User approval gate**: the orchestrator reports findings and a proposed plan FIRST and waits for explicit user approval before dispatching new implementation work, committing, merging, or pushing. "~하자" during discussion is consensus on direction, not a go signal; ask "시작할까요?" and wait.
- **Push approval gate (REQUIRED)**: `git push` to ANY branch requires explicit user approval each time. Commit locally as needed, then STOP before pushing and ask. Never push autonomously. The **`submission` branch is FROZEN** (it is the graded git-clone source): push only to `dev`; never push to `submission` unless the user explicitly requests it.
- **Dev CI gate**: `.github/workflows/ci.yml` runs on push/PR to `dev` only (not `submission`): `uv sync --frozen --extra rag --extra ui`, `ruff check .`, then lean pytest (`SUTRA_LEAN_TESTS=1 uv run pytest -q`). Dev-CI-green is a necessary-but-not-sufficient human gate before any approval-gated submission update.
- **Orchestrator keeps**: architecture and tradeoff decisions, task prioritization, prompt/policy design, diff review, test gating, merges into the main tree, commits on `dev`, and user-facing summaries.
- **Evidence required** from every delegate: files changed, commits made (if any), verification command output (e.g. `pytest -q` tail). Unverified claims are treated as not done.
- If a workflow skill or subagent is unavailable, continue inline and note that the work was not delegated.

## Worktree Environment Policy

- Worker worktrees sync **base + dev dependency group only** (`uv sync`); the uv global cache (hardlinks, same drive) makes this take seconds-to-minutes. Never install `xpu`/`ui` extras in worker worktrees.
- Heavy integration verification (llama-server, Chainlit UI, XPU torch) happens only in the main working tree.
- Prefer reusing existing worktrees that already have a `.venv`. Branch naming for delegated work: `p0/<topic>`, `p1/<topic>` matching the active plan phase.

## Documentation Policy & Roles

- Temporary plans, design proposals, reviews, and logs must be stored under `tmp/` (e.g., `tmp/planning_docs/`).
- Only stable, source-of-truth reference documentation goes under `docs/`.
- **Key Files**:
  - [README.md](README.md): project overview and commands.
  - [AGENTS.md](AGENTS.md): agent-facing rules, scope, and workflow constraints.
  - [docs/project_state.md](docs/project_state.md): active tasks, corpus counts, and focus area directions.
  - [docs/doc_index.md](docs/doc_index.md): index registry specifying what is current vs. stale/reference.

## Verification

- Run the smallest relevant `uv run ...` command before claiming a setup or code change works.
- For environment changes, check at least Python version, package import, and torch/XPU availability when applicable.
- **Prefer `uv run sutra` CLI** for any operation that has a sutra subcommand (`ask`, `llama serve`, `docs check`, `workspace validate`, `doctor`, `ui`). Avoid ad-hoc scripts or manual `python -c` when a CLI path exists.
- If a desired operation has no sutra CLI path, note it and ask the user at session end whether a new subcommand should be added.
- **Execute real tests**: Dry-run checks and import verification are not sufficient. Whenever possible, start the actual service (`sutra llama serve`, `sutra ask`, `sutra ui`) and verify outputs. Mock-only tests pass silently while real execution reveals port conflicts, missing deps, model loading failures, and import errors that dry-runs miss.
- After any server process test, verify the process is fully terminated and the port is released before claiming completion.

## Parallel Agent Work Policy

- **Git worktree required**: Each parallel agent MUST operate in its own isolated git worktree. Never run multiple agents in the same working directory — file conflicts, port collisions, and dependency state will silently corrupt results.
- Worktree naming: `../sutra-{group}-{id}` (e.g. `../sutra-a1`, `../sutra-b2`).
- After task completion and review pass, the agent reports its branch and evidence; it does NOT push. The orchestrator merges branches into the main tree and pushes ONLY after explicit user approval (see the push approval gate in Delegation Policy).
