# Evidence Packet: phase-2.2-qa-data-2026-06-06

- meeting_id: `phase-2.2-qa-data-2026-06-06`
- opened_at: `2026-06-06`
- trigger: final Phase 2.2 critic returned `REQUEST CHANGES`
- phase: `Phase 2.2 QA Dataset Generation`
- step_id: `phase-2.2-qa-dataset-generation`
- attempt_count: 3 critic loops

## Trigger Summary

Scripted gates pass for `data/qa_seed.json`, but the final critic found remaining QA quality blockers:

- case-variant boilerplate such as `The Strong CNU`
- additional CNU coop mojibake fragments
- generic fallback evidence text that is not source-specific

## Relevant Artifacts

- `data/qa_seed.json`
- `data/knowledge_seed.json`
- `src/nlp_term/prepare/qa_data.py`
- `src/nlp_term/validators.py`
- `docs/pre_colab_progress.md`
- `docs/pre_colab_failure_log.md`

## Current Scripted Gates

- `uv run python -m nlp_term.validators --dataset-quality --data-dir data --min-qa-rows 50 --min-qa-per-label 8 --require-qa-source`: passes
- `uv run python -m nlp_term.validators --seed-data --data-dir data`: passes
- `uv run python -m compileall src\nlp_term\prepare src\nlp_term\validators.py`: passes
- `uv run ruff check src\nlp_term\prepare src\nlp_term\validators.py`: passes

## Research Used

Meeting method research:

- ASQ, Nominal Group Technique: https://asq.org/quality-resources/nominal-group-technique (accessed 2026-06-06)
- Praxis Framework, Nominal Group Technique: https://www.praxisframework.org/en/library/nominal-group-technique (access attempted 2026-06-06; search result available, direct page may be inaccessible)
- Delphi method overview: https://en.wikipedia.org/wiki/Delphi_method (accessed 2026-06-06)
- Gary Klein, Performing a Project Premortem: https://hbr.org/2007/09/performing-a-project-premortem (accessed 2026-06-06)
- Du et al., Improving Factuality and Reasoning in Language Models through Multiagent Debate: https://arxiv.org/abs/2305.14325 (accessed 2026-06-06)
- Multi-Agent Wiki, Debate/Judge/Voting: https://multi-agent.wiki/patterns/debate-judge (accessed 2026-06-06)

Data-quality research:

- Trafilatura package and boilerplate-aware extraction: https://pypi.org/project/trafilatura/ (accessed 2026-06-06)
- jusText boilerplate removal package: https://pypi.org/project/jusText/3.0.1/ (accessed 2026-06-06)
- Retrieval-Augmented Generation survey: https://huggingface.co/papers/2312.10997 (accessed 2026-06-06)

Project materials:

- `docs/term_project_requirements.md`
- `docs/source_inventory.md`
- `docs/pre_colab_goal_plan.md`

## Assignment Constraints

- Task 1/2 before Optional Task 3.
- Final inference cannot use external LLM API, MCP, or tool-call agent.
- Data must remain source-backed and verifiable.
- Changes must preserve `src/classifier.ipynb` and `chatbot.sh`.
