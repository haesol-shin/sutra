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

## 2026-06-06 step-1.2-fetch-timeout-attempt-1

- step_id: `phase-1.2-domain-parser-coverage`
- phase: `source_parsers_and_knowledge_docs`
- command_or_action: `uv run python -m nlp_term.collect.run_collect --fetch --output data/sources/source_probe.json`
- exit_status: failed
- failure_summary: Graduation PDF fetch from `plus.cnu.ac.kr` timed out at the current 20 second read timeout.
- changed_files: none intentionally changed by the failed command
- suspected_cause: Remote server/network latency during large PDF download.
- next_action: Retry the fetch once before changing collector behavior; existing raw snapshots remain available for parser validation.
- unresolved_blocker: none until max attempts is reached

## 2026-06-06 step-1.2-knowledge-quality-attempt-1

- step_id: `phase-1.2-domain-parser-coverage`
- phase: `source_parsers_and_knowledge_docs`
- command_or_action: `uv run python -m nlp_term.validators --knowledge-quality data/knowledge_seed.json --source-probe data/sources/source_probe.json --min-docs-per-label 3 --min-body-chars 80 --min-source-parse-ratio 0.8`
- exit_status: failed
- failure_summary: Dining label 3 produced only 2 `KnowledgeDoc` rows, below the required minimum of 3 per label.
- changed_files: `data/knowledge_seed.json`, `data/cls_train_seed.json`, `data/label_audit_seed.json`, `data/qa_seed.json`
- suspected_cause: Generic chunking produced too few chunks for shorter dining HTML sources.
- next_action: Adjust source chunking so each raw source can emit multiple non-overlapping chunks when enough text exists, then regenerate knowledge and rerun quality gates.
- unresolved_blocker: none until max attempts is reached

## 2026-06-06 step-2.1-conflicting-duplicates-attempt-1

- step_id: `phase-2.1-classification-dataset-generation`
- phase: `source_backed_classification_and_qa_data`
- command_or_action: sequential Phase 2.1 critic review.
- exit_status: request_changes
- failure_summary: Numeric dataset gates passed, but critic found exact duplicate question texts assigned to conflicting labels and accepted by tautological self-consistency votes.
- changed_files: `data/cls_train_seed.json`, `data/label_audit_seed.json`, `docs/pre_colab_progress.md`, `src/nlp_term/prepare/cls_data.py`
- suspected_cause: Generator deduplicated by `(question, label)` instead of normalized question text, raw anchors included boilerplate tokens, and audit votes simply repeated the expected label.
- next_action: Add global question-label consistency enforcement in generator and validators, filter boilerplate anchors, and make deterministic audit votes rule-based enough to catch conflicts.
- unresolved_blocker: none until max attempts is reached

## 2026-06-06 step-2.1-row-count-after-dedupe-attempt-2

- step_id: `phase-2.1-classification-dataset-generation`
- phase: `source_backed_classification_and_qa_data`
- command_or_action: `uv run python -m nlp_term.validators --dataset-quality --data-dir data --min-cls-rows 250 --min-cls-per-label 40 --min-ambiguous-per-label 5 --no-dry-run --require-validated`
- exit_status: failed
- failure_summary: After fixing conflicting duplicate questions, the classification dataset dropped to 201 rows, below the required 250 rows.
- changed_files: `src/nlp_term/prepare/cls_data.py`, `src/nlp_term/validators.py`, `data/cls_train_seed.json`, `data/label_audit_seed.json`
- suspected_cause: Global dedupe and stronger anchor filtering removed low-quality rows faster than template variants replaced them.
- next_action: Add safe domain-specific template variants that include label hints and do not create cross-label duplicate questions.
- unresolved_blocker: none until max attempts is reached

## 2026-06-06 step-2.2-qa-quality-attempt-1

- step_id: `phase-2.2-qa-dataset-generation`
- phase: `source_backed_classification_and_qa_data`
- command_or_action: sequential Phase 2.2 critic review.
- exit_status: request_changes
- failure_summary: QA rows passed numeric/source-presence gates but copied navigation boilerplate, mojibake, and generic non-answer text into answers.
- changed_files: `data/qa_seed.json`, `docs/pre_colab_progress.md`, `src/nlp_term/prepare/qa_data.py`
- suspected_cause: QA generator used the first source body tokens directly and validator only checked for URL/source hint presence.
- next_action: Clean source excerpts before QA generation, remove generic answer variants, and strengthen QA validators against boilerplate, mojibake, banned terms, and generic non-answer rows.
- unresolved_blocker: none until max attempts is reached

## 2026-06-06 step-2.2-qa-quality-attempt-2

