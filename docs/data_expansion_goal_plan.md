# Data Expansion And RAG Stabilization Goal Plan

작성일: 2026-06-07

## Goal

충남대학교 Campus ChatBot의 병목을 모델이 아니라 데이터 품질/범위/검증 문제로 보고, Task 1/2 우선의 데이터 확장과 RAG 안정화를 하나의 장기 실행 목표로 진행한다.

제외 범위:

- 발표자료 작성.
- 실제 Colab 구동.
- 외부 LLM API, MCP, full tool-call agent를 최종 inference path에 넣는 방식.
- 데이터 부족을 감추기 위한 fallback 답변 품질 주장.

포함 범위:

- Task 1 분류 데이터 확장.
- Task 2 source-backed QA/RAG 데이터 확장.
- Task 3에 재사용 가능한 deterministic crawler/API 기반 최신 정보 수집 경계 설계.
- PDF/HWP/HWPX/HTML 수집 및 파싱.
- 단계별 정량 검증, 실패 기록, 재시도 규칙.

## Current Baseline

현재 저장소 기준:

- raw source: 6 files.
- `data/knowledge_seed.json`: 15 rows.
- `data/qa_seed.json`: 50 rows.
- `data/cls_train_seed.json`: 657 rows.
- local Task 2 backend: `llama.cpp + Qwen3.5-9B Q4_K_M GGUF`, `q8_0` KV cache.
- current bottleneck: repeated model loading, retrieval source quality, source-backed data volume, latest-information crawler boundary.

Interpretation:

- 현재 데이터는 pipeline smoke 수준이다.
- RAG 성능을 주장하기에는 source count와 chunk diversity가 부족하다.
- 다음 목표의 핵심은 더 큰 모델 탐색이 아니라 source-backed corpus 확장과 retrieval/eval gate 강화다.

## External Baseline Used For Scale

이 과제는 BEIR/MS MARCO 같은 공개 검색 벤치마크 규모를 따라갈 필요는 없지만, 규모 감각은 참고한다.

- NVIDIA RAG benchmark는 수천~수만 페이지와 수십~수천 query 단위의 benchmark를 사용한다.
- BEIR의 작은 데이터셋도 수천 corpus document와 수백 query 단위다.
- MS MARCO passage ranking은 대형 benchmark로 수백만 passage/query 단위다.
- Ragas testset generation 흐름은 RAG 평가 질문을 수동으로 대량 작성하기 어렵기 때문에 synthetic QA generation과 검증을 사용한다.

Project-specific target:

| Artifact | Current | Stage 1 minimum | Stage 2 stable target |
| --- | ---: | ---: | ---: |
| raw source URL/file | 6 | 50 | 120 |
| source-backed knowledge chunks | 15 | 300 | 800 |
| Task 2 eval QA | 50 | 150 | 300 |
| Task 1 classification rows | 657 | 1,500 | 2,500 |
| graduation departments | 1 central PDF | 6 departments | 10 departments |

## Source Scope

### Label 0: Graduation Requirements

Priority: highest.

Scope:

- 중앙 교육과정 PDF.
- 학과별 졸업요건 페이지.
- 학과별 PDF/HWP/HWPX 첨부.
- 입학년도/교육과정 연도별 차이.
- 대표 학과 6개부터 시작하고, 안정화 후 10개로 확장한다.

Representative source candidates:

- `https://plus.cnu.ac.kr/html/kr/25file/2025_book.pdf`
- `https://english.cnu.ac.kr/english/edu/undergraduate02.do`
- `https://biochemistry.cnu.ac.kr/biochemistry/info/requirements.do`

Structured fields:

- `department`
- `college`
- `curriculum_year`
- `admission_year`
- `requirement_type`
- `credits`
- `source_file_type`
- `effective_date`
- `source_url`

Stage 1 gates:

- at least 6 departments.
- at least 120 graduation chunks.
- at least 30 graduation QA rows.
- at least 300 graduation classification rows.
- every graduation chunk has one of `department`, `curriculum_year`, or `admission_year`.

