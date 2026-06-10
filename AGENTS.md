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

- When `codex-spark` is available, delegate low-judgment execution tasks to it before doing them inline.
- Good `codex-spark` tasks include crawling/fetching candidate pages, exploratory source discovery, repetitive parser trials, mechanical code edits from an already-approved design, and routine verification command runs.
- Keep architecture, tradeoff decisions, task prioritization, final acceptance, commits, and user-facing summaries with the main Codex agent unless the user explicitly asks otherwise.
- Give delegated tasks narrow inputs, expected outputs, and stop conditions. Require concrete evidence such as fetched URLs, file paths, count tables, failing/passing commands, or short implementation diffs.
- If `codex-spark` is unavailable, continue inline and note that the work was not delegated.

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
