# Document Index

This file registry defines document statuses. If documents conflict, [docs/project_state.md](project_state.md) and this index override old in-document "current" claims.

> [!IMPORTANT]
> **Read Guidance:**
> - Read [README.md](../README.md), [docs/project_state.md](project_state.md), and [docs/sutra_architecture.md](sutra_architecture.md) for a general project overview.
> - Read [examples/cnu-campus/README.md](../examples/cnu-campus/README.md) for details about the CNU example workspace.
> - Any temporary plans, reviews, or logs placed in `tmp/` are *not* source-of-truth documents.
> - Stale documents and planning artifacts identified in Pass 2 have been deleted to clean up the repository.

## Status Definitions
- `Current`: Active direction or required current state.
- `Reference`: Stable background information.
- `Evidence`: Experiment result, audit, or raw finding.

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