### Label 1: Notices

Priority: medium.

Scope:

- 중앙 학사공지 board list/detail.
- department notices only when they support graduation/course/academic tasks.
- recent notices are more valuable than old notices.

Structured fields:

- `notice_title`
- `posted_date`
- `department_or_office`
- `board_name`
- `detail_url`
- `attachment_urls`

Stage 1 gates:

- at least 40 clean notice chunks.
- at least 20 detail pages, not only board list pages.
- zero chunks dominated by page chrome.
- posted date parsed for at least 80% of notice chunks.

### Label 2: Academic Calendar

Priority: high for structured parsing, medium for volume.

Scope:

- official academic calendar page.
- year/semester events.
- date range normalization.

Structured fields:

- `event_name`
- `start_date`
- `end_date`
- `semester`
- `academic_year`
- `source_url`

Stage 1 gates:

- at least 40 calendar chunks/events.
- at least 30 structured date rows.
- every structured row has `start_date`.
- date parser rejects impossible dates.

### Label 3: Dining

Priority: latest information, not historical accumulation.

Scope:

- official or official-chain dining pages.
- current/near-future menu snapshots.
- short TTL cache.

Structured fields:

- `cafeteria`
- `meal_date`
- `meal_type`
- `menu_items`
- `price`
- `source_url`
- `fetched_at`

Stage 1 gates:

- at least 30 current dining rows.
- at least 2 cafeterias if source supports it.
- fetched date recorded for all rows.
- stale rows are excluded from "latest" Task 3 claims unless explicitly described as cached snapshot.

### Label 4: Shuttle

Priority: high for structured parsing.

Scope:

- official shuttle/time-table page.
- route, stop, weekday/weekend, semester/holiday distinctions.
- PDF/HWP attachments if official page points to them.

Structured fields:

- `route_name`
- `stop_name`
- `departure_time`
- `day_type`
- `term_type`
- `source_url`

Stage 1 gates:

- at least 40 shuttle chunks/rows.
- at least 1 route with parsed stops and times.
- every parsed time matches `HH:MM`.
- no final latest claim without official-chain source.

## Architecture Decision

Decision:

- Build deterministic source collection and parsing first.
- Use local LLM for Task 2 natural answer generation after retrieval.
- Keep the LLM's role constrained to answer wording, not source discovery or tool selection.
- For label generation, use self-consistency only during data construction, then store validated labels as deterministic artifacts.

Alternatives considered:

1. Full LLM tool-call agent for Task 3.
   - Rejected for this project stage because the behavior is harder to bound, harder to grade, and unnecessary for fixed campus information domains.

2. Larger local model before data expansion.
   - Deferred because current `Qwen3.5-9B Q4_K_M` fits VRAM and generation works. Current answer errors are more often retrieval/source issues than model capacity issues.

3. Static RAG only.
   - Rejected for dining/shuttle/notices because freshness matters. These domains need deterministic refresh paths and freshness metadata.

Consequences:

- Crawler/parser quality becomes the main engineering work.
- The same raw source inventory should serve Task 1, Task 2, and optional Task 3.
- Fallback answers are allowed only as explicit emergency behavior and must not be used as performance evidence.

## Execution Rules

- Work one step at a time.
- Each implementation step has `max_attempts=3`.
- Every failed attempt records:
  - step id
  - command
  - observed failure
  - suspected cause
  - next change
  - whether a meeting loop was opened
- Failure log path: `docs/data_expansion_failure_log.md`.
- Progress log path: `docs/data_expansion_progress.md`.
- If a critic returns `REQUEST CHANGES`, do not stop by default. Open the 5-agent meeting protocol and produce the next concrete change list.
- If the same step fails 3 times, pause only when the blocker requires user choice, credentials, or an inaccessible external source.
- Commit after each coherent passing work unit.

## Planning Loop

Each phase starts with up to 3 sequential loops:

