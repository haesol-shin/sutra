# Handoff: phase-2.2-qa-data-2026-06-06

## Meeting Verdict

Implement positive evidence span selection for QA generation, but only after hardening the handoff with concrete thresholds and deterministic gates.

Five-agent meeting result:

- Source/Data Steward: `REQUEST CHANGES`
- Runtime/Architecture Engineer: `PASS/WATCH`
- Evaluation/Validator Engineer: `REQUEST CHANGES`
- Red-Team Critic: `REQUEST CHANGES`
- Facilitator/Planner: `PASS`

Decision: proceed with the same direction, revised into a stricter implementation spec before execution.

## Rationale

The previous deny-list approach passed scripted validators but failed critic review because polluted source text kept appearing in new forms. The next step should select clean, source-specific evidence spans positively rather than only deleting known bad terms.

## Files

- `src/nlp_term/prepare/qa_data.py`
- `src/nlp_term/validators.py`
- `data/qa_seed.json`
- `docs/pre_colab_progress.md`
- `docs/pre_colab_failure_log.md`

## Implementation Direction

1. Add positive evidence span selection before row creation:
   - candidate span length: at least 40 characters after whitespace normalization
   - Korean density: at least 20 Hangul characters
   - source grounding: quoted evidence must be token-supported by the linked `KnowledgeDoc.body`
   - label relevance: at least one label-specific keyword from the table below
   - negative filter: no case-insensitive boilerplate, no mojibake/private-use glyphs, no generic fallback phrase

2. Exclude unusable chunks from QA generation when no clean span exists.

3. Keep the row gate:
   - at least 50 QA rows total
   - at least 8 QA rows per label
   - all rows source-linked and validated

4. Strengthen validators:
   - reject generic fallback evidence phrase
   - reject case-insensitive boilerplate variants
   - reject broader mojibake fragments
   - reject rows whose quoted evidence is too short, low-Hangul, or not source-specific

## Label Keyword Sets

- label 0 graduation: `졸업`, `교양`, `전공`, `학점`, `교육과정`, `이수`
- label 1 notice: `공지`, `학사정보`, `게시`, `백마광장`
- label 2 academic calendar: `학사일정`, `일정`, `학기`
- label 3 dining: `식단`, `메뉴`, `학생회관`, `조식`, `중식`, `석식`
- label 4 shuttle: `셔틀`, `버스`, `통학`, `시간표`, `운행`

## Negative Patterns

Reject any generated QA answer or quoted evidence containing these terms case-insensitively:

- `본문 바로가기`
- `사이드메뉴`
- `주요메뉴`
- `통합검색`
- `사이트맵`
- `CNU홍보`
- `홍보동영상`
- `홍보브로슈어`
- `사이버투어`
- `캠퍼스투어`
- `대학/대학원`
- `열기 버튼`
- `닫기버튼`
- `All Rights Reserved`
- `The Strong CNU`
- `Login`
- `ENG`
- `자료를 우선 확인해야 합니다.`
- `공식 source에서 확인한 해당 주제의 안내 범위와 근거`

Reject mojibake/private-use characters including observed fragments from the failed review: `泲`, `湮`, `ȯ`, `մ`, `ϴ`, `б`, `տ`, `α`, `ø`, `ũ`, `Ĵ`, `�`, and Unicode private-use glyphs.

## Pre-Generation Report

Before accepting regenerated QA data, produce or inspect a report with:

- usable clean spans per label
- rejected docs/spans with reasons
- projected QA row count per label
- whether any label depends on fallback or polluted chunks

No fallback or synthesized evidence row may count as source-backed QA data.

## Commands

- `uv run python -m nlp_term.prepare.build_all --output-dir data`
- `uv run python -m nlp_term.validators --dataset-quality --data-dir data --min-qa-rows 50 --min-qa-per-label 8 --require-qa-source --require-validated --no-dry-run`
- `uv run python -m nlp_term.validators --seed-data --data-dir data`
- `uv run python -m compileall src\nlp_term\prepare src\nlp_term\validators.py`
- `uv run ruff check src\nlp_term\prepare src\nlp_term\validators.py`

## Review Gate

After commands pass, run one Source/Data critic over all generated QA rows, not only a sample. The critic must verify:

- no navigation/header/footer text
- no mojibake or private-use glyphs
- no generic fallback excerpt
- quoted evidence is specific to the assigned label
- `source_doc_id` and `source_url` match the linked source

The critic must return `PASS` before Phase 2.2 is unblocked.

## Stop Condition

Open a second meeting cycle if positive evidence selection cannot keep at least 50 QA rows and at least 8 rows per label. The second cycle should consider upstream reparse/rechunk/backfill rather than more deny-list expansion.

## Final Resolution

The stop condition was reached during execution because positive evidence selection exposed polluted upstream HTML chunks. A second meeting cycle selected source-specific DOM main-content extraction and knowledge-body validation gates.

Final verified state:

- source-specific HTML extraction implemented with existing `beautifulsoup4`/`lxml`
- `KnowledgeDoc.body` validation rejects page chrome, mojibake, private-use glyphs, and missing source-specific signals
- `data/knowledge_seed.json`: 15 docs, 3 per label
- `data/qa_seed.json`: 50 rows, 10 per label
- final Source/Data critic reviewed all QA rows and returned `PASS`
