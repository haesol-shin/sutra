# Document Index

This file owns document status. If documents conflict, `docs/project_state.md` and this index override old in-document "current" claims.

Status enum:
- `Current`: active direction or required current state.
- `Reference`: stable background information.
- `Evidence`: experiment result, audit, or raw finding.
- `Historical`: useful past context, not active instruction.
- `Superseded`: replaced by another document.
- `Do Not Execute`: old plan or experiment that must not be run unless reactivated here.

Conflict rule:
- Read `docs/project_state.md` first for current direction.
- Do not execute old plans unless this index marks them `Current`.
- Treat `Do Not Execute` as stronger than any checklist or instruction inside that document.
- Unlisted docs are not current. Do not execute an unlisted plan unless the user explicitly reactivates it and this index is updated.

| Document | Status | Purpose | Read When | Superseded By |
| --- | --- | --- | --- | --- |
| `docs/project_state.md` | Current | Current project state and next action | Every session start |  |
| `docs/doc_index.md` | Current | Document status registry | Every session start |  |
| `docs/decision_log.md` | Reference | Append-only decision rationale | When reconstructing why a decision changed |  |
| `docs/term_project_requirements.md` | Reference | Assignment requirements | Before changing scope or evaluation behavior |  |
| `docs/sutra_architecture.md` | Current | Sutra package architecture, workspace format, and runtime boundaries | Before Sutra package, workspace, API, UI, or llama-server work |  |
| `docs/task2_simplification_direction_2026_06_09.md` | Current | Current Task 2 simplification direction | Before Task 2, RAG, Qwen, or evidence-path work |  |
| `docs/qwen_runtime.md` | Reference | Local Qwen runtime notes | Before model execution changes |  |
| `docs/source_inventory.md` | Reference | Source collection overview | Before source collection changes |  |
| `docs/model_decisions.md` | Reference | Model/backend decisions | Before model selection changes |  |
| `docs/data_readiness_report_2026_06_09.md` | Evidence | Data readiness counts and caveats | When auditing current data quality |  |
| `docs/source_fetch_audit_2026_06_08.md` | Evidence | Source fetch audit output | When checking source availability |  |
| `docs/data_inventory_report.md` | Evidence | Data/artifact inventory before Sutra cleanup | When auditing legacy data locations |  |
| `docs/data_structure_discovery_report.md` | Evidence | Raw CNU source structure and parser feasibility audit | Before building or extending CNU parsers |  |
| `docs/data_migration_plan.md` | Do Not Execute | Earlier direct data migration plan; superseded by raw rebuild direction | Only for historical reference | `docs/data_structure_discovery_report.md` |
| `docs/task2_public_probe_qwen_baseline_2026_06_08.md` | Evidence | Qwen public probe baseline | When comparing Task 2 answer quality |  |
| `docs/task2_public_probe_harness_diagnosis_2026_06_08.md` | Evidence | Harness failure diagnosis | When investigating old harness behavior |  |
| `docs/task2_probe39_report_2026_06_08.md` | Evidence | Probe39 run report | When comparing probe behavior |  |
| `docs/task2_public_probe_harness_latest.md` | Evidence | Latest legacy Task 2 harness diagnosis snapshot | Only when investigating legacy `nlp_term` behavior |  |
| `docs/task2_public_probe_qwen_latest.md` | Evidence | Latest legacy Task 2 Qwen baseline snapshot | Only when investigating legacy `nlp_term` behavior |  |
| `docs/task2_probe39_report_latest.md` | Evidence | Latest legacy Task 2 probe39 diagnosis snapshot | Only when investigating legacy `nlp_term` behavior |  |
| `docs/evidence/task2-public-probe-harness-latest.json` | Evidence | Machine-readable latest legacy public harness run | Only when investigating legacy `nlp_term` behavior |  |
| `docs/evidence/task2-public-probe-qwen-latest.json` | Evidence | Machine-readable latest legacy public Qwen run | Only when investigating legacy `nlp_term` behavior |  |
| `docs/evidence/task2-probe39-harness-latest.json` | Evidence | Machine-readable latest legacy probe39 harness run | Only when investigating legacy `nlp_term` behavior |  |
| `docs/project_architecture_plan.md` | Historical | Earlier architecture baseline | Only for background | `docs/project_state.md` |
| `docs/task2_task3_harness_architecture.md` | Historical | Earlier harness architecture | Only for background | `docs/task2_simplification_direction_2026_06_09.md` |
| `docs/task2_improvement_sequence_after_probe.md` | Historical | Earlier improvement ordering | Only for background | `docs/task2_simplification_direction_2026_06_09.md` |
| `docs/task2_claim_guard_notes.md` | Historical | Earlier claim-guard notes | Only for background | `docs/task2_simplification_direction_2026_06_09.md` |
| `docs/superpowers/plans/2026-06-09-simple-evidence-units.md` | Do Not Execute | Earlier detailed plan that needs revision before use | Only for historical reference | `docs/task2_simplification_direction_2026_06_09.md` |
| `docs/superpowers/plans/2026-06-09-project-memory-docs.md` | Historical | Plan used to create this memory router | Only for background after implementation | `docs/project_state.md` |
| `docs/superpowers/plans/2026-06-06-data-model-pipeline.md` | Historical | Earlier data/model pipeline plan | Only for historical reference | `docs/project_state.md` |
| `docs/superpowers/plans/2026-06-07-priority1-graduation-data-expansion.md` | Do Not Execute | Earlier graduation expansion plan conflicts with current no-prose-row direction | Only for historical reference | `docs/task2_simplification_direction_2026_06_09.md` |
| `docs/superpowers/plans/2026-06-07-task2-vertical-slice.md` | Do Not Execute | Earlier Task 2 vertical-slice plan predates current simplification direction | Only for historical reference | `docs/task2_simplification_direction_2026_06_09.md` |
| `docs/superpowers/plans/2026-06-08-academic-calendar-exact-lookup.md` | Historical | Earlier academic calendar exact lookup plan | Only for background when revisiting calendar retrieval | `docs/task2_simplification_direction_2026_06_09.md` |
| `docs/superpowers/plans/2026-06-08-evidence-pack-context-expansion.md` | Do Not Execute | Earlier evidence-pack expansion plan conflicts with current simplification direction | Only for historical reference | `docs/task2_simplification_direction_2026_06_09.md` |
| `docs/superpowers/plans/2026-06-08-generalization-coverage-expansion.md` | Historical | Earlier generalization coverage plan | Only for background when planning data coverage | `docs/project_state.md` |
| `docs/superpowers/plans/2026-06-08-source-adapter-structured-row-contract.md` | Historical | Earlier structured-row contract plan | Only for background when revisiting parser contracts | `docs/task2_simplification_direction_2026_06_09.md` |
| `docs/superpowers/plans/2026-06-08-temporal-intent-harness.md` | Do Not Execute | Older temporal policy plan conflicts with current simplification direction | Only for historical reference | `docs/task2_simplification_direction_2026_06_09.md` |
| `docs/superpowers/plans/2026-06-08-validator-policy-softening.md` | Do Not Execute | Older validator plan conflicts with current minimal-validator direction | Only for historical reference | `docs/task2_simplification_direction_2026_06_09.md` |
| `docs/superpowers/plans/2026-06-08-structure-aware-chunking.md` | Do Not Execute | Older chunking plan needs revision before use | Only for historical reference | `docs/task2_simplification_direction_2026_06_09.md` |
| `docs/superpowers/plans/2026-06-08-retrieval-candidate-expansion.md` | Historical | Earlier retrieval expansion plan | Only for background | `docs/task2_simplification_direction_2026_06_09.md` |
| `docs/superpowers/plans/2026-06-08-source-data-expansion-first.md` | Historical | Earlier data-first plan | Only for background | `docs/project_state.md` |