1. Planner: define files, commands, thresholds, and artifacts.
2. Architect: check source boundaries, entrypoint preservation, overengineering risk, and data leakage risk.
3. Critic: check quantitative gates, anti-gaming checks, freshness claims, and failure logging.

Pass condition:

- Architect verdict is `PASS`.
- Critic verdict is `PASS`.
- If either rejects, revise the phase plan and repeat.

## Phase 0: Baseline And Inventory Reset

### Step 0.1 Repository And Data Snapshot

Work:

- Record current tracked/ignored state.
- Count current raw sources, knowledge docs, QA rows, classification rows by label.

Commands:

```powershell
git status --short --ignored
uv run python -c "import json; from pathlib import Path; paths=['data/knowledge_seed.json','data/qa_seed.json','data/cls_train_seed.json']; [print(p, len(json.loads(Path(p).read_text(encoding='utf-8')))) for p in paths]"
```

Gate:

- tracked dirty files are only files touched by this step.
- baseline counts are recorded in `docs/data_expansion_progress.md`.

### Step 0.2 Source Inventory Schema

Work:

- Extend source inventory from five hardcoded source modules to a declarative inventory.
- Inventory rows include label, domain, URL, source type, freshness policy, parser type, priority, official-chain status, and notes.

Files:

- `docs/source_inventory.md`
- `src/nlp_term/collect/source_inventory.py`
- `src/nlp_term/collect/run_collect.py`

Gate:

- at least 50 Stage 1 source candidates are listed.
- graduation has at least 6 departments.
- every source has parser type among `html`, `board_detail`, `pdf`, `hwp`, `hwpx`, `calendar`, `dining`, `shuttle`.

## Phase 1: Source Discovery And Fetching

### Step 1.1 Graduation Source Expansion

Work:

- Discover and register central curriculum docs and representative department graduation pages/files.
- Include PDF/HWP/HWPX when linked by official department pages.

Gate:

- source probe contains at least 6 graduation departments.
- at least 12 graduation source rows.
- at least one PDF source remains.
- HWP/HWPX attachments are either downloaded or recorded as unsupported/failure with reason.

### Step 1.2 Notices Detail Expansion

Work:

- Fetch board list and detail pages.
- Extract title, date, office, body, attachments.

Gate:

- at least 20 notice detail pages.
- at least 80% have parsed date.
- list-only pages are not counted as detail content chunks.

### Step 1.3 Calendar Structured Fetch

Work:

- Parse academic calendar into date-structured records.

Gate:

- at least 30 structured event rows.
- every row has valid `start_date`.
- event rows can be converted into knowledge chunks.

### Step 1.4 Dining Freshness Fetch

Work:

- Determine official dining source chain.
- Fetch current or near-current menus.
- Store `fetched_at` and freshness TTL.

Gate:

- at least 30 menu rows or a documented source limitation.
- all rows have `fetched_at`.
- rows older than TTL are flagged stale.

### Step 1.5 Shuttle Structured Fetch

Work:

- Parse shuttle route/time information from official page and attachments.

Gate:

- at least 1 route.
- at least 20 stop/time rows.
- every departure time parses as `HH:MM`.

## Phase 2: Parser And Normalization Hardening

### Step 2.1 Document Parser Coverage

Work:

- Strengthen PDF parser for section titles and page spans.
- Add deterministic HWP/HWPX parse fixtures or sample-based checks.

Gate:

- PDF extraction produces section-aware chunks for central curriculum PDF.
- any counted HWP/HWPX source produces text length >= 1,000 or is excluded with failure reason.
- parse failure file is non-silent and machine-readable.

### Step 2.2 HTML And Board Parser Coverage

Work:

- Add source-specific main-content selectors for CNU official pages.
- Remove page chrome and navigation text before chunking.

Gate:

- page-chrome banned term scan returns zero hits in accepted knowledge chunks.
- notice detail parser returns title/body/date for at least 80% of fetched detail pages.

### Step 2.3 Structured Domain Parsers

Work:

- Convert calendar, dining, and shuttle records to both structured rows and natural-language knowledge chunks.

Gate:

- each structured parser writes JSON rows.
- every structured row has source URL and fetched/updated date where applicable.
- structured rows can regenerate knowledge docs deterministically.

## Phase 3: Knowledge Corpus Expansion

### Step 3.1 Stage 1 Knowledge Build

Work:

- Generate source-backed knowledge docs from expanded source probe.

Command:

```powershell
uv run python -m nlp_term.collect.run_collect --fetch --output data/sources/source_probe.json
uv run python -m nlp_term.prepare.from_sources --source-probe data/sources/source_probe.json --output data/knowledge_seed.json --failures-output data/source_parse_failures.json
uv run python -m nlp_term.validators --knowledge-quality data/knowledge_seed.json --source-probe data/sources/source_probe.json --min-docs-per-label 30 --min-body-chars 120 --min-source-parse-ratio 0.9
```

Gate:

- total knowledge docs >= 300.
- docs per label >= 30.
- graduation docs >= 120.
- source-parse ratio >= 0.90.
- no accepted chunk has mojibake/private-use/page-chrome terms.

### Step 3.2 Knowledge Diversity Check

Work:

- Check that chunks are not near-duplicates and not all from one source.

Gate:

- no normalized duplicate body.
- each label has at least 3 source ids.
- graduation has at least 6 departments.
- average chunk length is between 120 and 1,200 characters.

## Phase 4: Data Generation And Label Validation

### Step 4.1 Task 1 Classification Expansion

Work:

- Generate classification examples from source-backed chunks.
- Use self-consistency for label creation during data construction.
- Store final accepted label deterministically.

Gate:

- total classification rows >= 1,500.
- rows per label >= 250.
- ambiguous/adversarial rows per label >= 30.
- zero conflicting duplicate normalized questions.
- zero unvalidated rows.

### Step 4.2 Task 2 QA Expansion

Work:

- Generate source-backed QA pairs.
- Include exact source doc ids and evidence spans.

Gate:

- total QA rows >= 150.
- QA rows per label >= 25.
- graduation QA rows >= 40.
- every QA row has source id and evidence span.
- every answer passes JSON/schema validation.

### Step 4.3 Data Critic Pass

Work:

- Run a data/source critic over sampled and high-risk rows.

Gate:

- sample size >= 50 QA rows or all rows if fewer.
- zero unsupported latest-information claims.
- zero answers based only on stale dining/shuttle source unless explicitly marked stale.

## Phase 5: Retrieval And RAG Evaluation

### Step 5.1 Retrieval Metrics

Work:

- Evaluate retrieval using the expanded QA set.

Command:

```powershell
uv run python -m nlp_term.retrieve.evaluate --knowledge data/knowledge_seed.json --qa data/qa_seed.json --output model/retrieval_metrics.json
uv run python -m nlp_term.validators --retrieval-metrics model/retrieval_metrics.json --knowledge data/knowledge_seed.json --qa data/qa_seed.json --min-top1-label-accuracy 0.80 --min-top3-source-hit-rate 0.75
```

Gate:

- top-1 label accuracy >= 0.80.
- top-3 source hit rate >= 0.75.
- per-label failure counts are recorded.
- graduation top-3 source hit rate >= 0.75.

### Step 5.2 Chunk Ablation

Work:

- Compare current chunking with section-aware chunking and structured-row chunks.

Gate:

- best chunker improves or matches top-3 source hit rate.
- no selected chunker increases page-chrome hits.
- selected chunker is deterministic.

## Phase 6: Task 1 Performance Recheck

Work:

- Retrain classifier on expanded data with source-disjoint split.
- Add harder real-user-like questions.

Gate:

- macro F1 >= 0.70.
- weighted F1 >= 0.70.
- class F1 >= 0.55.
- metrics are source-disjoint and checksum-bound.
- if metrics are too perfect, add anti-gaming diagnostic and harder eval rows before claiming performance.

## Phase 7: Task 2 LLM Answer Path Recheck

Work:

