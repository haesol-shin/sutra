# 5-Agent Request-Changes Meeting Protocol

작성일: 2026-06-06

이 문서는 `REQUEST CHANGES` 또는 반복 실패가 발생했을 때 작업을 멈추지 않고, 근거 기반 5-agent 회의로 다음 방향을 정하는 운영 규칙이다.

## Research Grounding

- Nominal Group Technique: silent idea generation, round-robin sharing, clarification, ranking.
- Delphi method: iterative expert feedback with predefined stopping criteria.
- Premortem/prospective hindsight: assume the selected direction failed, then identify likely causes.
- Red-team/devil's advocacy: fixed adversarial role to reduce groupthink.
- Multi-agent debate: useful for blind-spot discovery, but source-backed artifacts and deterministic validators outrank agent agreement.

References:

- ASQ, Nominal Group Technique: https://asq.org/quality-resources/nominal-group-technique
- Praxis Framework, Nominal Group Technique: https://www.praxisframework.org/en/library/nominal-group-technique
- Delphi method overview: https://en.wikipedia.org/wiki/Delphi_method
- Gary Klein, Performing a Project Premortem: https://hbr.org/2007/09/performing-a-project-premortem
- Du et al., Improving Factuality and Reasoning in Language Models through Multiagent Debate: https://arxiv.org/abs/2305.14325
- Multi-Agent Wiki, Debate/Judge/Voting: https://multi-agent.wiki/patterns/debate-judge

## Trigger Conditions

Open a meeting when any of these happens:

1. Planner, architect, critic, verifier, code-reviewer, or test-engineer returns `REQUEST CHANGES`.
2. The same step fails twice, even if the local `max_attempts` is three.
3. A deterministic validator passes but a qualitative reviewer finds a project-risking quality failure.
4. A source/data bottleneck blocks Task 1 or Task 2 progress.
5. External factual uncertainty blocks a decision about CNU sources, parsing behavior, package compatibility, or assignment interpretation.

Do not open a meeting for simple syntax/import/lint/path failures when the fix is obvious and already covered by the accepted plan.

## Fixed Roles

1. Facilitator/Planner: owns packet, timebox, dashboard, handoff, and scope control.
2. Source/Data Steward: owns provenance, data construction, data quality, parsing, and evidence sufficiency.
3. Runtime/Architecture Engineer: owns entrypoints, module boundaries, Windows/uv compatibility, and final inference constraints.
4. Evaluation/Validator Engineer: owns deterministic gates, anti-gaming checks, commands, and failure logs.
5. Red-Team Critic: owns premortem, devil's advocacy, leakage checks, and groupthink detection.

## Evidence Packet

Before Round 1, create `docs/meetings/{meeting_id}-evidence.md` with:

- meeting id, opened date, trigger verdict, step id, phase, attempt count
- exact failing review text or command output summary
- relevant local files and artifact paths
- current command pass/fail status
- assignment constraints and current priority
- research used

When source/data quality blocks progress, research is required. The packet must include URLs or local artifact paths plus access date. Internet research is required when the bottleneck depends on current packages, public source behavior, current model/tooling behavior, or published methodology.

## Meeting Rounds

Round 0: Gate and Packet Check
- Confirm trigger is valid and packet has enough evidence.
- If a missing local command would materially affect the decision, run it before Round 1.

Round 1: Silent Proposal Generation
- Each role independently proposes one or two next directions.
- Each proposal must include affected files, expected artifact change, gate, and stop condition.

Round 2: Round-Robin Sharing
- Facilitator records one proposal per role per pass.
- No debate except factual clarification.

Round 3: Clarification and Evidence Binding
- Classify proposals as executable now, needs local inspection, needs internet/research, blocked by user priority, or invalid.
- Evaluation/Validator Engineer attaches the smallest deterministic gate or review checklist.

Round 4: Premortem and Red-Team
- Assume the top two proposals failed.
- Red-Team Critic lists likely causes.
- Source/Data Steward and Evaluation/Validator Engineer convert credible causes into guardrails.

Round 5: Ranking
- Each role scores surviving proposals from 1 to 5 on:
  - restores forward progress
  - protects assignment scope
  - improves evidence quality
  - has deterministic verification
  - limits implementation blast radius
- Record total and median score.

Round 6: Decision and Handoff
- Select a single top-ranked proposal if it satisfies decision rules.
- Write `docs/meetings/{meeting_id}-handoff.md` with exact files, commands, gates, owner role, and stop condition.

Round 7: Protocol Validation
- Changes to this protocol require Planner -> Critic validation up to three iterations.
- The validation record must be tracked in `docs/meetings/protocol-validation-*.md`.

## Decision Rules

1. Source-backed evidence beats agent consensus.
2. Deterministic validators beat LLM judge agreement for verifiable tasks.
3. Final inference must not depend on external LLM APIs, MCP, or tool-call agents.
4. Task 1/2 cannot be weakened to improve Optional Task 3.
5. A proposal cannot pass if it leaves the same failure unlogged.
6. If top-ranked proposals differ by fewer than three total points, choose lower blast radius unless Source/Data Steward vetoes it.
7. Qualitative source/data concerns must become either validator checks or explicit critic checklist items.

## Dashboard

Maintain `docs/meeting_room_dashboard.md` with one entry per meeting:

- meeting_id
- opened_at
- trigger_type
- phase
- step_id
- request_changes_source
- attempt_count
- status
- current_blocker
- research_used
- candidate_options
- selected_option
- decision_rule_used
- validator_gate
- review_gate
- commands_to_run
- artifacts_to_update
- failure_log_entry_required
- next_owner
- handoff_path
- closed_at
- outcome

## Stopping Criteria

Close the meeting when:

- one next direction is selected
- owner, artifact list, commands, validation gate, review gate, and stop condition are recorded
- dashboard status is `handoff_ready`, `closed`, or `blocked`

Escalate to the user when:

- viable options change assignment priorities
- viable options require paid/credentialed external services
- two consecutive meeting cycles produce no executable option
- Optional Task 3 would delay Task 1/2 readiness

## Current Phase 2.2 Handling

For `phase-2.2-qa-dataset-generation`, use the meeting protocol because the final critic loop still found QA data pollution even though scripted gates passed.

Recommended initial option:

- Implement positive evidence span selection instead of extending deny-lists.
- Exclude polluted source chunks from QA generation when no clean source-specific span is available.
- Strengthen validator checks against generic fallback evidence and case-insensitive boilerplate.
- Regenerate QA and require one Source/Data critic pass before Phase 2.2 is unblocked.
