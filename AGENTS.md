# Agent Instructions

This repository is for the Natural Language Processing term project: a Campus ChatBot for Chungnam National University students.

## Current Scope

- Keep the project centered on the assignment requirements summarized in `docs/term_project_requirements.md`.
- Prioritize Task 1 question classification and Task 2 chatbot/UI before Optional Task 3 realtime information.
- Treat Optional Task 3 as extra credit unless the user explicitly changes that priority.
- Use `../aidm-term-proj` only as a reference for environment and workflow patterns, not as a source of project requirements.

## Session Bootstrap

- Read `docs/project_state.md` first.
- Read `docs/doc_index.md` for document status.
- Read `docs/term_project_requirements.md` for assignment constraints.
- Use `docs/doc_index.md` `Read When` guidance for task-specific `Current`, `Reference`, or `Evidence` docs.
- Do not execute old plans unless `docs/doc_index.md` marks them `Current`.
- If docs conflict, `docs/project_state.md` and `docs/doc_index.md` override old in-document "current" claims.

## Project Conventions

- Use `uv` for environment management and command execution.
- Use Python 3.10.12.
- Use the package-root layout `src/nlp_term/`.
- Keep reusable project code under `nlp_term`, not directly under `src`.
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

## Documentation Roles

- `README.md`: short project overview and commands for humans.
- `AGENTS.md`: agent-facing rules, scope, and workflow constraints.
- `docs/term_project_requirements.md`: source-backed assignment requirements and open decisions.

## Verification

- Run the smallest relevant `uv run ...` command before claiming a setup or code change works.
- For environment changes, check at least Python version, package import, and torch/XPU availability when applicable.