- Use local LLM as primary Task 2 generator.
- Use retrieval context from expanded knowledge.
- Keep fallback minimized and visibly separated from performance evidence.

Gate:

- `chatbot.sh batch` generates valid JSON.
- at least 30 held-out QA prompts are evaluated.
- no malformed JSON output.
- no thinking markers.
- no banned placeholder terms.
- source-alignment critic passes sampled outputs.

## Phase 8: Task 3 Foundation

Work:

- Implement deterministic latest-info modules for domains where freshness matters.
- Keep full tool-call agent out of final inference.

Gate:

- dining rows include `fetched_at` and TTL.
- notice/latest rows include posted date.
- shuttle rows include source freshness.
- realtime output does not claim live freshness when source is stale.

## Phase 9: Final Pre-Colab Readiness

Work:

- Run integrated checks without actual Colab.

Commands:

```powershell
uv run python -m nlp_term.validators --inputs-only --data-dir data --require-realtime
uv run python -m nlp_term.validators --seed-data --data-dir data
uv run python -m nlp_term.validators --dataset-quality --data-dir data --min-cls-rows 1500 --min-cls-per-label 250 --min-qa-rows 150 --min-qa-per-label 25 --require-qa-source --require-validated --no-dry-run
uv run python -m nlp_term.validators --final-readiness --outputs-dir outputs
```

Gate:

- all commands exit 0.
- no final output depends on external LLM API.
- model backend decision is documented.
- remaining Colab-only risks are listed separately.

## Round 1 Planner Review

Verdict: `REVISE`

Findings:

- Initial plan must distinguish current smoke data from Stage 1 target data.
- Graduation requirements need highest priority and department/year structure.
- Dining should not be treated as historical RAG corpus; freshness is the core requirement.
- Task 3 should reuse deterministic source modules, not an autonomous tool-calling agent.

Applied changes:

- Added Stage 1 and Stage 2 target counts.
- Added graduation-specific metadata and gates.
- Added freshness gates for dining/shuttle/notices.
- Added deterministic Task 3 foundation phase.

## Round 1 Architect Review

Verdict: `PASS WITH CHANGES`

Findings:

- The plan preserves `src/classifier.ipynb` and `chatbot.sh`.
- A declarative source inventory is needed so collectors do not become scattered hardcoded modules.
- Structured rows and knowledge chunks should coexist. Calendar/dining/shuttle need structured JSON first, then natural-language chunks.
- The LLM should not own source discovery.

Applied changes:

- Added `src/nlp_term/collect/source_inventory.py`.
- Added structured parser outputs for calendar, dining, and shuttle.
- Clarified LLM role as answer wording only.

## Round 1 Critic Review

Verdict: `REVISE`

Findings:

- "More data" alone can inflate corpus size with duplicates and page chrome.
- The plan needs anti-gaming checks for near-duplicates, stale latest claims, and overly perfect generated classification metrics.
- Failure logging and retry rules should be explicit.

Applied changes:

- Added duplicate/body diversity gate.
- Added stale-source and unsupported latest-claim gates.
- Added failure log schema and max-attempt rules.
- Added anti-gaming note for overly perfect Task 1 metrics.

## Round 2 Planner Review

Verdict: `PASS`

Reason:

- The plan now has a clear data-first execution path, target counts, source scope, and phase gates.

## Round 2 Architect Review

Verdict: `PASS`

Reason:

- The plan keeps runtime boundaries simple: deterministic collectors/parsers, shared knowledge runtime, local LLM generation, no autonomous inference-time tool agent.

## Round 2 Critic Review

Verdict: `PASS`

Reason:

- Each phase has machine-checkable acceptance criteria or an explicit new validator requirement.
- Failure handling and re-review loops are defined.

## Execution Handoff

Recommended next command is not a shell command; it is the next implementation goal:

> Implement Phase 0 and Phase 1.1 first: reset source inventory, add declarative source candidates, expand graduation source discovery to at least 6 representative departments, and verify source probe coverage.

First passing work unit should commit with:

```text
feat: expand source inventory for data growth
```