- step_id: `phase-2.2-qa-dataset-generation`
- phase: `source_backed_classification_and_qa_data`
- command_or_action: sequential Phase 2.2 critic recheck.
- exit_status: request_changes
- failure_summary: Generic answers were fixed, but QA answers still contained broader navigation/promotional boilerplate and CNU coop mojibake not covered by the first filter.
- changed_files: `src/nlp_term/prepare/qa_data.py`, `src/nlp_term/validators.py`, `data/qa_seed.json`, `docs/pre_colab_progress.md`
- suspected_cause: Boilerplate and mojibake rejection lists were too narrow.
- next_action: Expand cleaning and validation terms for promotional chrome, open/close button text, footer-only content, and non-Korean mojibake fragments; regenerate QA and rerun gates.
- unresolved_blocker: none until max attempts is reached

## 2026-06-06 step-2.2-qa-quality-attempt-3

- step_id: `phase-2.2-qa-dataset-generation`
- phase: `source_backed_classification_and_qa_data`
- command_or_action: final allowed sequential Phase 2.2 critic recheck.
- exit_status: request_changes
- failure_summary: Numeric/source gates passed, but QA answers still contained case-variant boilerplate (`The Strong CNU`), additional CNU coop mojibake fragments, and fallback evidence text (`공식 source에서 확인한 해당 주제의 안내 범위와 근거`) that is not source-specific.
- changed_files: `src/nlp_term/prepare/qa_data.py`, `src/nlp_term/validators.py`, `data/qa_seed.json`, `docs/pre_colab_progress.md`
- suspected_cause: The cleaning logic still relies on deny-lists and generic fallback text instead of selecting cleaner source spans or excluding unusable chunks.
- next_action: Human decision required because the maximum 3 Phase 2.2 critic loops has been reached. Recommended next direction is to exclude polluted source chunks from QA generation or add positive evidence selection before regenerating QA.
- unresolved_blocker: `phase-2.2-qa-dataset-generation` did not pass

## 2026-06-06 step-6.1-realtime-timeout-attempt-1

- step_id: `phase-6.1-final-local-suite`
- phase: `final_pre_colab_readiness`
- command_or_action: `bash chatbot.sh realtime`
- exit_status: timeout
- failure_summary: The realtime fallback command exceeded the local 60 second command timeout during final readiness rerun after wording hardening.
- changed_files: none intentionally changed by the timed-out command
- suspected_cause: Windows bash/uv startup latency; the same command had passed earlier in the run.
- next_action: Retry once with a 120 second timeout before changing runtime behavior.
- unresolved_blocker: none until retry fails

## 2026-06-06 step-6.1-realtime-bash-vm-timeout-attempt-2

- step_id: `phase-6.1-final-local-suite`
- phase: `final_pre_colab_readiness`
- command_or_action: `bash chatbot.sh realtime`
- exit_status: failed
- failure_summary: Retrying with a 120 second timeout failed before the script body could run because Bash/WSL reported `HCS_E_CONNECTION_TIMEOUT` while creating the VM.
- changed_files: none intentionally changed by the failed command
- suspected_cause: Local WSL/bash service startup failure, not Python realtime code failure.
- next_action: Inspect which `bash` executable is being used, verify the Python module path directly, then retry `chatbot.sh` after local bash/WSL recovery if possible.
- resolution: A later submission-readiness critic successfully ran `chatbot.sh realtime` and regenerated valid realtime output; the failure was transient local WSL/bash startup behavior.
- unresolved_blocker: none after successful rerun

## 2026-06-06 step-6.1-realtime-provenance-request-changes

- step_id: `phase-6.1-final-local-suite`
- phase: `final_pre_colab_readiness`
- command_or_action: final Data/Source critic review.
- exit_status: request_changes
- failure_summary: `outputs/realtime_output.json` claimed `검증된 공식 source` and `최신 정보` even though current source probe entries have `official_chain_ok=false`.
- changed_files: `src/nlp_term/chat/realtime.py`, `src/nlp_term/validators.py`, `outputs/realtime_output.json`
- suspected_cause: Final-readiness validator only checked placeholder terms and did not bind realtime wording to source verification status.
- next_action: Keep Task 3 path as fallback-only, soften realtime wording, and add a realtime provenance validator that rejects unsupported verified/latest source claims.
- unresolved_blocker: none after wording and validator hardening

## 2026-06-06 step-6.1-submission-doc-status-request-changes

- step_id: `phase-6.1-final-local-suite`
- phase: `final_pre_colab_readiness`
- command_or_action: final Submission-readiness critic review.
- exit_status: request_changes
- failure_summary: Functional readiness passed, but `docs/pre_colab_progress.md` still marked Phase 6.1 as `in_progress` and this failure log still made the bash/WSL timeout look like a current blocker.
- changed_files: `docs/pre_colab_progress.md`, `docs/pre_colab_failure_log.md`
- suspected_cause: Documentation was updated before the successful post-fix critic reruns completed.
- next_action: Update Phase 6.1 status to pass and record that the later critic successfully reran `chatbot.sh realtime`.
- unresolved_blocker: none after documentation status update
