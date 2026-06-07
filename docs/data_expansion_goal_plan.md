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

| Artifact | Current | Stage 0 serial gate | Stage 1 minimum | Stage 2 stable target |
| --- | ---: | ---: | ---: | ---: |
| raw source URL/file | 6 | 8-12 | 50 | 120 |
| source-backed knowledge chunks | 15 | 50 | 300 | 800 |
| Task 2 eval QA | 50 | 50 source-checked | 150 | 300 |
| Task 1 classification rows | 657 | 700 source-checked | 1,500 | 2,500 |
| graduation departments | 1 central PDF | 1-2 departments | 6 departments | 10 departments |

## Execution Strategy: Serial First, Parallel Later

The first execution stage must prove the whole pipeline on a very small source set before broad crawling begins.

Stage 0 is deliberately small:

- graduation: central curriculum PDF plus 1-2 representative department sources.
- notices: board list plus 3-5 detail pages.
- academic calendar: one official calendar page.
- dining: one current official or official-chain menu source.
- shuttle: one official timetable source.

Stage 0 pass means:

- raw source snapshots are saved with checksums.
- parsed text is clean enough to produce accepted chunks.
- chunks preserve metadata needed by the task, such as department, year, date, meal, route, or source URL.
- QA/evidence rows can be generated deterministically from the chunks.
- lexical retrieval can find the intended label/source on the small QA set.
- local LLM generation produces valid JSON and does not contradict the retrieved evidence in sampled checks.
- every failure is logged and can be retried without manual state cleanup.

Only after Stage 0 passes should the project move to Stage 1 broad source discovery. Only after Stage 1 passes should source collection be parallelized by domain.

Parallelization rule:

- Do not parallelize a parser or crawler family until one source in the same family has passed fetch, parse, chunk, QA, retrieval, and answer-generation checks.
- Parallel workers may expand different domains only after their shared schema and validator gates are fixed.
- If parallel expansion introduces repeated parse failures or page-chrome contamination, return to the serial loop for that domain.

RAG engineering order:

1. crawl and parse official sources.
2. create clean chunks and evidence-bearing QA rows.
3. run metadata-aware lexical retrieval as the first baseline.
4. compare embedding retriever on the same QA set.
5. compare embedding retriever plus reranker only after baseline retrieval metrics exist.
6. adopt embedder/reranker only if measured source hit rate or answer critic pass rate improves enough to justify latency and dependency cost.

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
- Mark each source with `stage`: `stage0`, `stage1`, or `stage2`.
- Mark whether a source is active for the current serial loop or only a later expansion candidate.

Files:

- `docs/source_inventory.md`
- `src/nlp_term/collect/source_inventory.py`
- `src/nlp_term/collect/run_collect.py`

Gate:

- at least 8 and at most 12 Stage 0 active source candidates are listed.
- Stage 0 includes all five labels.
- Stage 0 graduation includes the central curriculum PDF plus 1-2 department sources.
- Stage 1 may list at least 50 later source candidates, but Stage 1 candidates are not fetched until Stage 0 passes.
- every source has parser type among `html`, `board_detail`, `pdf`, `hwp`, `hwpx`, `calendar`, `dining`, `shuttle`.

## Phase 1: Source Discovery And Fetching

### Step 1.1 Stage 0 Serial Source Loop

Work:

- Fetch and parse only the Stage 0 active source set.
- Run the full loop serially: fetch, parse, chunk, QA generation, retrieval smoke, and LLM batch smoke.
- Fix parser/schema problems before adding more sources.

Gate:

- source probe contains 8-12 active Stage 0 sources.
- all five labels are represented.
- graduation contains central curriculum PDF plus 1-2 department sources.
- total source-backed knowledge docs >= 50.
- every active source either produces at least one accepted chunk or appears in the parse-failure log with a concrete reason.
- retrieval smoke over Stage 0 QA records top-3 source hit rate.
- `chatbot.sh batch` produces valid JSON on Stage 0 test prompts.

### Step 1.2 Graduation Source Expansion

Work:

- After Stage 0 passes, discover and register central curriculum docs and representative department graduation pages/files.
- Include PDF/HWP/HWPX when linked by official department pages.

Gate:

- source probe contains at least 6 graduation departments.
- at least 12 graduation source rows.
- at least one PDF source remains.
- HWP/HWPX attachments are either downloaded or recorded as unsupported/failure with reason.

### Step 1.3 Notices Detail Expansion

Work:

- Fetch board list and detail pages.
- Extract title, date, office, body, attachments.

Gate:

- at least 20 notice detail pages.
- at least 80% have parsed date.
- list-only pages are not counted as detail content chunks.

### Step 1.4 Calendar Structured Fetch

Work:

- Parse academic calendar into date-structured records.

Gate:

- at least 30 structured event rows.
- every row has valid `start_date`.
- event rows can be converted into knowledge chunks.

### Step 1.5 Dining Freshness Fetch

Work:

- Determine official dining source chain.
- Fetch current or near-current menus.
- Store `fetched_at` and freshness TTL.

Gate:

- at least 30 menu rows or a documented source limitation.
- all rows have `fetched_at`.
- rows older than TTL are flagged stale.

### Step 1.6 Shuttle Structured Fetch

Work:

- Parse shuttle route/time information from official page and attachments.

Gate:

- at least 1 route.
- at least 20 stop/time rows.
- every departure time parses as `HH:MM`.

## Phase 2: Parser And Normalization Hardening

Phase 2의 핵심은 source별 parser가 structured rows와 natural-language knowledge chunks를 함께 만들도록 고정하는 것이다. fixed-window chunk만으로는 표 행, 날짜 범위, 학과/입학연도 조건, 식당/끼니 정보가 서로 다른 chunk로 갈라질 수 있다.

