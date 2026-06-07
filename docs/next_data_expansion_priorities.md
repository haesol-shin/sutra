# Next Data Expansion Priorities

작성일: 2026-06-07

## Scope

이 문서는 Goal 2.3 진단 결과를 바탕으로 다음 데이터 확장 순서를 정한다. 지금 단계의 목적은 데이터를 바로 늘리는 것이 아니라, 어떤 데이터를 먼저 늘려야 Task 1, Task 2, Optional Task 3의 generalization 위험을 줄일 수 있는지 정하는 것이다.

## Current Baseline

baseline:

- Task 1 gold set: 50 rows, 10 rows per label
- Task 1 current gold macro F1: `0.8385`
- Task 1 current gold weighted F1: `0.8385`
- Task 1 observed gold errors: 8
- Task 1 largest issue group: label-boundary ambiguity 3, classifier feature/model limitation 3, data coverage shortage 2
- Task 2 answer gold set: 25 rows
- Task 2 deterministic fact recall: `0.80`
- Task 2 deterministic naturalness heuristic pass rate: `0.24`
- Task 2 deterministic source hint rate: `0.76`
- Task 2 llama sample size: 3 rows
- Task 2 llama sample naturalness heuristic pass rate: `1.0`
- Task 2 llama sample source hint rate: `0.0`
- Retrieval fact-probe hit@1: `0.60`
- Retrieval fact-probe hit@3: `1.0`
- Current knowledge docs: 53

These numbers are small-set diagnostics. They are useful for direction, but they are not final performance or generalization evidence.

## Priority 1: 졸업요건, 교육과정, PDF/HWP

Why first:

- The user explicitly flagged 졸업요건, representative departments, yearly curriculum differences, PDF, and HWP as important.
- Task 1 error analysis found data coverage shortage around graduation/curriculum-like boundaries.
- Graduation answers are high-impact for students and easy to make wrong if year, department, or curriculum document is missing.

Target sources:

- university-wide graduation requirement pages
- representative department graduation pages
- yearly curriculum PDF/HWP files
- department curriculum tables where available
- source metadata for department, curriculum year, parser type, and document year

acceptance gate:

- at least 5 representative departments covered
- at least 3 curriculum years covered where source pages provide them
- PDF/HWP parser output has no mojibake/private-use glyph scan hits
- every graduation/curriculum knowledge doc has department/year/parser metadata when applicable
- add at least 25 new Task 1 gold-like questions and 25 new Task 2 fact candidates from these sources before claiming improvement

Expected metric movement:

- Task 1 boundary errors around graduation versus notices/calendar should become easier to inspect.
- Task 2 should get more realistic grounding for 졸업요건 answers.
- Retrieval hit@3 may remain high on fact probes, so realistic user-query tests must be added too.

## Priority 2: 학사일정과 날짜 구조화

Why second:

- Retrieval fact-probe top1 is weakest for label 2 at `0.4`.
- 학사일정 often overlaps with notices and shuttle wording, which already caused Task 1 confusion.
- Date answers need structured extraction so the LLM does less guessing.

Target sources:

- official academic calendar pages
- semester-specific course registration pages if available
- leave/return, registration, exam, and graduation event dates

acceptance gate:

- store normalized date spans where source text allows it
- preserve source URL and fetched date
- create label 2 adversarial Task 1 examples that distinguish calendar from notices
- add Task 2 answer gold rows for at least 10 date questions with expected fact IDs

Expected metric movement:

- improve label 2 top1 retrieval stability
- reduce Task 1 false positives into label 2
- make Task 2 calendar answers less dependent on free-form generation

## Priority 3: 공지사항 Source Breadth

Why third:

- Notices are broad and can easily dominate search if collected naively.
- They are important, but less stable than graduation/curriculum documents.
- The priority is representative breadth, not unlimited crawling.

Target sources:

- central academic notices
- scholarship/course notices only if they map clearly to assignment labels
- optional representative department notices if source volume is manageable

acceptance gate:

- crawl source inventory before adding rows
- keep notice docs deduplicated by URL/title/date
- add boundary examples for notice versus calendar
- prevent notice docs from swallowing graduation/curriculum queries in retrieval diagnostics

Expected metric movement:

- better Task 1 label 1 coverage
- clearer boundaries between label 1 and label 2

## Priority 4: 식단 최신성

Why fourth:

- Dining is freshness-sensitive.
- Old menus are less useful than a stable current parser and provenance path.

Target sources:

- official cafeteria/menu page
- date, meal type, location, menu items

acceptance gate:

- current-week or current-day extraction path documented
- stale menu rows marked clearly
- Task 2 responses do not imply old menus are current

Expected metric movement:

- better Task 2 freshness behavior
- prepares Optional Task 3 if realtime data is attempted

## Priority 5: 셔틀 시간표와 Optional Task 3 Hooks

Why fifth:

- Shuttle information often has a dedicated page and may be handled with deterministic lookup.
- Optional Task 3 can benefit from a crawler/API-style function without making the LLM a full tool-call agent.

Target sources:

- official shuttle/bus timetable pages
- route, stop, departure time, weekday/weekend metadata

acceptance gate:

- parse route and time table into structured rows
- add deterministic lookup tests before asking the LLM to verbalize answers
- keep out-of-scope route questions marked unknown instead of hallucinated

Expected metric movement:

- stronger Task 2 answers for shuttle questions
- clear path to Optional Task 3 without full LLM tool-call autonomy

## Engineering Order

1. Build source inventory for Priority 1 only.
2. Add parser fixtures for HTML, PDF, and HWP-like outputs where available.
3. Add validator gates for metadata, Korean text quality, source URL, and row counts.
4. Generate LLM-assisted labels with self-consistency, then run deterministic structure validation.
5. Add human review queue for low-confidence or boundary examples.
6. Re-run Task 1 gold and Task 2 gold answer diagnostics.
7. Only after source expansion stabilizes, revisit embedding RAG, cross-encoder reranking, or llama answer formatting.

## Do Not Do Yet

- Do not claim final performance from the current high Task 1/Task 2 numbers.
- Do not optimize the classifier before expanding and auditing data.
- Do not add embedding RAG until there is enough source breadth to make retrieval comparison meaningful.
- Do not use external LLM API at inference time.
- Do not use deterministic fallback as evidence for llama quality.
