# Document Index

This file registry defines document statuses. If documents conflict, [docs/project_state.md](project_state.md) and this index override old in-document "current" claims.

> [!IMPORTANT]
> **Read Guidance:**
> - Read [README.md](../README.md), [docs/project_state.md](project_state.md), and [docs/sutra_architecture.md](sutra_architecture.md) for a general project overview.
> - Read [examples/cnu-campus/README.md](../examples/cnu-campus/README.md) for details about the CNU example workspace.
> - Any temporary plans, reviews, or logs placed in `tmp/` are *not* source-of-truth documents.
> - Stale documents remain on disk during this first pass, but are marked below for deletion/archive in the next pass.

## Status Definitions
- `Current`: Active direction or required current state.
- `Reference`: Stable background information.
- `Evidence`: Experiment result, audit, or raw finding.
- `Historical / Stale`: Stale/legacy documentation or plans (slated for archive/deletion in Pass 2).
- `Do Not Execute`: Old plans/experiments that must not be run.

---

## Active & Reference Documents

| Document | Status | Purpose | Read When |
| --- | --- | --- | --- |
| [README.md](../README.md) | Current | Project overview and commands | Every session start |
| [AGENTS.md](../AGENTS.md) | Current | Agent instructions and conventions | Every session start |
| [docs/project_state.md](project_state.md) | Current | Current project state and next action | Every session start |
| [docs/doc_index.md](doc_index.md) | Current | Document status registry | Every session start |
| [docs/sutra_architecture.md](sutra_architecture.md) | Current | Sutra package architecture and workspace format | Before core package or runner changes |
| [examples/cnu-campus/README.md](../examples/cnu-campus/README.md) | Current | CNU example workspace description | Before modifying the CNU workspace |
| [docs/decision_log.md](decision_log.md) | Reference | Append-only historical decision rationale | When reconstructing design decisions |
| [docs/term_project_requirements.md](term_project_requirements.md) | Reference | Assignment constraints (Legacy) | Before changing baseline evaluation |
| [docs/qwen_runtime.md](qwen_runtime.md) | Reference | Local Qwen runtime notes | Before model execution changes |
| [docs/source_inventory.md](source_inventory.md) | Reference | Source collection overview | Before source collection changes |
| [docs/model_decisions.md](model_decisions.md) | Reference | Model/backend decisions | Before model selection changes |
| [docs/data_structure_discovery_report.md](data_structure_discovery_report.md) | Evidence | Raw CNU source structure audit | Before extending/building CNU parsers |
| [docs/source_fetch_audit_2026_06_08.md](source_fetch_audit_2026_06_08.md) | Evidence | Source fetch audit output | When checking source availability |
| [docs/tier1_data_collection_run_2026_06_08.md](tier1_data_collection_run_2026_06_08.md) | Evidence | Documents the data collection process | Rationale for rebuild from raw |

## Stale Documents & Plans (Slated for Archive/Deletion in Pass 2)

These files are legacy assets from the original "NLP Term Project" framing and noisy corpus phases. Do not execute or use them for active development guidance.

| Document | Status | Reason |
| --- | --- | --- |
| `docs/project_architecture_plan.md` | Historical / Stale | Superseded by `sutra_architecture.md` |
| `docs/data_migration_plan.md` | Do Not Execute | Stale plan about 2414-doc migration |
| `docs/data_expansion_goal_plan.md` | Historical / Stale | Superseded by clean rebuild |
| `docs/data_expansion_progress.md` | Historical / Stale | Early data progress tracking |
| `docs/data_expansion_failure_log.md` | Historical / Stale | Early failure log |
| `docs/pre_colab_goal_plan.md` | Historical / Stale | Superseded early pre-Colab plan |
| `docs/pre_colab_progress.md` | Historical / Stale | Early progress tracking |
| `docs/pre_colab_failure_log.md` | Historical / Stale | Early failure log |
| `docs/next_data_expansion_priorities.md` | Historical / Stale | Superseded by clean rebuild |
| `docs/meeting_room_dashboard.md` | Historical / Stale | Agent workflow dashboard |
| `docs/meeting_protocol.md` | Historical / Stale | Multi-agent protocol |
| `docs/harness_safety_experiment.md` | Historical / Stale | Legacy `nlp_term` experiment |
| `docs/task2_improvement_sequence_after_probe.md` | Historical / Stale | Superseded sequence plan |
| `docs/task2_claim_guard_notes.md` | Historical / Stale | Superseded notes |
| `docs/task2_llm_backend_plan.md` | Historical / Stale | Superseded LLM plan |
| `docs/task2_llm_backend_results.md` | Historical / Stale | Superseded results |
| `docs/task2_task3_harness_architecture.md` | Historical / Stale | Legacy harness architecture |
| `docs/task1_error_improvement_candidates.md` | Historical / Stale | Legacy classifier error analysis |
| `docs/task2_example_questions_qwen_2026_06_08.md` | Historical / Stale | Stale experiment output |
| `docs/representative_departments_2026.md` | Historical / Stale | Stale reference list |
| `docs/synthetic_data_protocol.md` | Historical / Stale | Stale protocol |
| `docs/data_readiness_report_2026_06_09.md` | Historical / Stale | Refers to legacy noisy corpus |
| `docs/data_inventory_report.md` | Historical / Stale | Legacy layout description |
| `docs/task2_simplification_direction_2026_06_09.md` | Historical / Stale | Prior simplification notes for nlp_term |
| `docs/superpowers/plans/*` (14 plan files) | Historical / Stale | Early project plans under `docs/superpowers/plans/` |
| `docs/meetings/*` (22 meeting records) | Historical / Stale | Agent workflow logs under `docs/meetings/` |
