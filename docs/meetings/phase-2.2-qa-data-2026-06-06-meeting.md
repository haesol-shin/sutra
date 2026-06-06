# Meeting: phase-2.2-qa-data-2026-06-06

작성일: 2026-06-06

## Trigger

The Phase 2.2 QA dataset step received `REQUEST CHANGES` after three critic loops. Scripted validators passed, but qualitative review found CNU page boilerplate, mojibake, and generic fallback evidence inside `data/qa_seed.json`.

## Research Basis

- Meeting structure: Nominal Group Technique, Delphi-style iteration, premortem, red-team critique, and multi-agent debate.
- Data-quality direction: web boilerplate removal patterns from Trafilatura/jusText-style main-content extraction, plus source-grounded RAG evidence checking.

References:

- ASQ, Nominal Group Technique: https://asq.org/quality-resources/nominal-group-technique (accessed 2026-06-06)
- Gary Klein, Performing a Project Premortem: https://hbr.org/2007/09/performing-a-project-premortem (accessed 2026-06-06)
- Du et al., Improving Factuality and Reasoning in Language Models through Multiagent Debate: https://arxiv.org/abs/2305.14325 (accessed 2026-06-06)
- Trafilatura: https://pypi.org/project/trafilatura/ (accessed 2026-06-06)
- jusText: https://pypi.org/project/jusText/3.0.1/ (accessed 2026-06-06)
- RAG survey: https://huggingface.co/papers/2312.10997 (accessed 2026-06-06)

## Role Verdicts

| Role | Verdict | Main Point |
| --- | --- | --- |
| Source/Data Steward | `REQUEST CHANGES` | The direction is right, but exact evidence-span gates must be recorded. |
| Runtime/Architecture Engineer | `PASS/WATCH` | Minimal and Windows/uv friendly if implemented locally in QA generation and validators. |
| Evaluation/Validator Engineer | `REQUEST CHANGES` | Current official gate still passes polluted rows, so pollution and grounding checks must be deterministic. |
| Red-Team Critic | `REQUEST CHANGES` | The handoff underspecified thresholds, keyword sets, row-loss recovery, and fallback bans. |
| Facilitator/Planner | `PASS` | Proceed with positive evidence selection, but keep a clear stop condition. |

## Options

| Option | Description | Total | Median | Decision |
| --- | --- | ---: | ---: | --- |
| A | Exclude polluted chunks before QA generation | 18 | 4 | Included as fallback inside B |
| B | Positive evidence span selection plus hard validator gates | 23 | 5 | Selected |
| C | Reparse/rechunk/backfill clean source sections upstream | 17 | 3 | Recovery path if B fails row gates |

## Decision

Select Option B, revised:

1. Add source-specific evidence span selection before QA row creation.
2. Forbid generic fallback evidence entirely.
3. Add case-insensitive boilerplate, mojibake, private-use glyph, Korean-density, label-keyword, and source-grounding checks to validators.
4. Regenerate `data/qa_seed.json`.
5. Run deterministic gates.
6. Run a Source/Data critic over all QA rows before unblocking Phase 2.2.

## Premortem Guardrails

Assumed failure: positive scoring still selects page chrome or drops below row gates.

Guardrails:

- Evidence must quote a useful clean span, not a synthesized summary.
- Navigation/header/footer terms are rejected case-insensitively.
- Label-specific keywords are required but not sufficient; Korean density and source grounding are also required.
- If row count drops below 50 or any label drops below 8, open a second meeting cycle for upstream reparse/rechunk/backfill.

## Handoff

Updated handoff: `docs/meetings/phase-2.2-qa-data-2026-06-06-handoff.md`

## Second Meeting Cycle

Trigger: final all-row Source/Data critic returned `REQUEST CHANGES` after positive evidence selection because the remaining bad rows were grounded in polluted `KnowledgeDoc.body` text from CNU HTML navigation/sidebar/page chrome.

Second-cycle verdict:

- Source/Data Steward: `PASS` for moving upstream to HTML main-content extraction.
- Runtime/Architecture Engineer: `REQUEST CHANGES` until extraction is selector-first and dependency-light.
- Evaluation/Validator Engineer: `REQUEST CHANGES` until `KnowledgeDoc.body` gets chrome/content gates.
- Red-Team Critic: `REQUEST CHANGES` until selector order, backfill rules, and upstream gates are explicit.
- Facilitator/Planner: `REQUEST CHANGES` on the current regenerated data; select source-specific DOM extraction as the next handoff.

Second-cycle decision:

1. Do not add `trafilatura` as a base dependency for this phase.
2. Use existing `beautifulsoup4` and `lxml` to extract source-specific main content:
   - `academic_notice_board`: board list rows
   - `academic_calendar`: `.calen_box` schedule content
   - `shuttle_bus`: `#contents .content #txt`
   - `cnu_mobile_food`: `.menu-wr` / `.menu-tbl`
3. Add `KnowledgeDoc.body` chrome/content gates so polluted source text cannot make QA rows look grounded.

Final outcome:

- `data/knowledge_seed.json`: 15 docs, 3 per label.
- `data/qa_seed.json`: 50 rows, 10 per label.
- `data/source_parse_failures.json`: `cnucoop_discovery` excluded because no clean chunk passed quality gates.
- Independent chrome scan: 0 hits in knowledge and QA.
- Final Source/Data critic: `PASS`.
