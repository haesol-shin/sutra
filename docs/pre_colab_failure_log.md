# Pre-Colab Failure Log

이 로그는 pre-Colab 목표 모드 실행 중 실패한 계획/구현/검증 시도를 기록한다. 같은 실패를 반복하지 않기 위해 다음 반복은 반드시 직전 실패의 `next_action`을 먼저 반영한다.

## 2026-06-06 loop-0-invalid-parallel-review

- step_id: `planning-loop-0`
- phase: `plan_arch_eval_protocol`
- command_or_action: planner, architect, critic subagents were spawned in parallel.
- exit_status: rejected_by_user
- failure_summary: The user required sequential `plan -> architecture -> evaluation`, but the first review was dispatched in parallel.
- changed_files: none
- suspected_cause: Misread "플랜 -> 아키텍쳐 -> 평가" as three independent review lanes instead of an ordered review loop.
- next_action: Restart loop. Create a concrete plan document first, then send only that plan to architecture review, then send architecture-approved plan to evaluation review.
- unresolved_blocker: none after loop reset

## 2026-06-06 loop-1-architecture-request-changes

- step_id: `planning-loop-1-architecture`
- phase: `pre_colab_goal_plan`
- command_or_action: sequential architecture review of `docs/pre_colab_goal_plan.md`.
- exit_status: request_changes
- failure_summary: The plan had two execution-contract gaps: Step 1.2 did not name the module/CLI that consumes `data/sources/source_probe.json` and raw snapshots, and Step 4.1 called `nlp_term.retrieve.evaluate` even though that module does not exist yet.
- changed_files: `docs/pre_colab_goal_plan.md`
- suspected_cause: The plan described desired artifacts but did not fully specify the implementation boundary for source parsing and retrieval evaluation.
- next_action: Revise Step 1.2 to add an explicit source-backed prepare CLI and revise Step 4.1 to include `src/nlp_term/retrieve/evaluate.py` as a planned implementation file before re-running architecture review.
- unresolved_blocker: none after plan revision

## 2026-06-06 loop-2-architecture-request-changes

- step_id: `planning-loop-2-architecture`
- phase: `pre_colab_goal_plan`
- command_or_action: sequential architecture review of revised `docs/pre_colab_goal_plan.md`.
- exit_status: request_changes
- failure_summary: Step 4.2 used `--final-readiness` as a Task 2-only gate even though the current validator also reads realtime output. Step 6.1 also omitted the new `nlp_term.prepare.from_sources` command before `build_all`.
- changed_files: `docs/pre_colab_goal_plan.md`
- suspected_cause: The plan mixed final submission readiness checks into a Task 2-only phase and did not fully propagate the new source parsing boundary into the final suite.
- next_action: Remove `--final-readiness` from Step 4.2 and add `nlp_term.prepare.from_sources` to the final local suite before provenance and seed-data checks.
- unresolved_blocker: none after plan revision

## 2026-06-06 loop-3-architecture-request-changes

- step_id: `planning-loop-3-architecture`
- phase: `pre_colab_goal_plan`
- command_or_action: final allowed sequential architecture review of revised `docs/pre_colab_goal_plan.md`.
- exit_status: request_changes
- failure_summary: The plan names HTML parser utilities, but the existing graduation collector fetches a PDF source and explicitly marks PDF extraction as unimplemented. Executing Step 1.2 as written could leave graduation knowledge unsupported.
- changed_files: none after rejection
- suspected_cause: Source modality was not represented in the plan boundary. The plan treated all raw snapshots as HTML-like text even though at least one source is PDF.
- next_action: Human decision required because the maximum 3 architecture loops has been reached. Either allow one additional architecture loop after adding a PDF parsing boundary, or narrow Step 1.2 to non-PDF sources and defer graduation PDF extraction.
- unresolved_blocker: `planning-loop-3-architecture` did not pass

## 2026-06-06 human-decision-document-parsers

- step_id: `planning-loop-3-resolution`
- phase: `pre_colab_goal_plan`
- command_or_action: user decided PDF and HWP support are likely needed.
- exit_status: resolved_by_scope_change
- failure_summary: The prior architecture blocker is addressed by expanding the parser boundary from HTML-only to HTML/PDF/HWP/HWPX.
- changed_files: `docs/pre_colab_goal_plan.md`, `docs/source_inventory.md`
- suspected_cause: Source modality requirements were discovered during sequential architecture review rather than initial planning.
- next_action: Allow one additional sequential architecture review focused only on whether the new document parser boundary closes the loop-3 blocker.
- unresolved_blocker: none after scope change

## 2026-06-06 loop-1-evaluation-request-changes

- step_id: `planning-loop-1-evaluation`
- phase: `pre_colab_goal_plan`
- command_or_action: sequential evaluation review after architecture PASS.
- exit_status: request_changes
- failure_summary: Several quantitative gates were written as plan text but were not guaranteed by current commands. Source-disjoint classifier evaluation could be faked, seed/QA/chat quality thresholds were not machine-checked by validators, and retrieval evaluation could use a different knowledge path than batch/UI answers.
- changed_files: `docs/pre_colab_goal_plan.md`
- suspected_cause: The plan mixed desired quality thresholds with existing validators without adding a validator-hardening phase first.
- next_action: Add explicit validator/metrics implementation steps before data/model quality gates: source parser quality validator, dataset quality validator, classifier metrics validator, retrieval metrics validator, and shared knowledge-loading verification for evaluator/batch/UI.
- unresolved_blocker: none after plan revision

## 2026-06-06 loop-2-evaluation-request-changes

- step_id: `planning-loop-2-evaluation`
- phase: `pre_colab_goal_plan`
- command_or_action: sequential evaluation review of revised plan.
- exit_status: request_changes
- failure_summary: Validator commands were added, but classifier and retrieval metric validators still trusted generated metric files without binding them back to the source dataset, split manifest, knowledge artifact, or QA artifact. The plan also referenced `generation_method` on `KnowledgeDoc` without specifying its schema location.
- changed_files: `docs/pre_colab_goal_plan.md`
- suspected_cause: The first validator-hardening pass checked threshold names but did not fully prevent self-reported metrics from passing without artifact consistency checks.
- next_action: Bind metric validators to original artifacts and define `generation_method` as `KnowledgeDoc.metadata.generation_method`.
- unresolved_blocker: none after plan revision