Source-specific parser contract:

| Source family | Primary output | Knowledge chunk policy | Required metadata |
| --- | --- | --- | --- |
| Graduation HTML/PDF/HWP/HWPX | requirement rows when possible; otherwise section text | heading/section-aware chunks; preserve department, curriculum year, admission year, requirement type, and nearby credit values together | `department`, `curriculum_year`, `admission_year`, `requirement_type`, `source_file_type`, `page_span` or `section_title` |
| Academic calendar | event rows | one event or adjacent related events per chunk; never split event name from date range | `event_name`, `start_date`, `end_date`, `academic_year`, `semester` |
| Notice board list/detail | notice detail rows | one notice detail per chunk; list pages are navigation evidence only unless titles/dates are parsed into rows | `notice_title`, `posted_date`, `department_or_office`, `board_name`, `detail_url`, `attachment_urls` |
| Dining | menu rows | one date/location/meal snapshot per chunk generated from structured rows | `meal_date`, `cafeteria`, `meal_type`, `menu_items`, `price`, `fetched_at` |
| Shuttle | route/stop/time rows | one route or timetable block per chunk; keep stop names and departure times together | `route_or_stop`, `departure_time`, `operation_date` or `effective_date`, `timetable_url` |

Chunking policy:

- Prefer source-specific structured rows when the source is naturally tabular or time-sensitive.
- Preserve domain-specific atomic units before recursive splitting. Recursive section-aware text splitting is preferred only for prose documents.
- Use fixed-size sliding windows only as a fallback when no paragraph, heading, row, or sentence boundary can be detected.
- Preserve tables by row or logical block before applying character limits.
- Keep deterministic provenance in every `KnowledgeDoc`: `chunking_strategy`, `chunk_index`, `char_start`, `char_end`, and source checksum when available.
- A source-specific parser is not considered ready until one source in that family passes fetch, parse, chunk, QA, retrieval, and answer-generation smoke.

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

### Step 5.0 Retrieval Basis Decision

Decision:

- Initial RAG retrieval basis is metadata-aware lexical retrieval.
- Use character n-gram TF-IDF or BM25-style scoring as the first baseline because it is deterministic, fast, and easy to debug.
- Apply metadata filters/boosts for label, department, curriculum year, date, freshness, cafeteria, route, and source type when those fields exist.
- Do not introduce a vector database before Stage 0 passes.
- Do not introduce a reranker before baseline retrieval metrics exist.

Adoption gate for embedding/reranker:

- embedding retrieval must improve top-3 source hit rate by at least 5 percentage points, or materially reduce per-label failures, on the same QA set.
- reranker must improve source hit rate or source-alignment critic pass rate enough to justify added latency.
- if lexical retrieval already passes gates and embedding/reranker adds complexity without clear gain, keep lexical for the next milestone.

### Step 5.1 Retrieval Metrics

Work:

- Evaluate retrieval using the Stage 0 QA set first, then the expanded QA set.

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

### Step 5.3 Embedder And Reranker Experiment

Work:

- Compare lexical baseline, embedding retriever, and embedding retriever plus reranker on the same QA/evidence set.
- Keep this as an experiment until the measured improvement justifies the dependency and latency.

Gate:

- metrics file contains all compared retrieval modes.
- every mode uses the same knowledge checksum and QA checksum.
- embedding mode improves top-3 source hit rate by at least 5 percentage points or documents why it is not adopted.
- reranker mode records candidate count, latency, and source hit rate change.
- adopted mode is documented as the Task 2 retrieval default; rejected modes remain documented as experiments.

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

## Round 3 Planner Review

Verdict: `REVISE`

New discussion input:

- Do not begin with broad crawling.
- First prove a minimal serial loop works end to end.
- After the structure is trusted, expand and parallelize by domain.
- Decide the RAG basis explicitly.
- Keep embedder/reranker as measured experiments, not default complexity.

Findings:

- The previous Stage 1 target was useful as a scale target, but it appeared too early in the execution handoff.
- A large source inventory before parser confidence can hide bugs and duplicate page-chrome noise.
- RAG engineering before clean source/evidence data would make retrieval failures hard to diagnose.

Applied changes:

- Added Stage 0 serial gate.
- Added serial-first, parallel-later execution strategy.
- Changed first source work unit from broad graduation expansion to Stage 0 serial source loop.
- Added retrieval basis decision and embedder/reranker adoption gates.

## Round 3 Architect Review

Verdict: `PASS`

Reason:

- The revised sequence reduces architectural risk by proving one source family before multiplying it.
- The collector/parser boundary remains deterministic.
- Metadata-aware lexical retrieval is an appropriate first runtime because it preserves debuggability.
- Embedding and reranking are still included, but only after a stable QA/evidence benchmark exists.

## Round 3 Critic Review

Verdict: `PASS`

Reason:

- The revised plan has a smaller first gate and clearer stop conditions.
- The plan now prevents premature parallelization.
- The plan avoids declaring RAG quality before source coverage, evidence spans, and retrieval metrics exist.
- The plan includes an explicit measurement threshold for adopting embedder/reranker.

## Execution Handoff

Recommended next command is not a shell command; it is the next implementation goal:

> Implement Phase 0 and Phase 1.1 first: reset source inventory, add declarative stage-aware source candidates, run the small Stage 0 serial source loop across all five labels, and verify fetch/parse/chunk/QA/retrieval/chat smoke before broad expansion.

First passing work unit should commit with:

```text
feat: add stage-aware source inventory
```
