# Agent Instructions

This repository is for Sutra, a lightweight local-first RAG runtime, with an example workspace for the Chungnam National University (CNU) Campus ChatBot.

## Current Scope

- **Active package**: [src/sutra](src/sutra) is the active engine core.
- **Example workspace**: [examples/cnu-campus](examples/cnu-campus) contains the reference configuration and data indexes.
- **Legacy package**: [src/nlp_term](src/nlp_term) is legacy code and is no longer active. Do **not** read, import, or reference any code under `src/nlp_term/`. All new work is under `src/sutra/`, `classifier/`, or `examples/cnu-campus/`.
- Treat the original assignment constraints in [docs/term_project_requirements.md](docs/term_project_requirements.md) as reference context. The active default task priorities (Task 1, 2, 3) are de-prioritized/legacy; development is centered on Sutra RAG capabilities.
- Use `../aidm-term-proj` only as a reference for environment and workflow patterns.

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

Implementation work is delegated to CLI sub-agents; the orchestrating agent (Claude) keeps design judgment, review, merge, and user-facing reporting.

- **Routing by difficulty**:
  - `codex` (`codex exec --full-auto -c model_reasoning_effort=high`, model gpt-5.5): **default for all code work** — implementation, fixes, parsers, entry-point work, anything where failure-mode design matters.
  - `opencode` (deepseek-v4-flash-free): mechanical/secondary work only. **Code tasks delegated to opencode MUST use the Executor agent** defined at [.opencode/agent/executor.md](.opencode/agent/executor.md): `opencode run --agent executor "Read tmp/TASK.md and execute it"`. Plain `opencode run` without the agent is reserved for non-code chores.
  - Internal Claude subagents (search, research, review assistance): model **sonnet**.
- **Task contract**: every delegation gets a self-contained `tmp/TASK.md` in its worktree containing verified facts, explicit deliverables, file-scope constraints ("do not touch X — owned by parallel agent"), required verification commands, and a stop-condition report format. Launch with a one-line pointer prompt ("Read tmp/TASK.md and execute it").
- **Review loop**: when an executor session finishes, a FRESH codex session reviews the branch diff (writes `tmp/REVIEW_round<N>.md`), the executor session addresses findings, repeated for at most 3 rounds; unresolved issues escalate to the orchestrator. opencode outputs get the same codex review.
- **Commit convention**: strictly `type: message` (feat/fix/test/docs/env/refactor/chore). No scope prefixes. Branch merges into dev use **squash merge** (`git merge --squash <branch>` then one `type: message` commit carrying gate evidence) — merge-commit chains were judged noisy by the user.
- **User approval gate**: the orchestrator reports findings and a proposed plan FIRST and waits for explicit user approval before dispatching new work, committing, or merging. "~하자" during discussion is consensus on direction, not a go signal; ask "시작할까요?" and wait.
- **Orchestrator keeps**: architecture and tradeoff decisions, task prioritization, prompt/policy design, diff review, test gating, merges into the main tree, commits on `dev`, and user-facing summaries.
- **Evidence required** from every delegate: files changed, commits made, verification command output (e.g. `pytest -q` tail). Unverified claims are treated as not done.
- If both CLIs are unavailable, continue inline and note that the work was not delegated.

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
- After task completion and review pass, the agent pushes its branch. The team lead merges branches sequentially into the main working tree.
