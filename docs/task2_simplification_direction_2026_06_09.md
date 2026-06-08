# Task 2 Simplification Direction

Date: 2026-06-09

This note records the current direction after the complexity audit. Older detailed plans under `docs/superpowers/plans/` remain useful as history, but they should not be executed as-is if they conflict with this note.

## Decision

Do not restart the implementation from scratch. Keep the useful existing assets and simplify the active Task 2 path.

The target path is:

```text
question -> retrieve relevant evidence -> build evidence context -> prompt Qwen -> return answer with trace
```

The project should win by giving Qwen clean, official, relevant evidence. The implementation should avoid policy-heavy front-end logic that blocks or rewrites Qwen's behavior before generation.

## Concrete Implementation Rules

- Retrieval may use Task 1 output as a domain hint, but generation must not be blocked by mechanical answer-kind routing.
- The only normal pre-generation block is empty evidence: if no evidence items can be built, return the minimal insufficient-evidence answer.
- Answer validation is diagnostic. It may record internal leaks, unsupported claims, or raw JSON in trace, but it should not replace a generated Qwen answer unless the answer is empty/unusable.
- Retrieval ranking should not call the Task 1 classifier internally. If a route/domain is needed, pass it explicitly from the caller or handle it outside ranking.
- Route/domain should be a retrieval preference, not a hard blocker. Keep sufficiently scoring candidates across labels, then sort route-matching evidence first instead of discarding cross-label evidence. If no candidate reaches the relevance floor, route-matching docs may still be used as sparse domain evidence.
- Date handling is prompt context only: current date, timezone, original expression, and exact resolved date/period when available.
- Plain/recursive chunking means paragraph -> sentence -> fixed-size split in source order, without domain keyword scoring, confidence labels, or hidden quality classes.
- Source-specific parsing is allowed only when the source has explicit structure such as tables, list rows, menus, route tables, or board rows.

## Keep

- Source collection and official-source tracking.
- Explicit source-structured rows from tables, lists, or stable page structure.
- Plain text chunks from prose sources.
- Evidence-pack construction as a lightweight formatting layer.
- Qwen/llama backend execution.
- Probe runners that evaluate the active Qwen evidence path.

## Remove Or Quarantine

- Tool-use and single-tool experiment paths from active runtime code.
- Mechanical answer-kind routing that gates generation.
- Temporal confidence and retrieval-policy classifiers.
- Evidence sufficiency policy that blocks answers beyond empty/no-evidence cases.
- Duplicate classification inside retrieval ranking.
- Graduation prose-to-structured-row extraction.
- Chunk confidence labels or keyword-derived quality labels.
- Validator behavior that turns otherwise natural answers into fail-closed outputs unless the evidence is truly empty or unusable.

## Date Handling

Use date handling as context, not as a policy gate.

The prompt should receive:

- Current date.
- Timezone.
- Resolved relative date or period when it can be computed exactly.
- The original user wording when useful.

This follows the general pattern used by modern LLM systems: dynamic runtime facts such as current date are injected into the model context, while durable behavior rules remain in the system/developer prompt.

## Aggregate Rows

Aggregate rows are allowed when they are useful answer-sized evidence units, such as weekly dining bundles or route-level shuttle summaries.

They must be clearly marked as derived bundles, not source-native structured facts.

Required metadata:

- `generation_method`: a value that distinguishes derived bundles from source-native rows.
- `row_type`: the bundle type, such as `dining_weekly_menu`.
- Original source identifiers or URLs used to create the bundle.
- Bundle scope, such as date range, cafeteria, route name, semester, or month.
- Enough provenance for the answer trace to show where the bundle came from.

This metadata is necessary. Without it, Qwen and the developer cannot tell whether the evidence came directly from an official source row or from a local composition step.

## Chunking Direction

Structured sources should use source-specific parsers only when the source structure is explicit.

General prose should use simple recursive/plain chunking. Domain-specific chunking is acceptable only when it preserves source structure without adding confidence scores or hidden quality classifications.

## Source Inventory Direction

Source inventory should list where data can be collected from. Active runtime sources and exploratory candidate sources should be separated so the build path is easy to reason about.

## Build Direction

Build scripts should be deterministic. They should not silently reuse old generated `source_parse` artifacts. Source-backed knowledge should be rebuilt explicitly from the current source probe when requested.
