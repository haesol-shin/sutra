# Source Data Expansion First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand official/source-backed campus data before further harness tuning, then produce reviewable raw, parsed, and summary artifacts for dining, shuttle, academic calendar, and graduation requirements.

**Architecture:** Keep collection deterministic. Fetch official or official-chain sources into raw snapshots, parse each domain into structured rows first, then regenerate natural-language knowledge chunks from those rows. Do not ask Qwen to discover or repair missing source facts.

**Tech Stack:** Python 3.10.12, uv, requests, BeautifulSoup/lxml, existing `RawSource`/`KnowledgeDoc` schemas, pytest.

---

## Decision

Data expansion is now the next improvement priority.

Reason:

- The latest Qwen baseline showed that several failures are caused by missing or weak evidence, not generation capacity.
- Dining and shuttle data already exist on official or official-linked pages, but the current parser mostly treats them as generic HTML chunks.
- Academic-calendar exact lookup should still be implemented later, but structured calendar data should come first.
- Graduation questions need central + department-specific sources; otherwise general questions can retrieve unrelated department pages.

## Critic Revision

The first version of this plan was too broad because it proposed adding more active Stage 0 sources while the repository already has 10 active Stage 0 sources. The revised execution sequence is:

1. **Work Unit A:** freeze the current Stage 0 source set, fetch/audit raw snapshots, and verify official-chain evidence.
2. **Work Unit B:** parse already-active dining, calendar, and shuttle sources into structured rows.
3. **Work Unit C:** expand graduation through central evidence plus representative departments, with metadata gates for general-vs-department-specific questions.
4. **Work Unit D:** regenerate knowledge from structured rows and review public-probe failures before further Qwen/RAG tuning.

Current goal execution is limited to **Work Unit A**. Do not promote new active Stage 0 sources until the audit identifies a replacement, promotion, defer, or reject decision.

Work Unit A gates:

- Stage 0 active count remains 10.
- Every active raw item has `source_id`, `source_url`, `raw_checksum`, `fetched_at`, parser name/version, and raw file status.
- Dining is treated as `official_linked` only because a CNU `plus.cnu.ac.kr` welfare page links to `mobileadmin.cnu.ac.kr/food/index.jsp`.
- Inactive candidates remain `defer`.
- The current knowledge baseline is 53 docs, not the older 15-row smoke baseline.

## Source Scope For This Goal

### Dining

Primary source:

- `https://mobileadmin.cnu.ac.kr/food/index.jsp`

Evidence:

- The page exposes weekday menu dates for `2026.06.08` through `2026.06.13`.
- It contains cafeteria columns for 제1학생회관, 제2학생회관, 제3학생회관, 제4학생회관, 생활과학대학.
- It contains meal sections such as 조식, 중식, 석식 and menu items.

Goal:

- Fetch and parse the available June menu snapshot.
- Store rows by `meal_date`, `cafeteria`, `meal_type`, `user_type`, `menu_name`, `price`, `menu_items`, `fetched_at`, `source_url`.
- If only one week is exposed by the endpoint, record that limitation; do not pretend the full month was available.

### Shuttle

Primary sources:

- `https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html`
- `https://geo.cnu.ac.kr/notice/?vid=956`

Evidence:

- The central CNU page states 2026 shuttle operation 기준, non-operation conditions, timetable, and routes.
- The notice page states operation period `2026. 3. 3.(화) ~ 2026. 12. 18.(금)` and references the attached 2026 operation plan HWP.

Goal:

- Parse central timetable and route rows.
- Fetch the 2026 notice page as corroborating evidence.
- Download or record the HWP attachment status. If unsupported, store a parse failure with reason instead of silently skipping it.

### Academic Calendar

Primary source:

- `https://plus.chungnam.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&month=01&site_dvs_cd=kr&year=2026`

Fallback equivalent if hostname fails:

- `https://plus.cnu.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&site_dvs_cd=kr`

Evidence:

- Search result exposes structured 2026 calendar rows such as `01.20(화) 동기 계절학기 성적발표` and `01.26(월) ~ 01.28(수) 2026학년도 제1학기 예비수강신청`.

Goal:

- Fetch 2026 calendar by month if the endpoint supports `year`/`month`.
- Parse rows into `academic_year`, `month`, `event_name`, `start_date`, `end_date`, `source_url`.
- Confirm whether `2026학년도 제1학기 종강` exists in the official CNU calendar. If absent, record absence; do not infer from another university.

### Graduation

Primary sources:

- `https://plus.cnu.ac.kr/html/kr/sub05/sub05_051202.html`
- `https://plus.cnu.ac.kr/html/kr/23file/2023_book.pdf`
- `https://plus.cnu.ac.kr/html/kr/24file/2024_book.pdf`
- `https://plus.cnu.ac.kr/html/kr/25file/2025_book.pdf`
- 2026 curriculum PDF if discoverable from official CNU page.
- `https://computer.cnu.ac.kr/computer/edu/requirements.do`
- Computer/AI department attachment URLs discovered from the requirements board.

Evidence:

- The central graduation page states that undergraduate graduation generally requires 130 credits, with exceptions by department/major.
- It links or exposes graduation-credit tables for 2020 through 2025 entrants.
- The computer department has a graduation-requirements board and at least one attachment for `컴퓨터융합학부 2025학년도 입학생 졸업요건`.

Goal:

- Add the central graduation-credit page, not only department pages.
- Add 2023, 2024, 2025, and 2026 curriculum docs when official URLs are confirmed.
- Crawl the computer graduation requirements board list and its attachments.
- Keep department-specific metadata explicit so general graduation questions do not retrieve 생화학과/영어영문학과 unless the question asks for those departments.

## Implementation Tasks

### Task 1: Source Inventory Update

**Files:**

- Modify: `src/nlp_term/collect/source_inventory.py`
- Modify: `docs/source_inventory.md`
- Test: `tests/test_data_expansion_priority_report.py`

- [ ] Add active Stage 0 source specs for:
  - `graduation_credit_page`
  - `academic_calendar_2026_monthly`
  - `shuttle_bus_2026_notice`
  - `computer_graduation_requirements_board`
- [ ] Add Stage 1 source specs for:
  - `curriculum_2023_pdf`
  - `curriculum_2024_pdf`
  - `curriculum_2025_pdf`
  - `curriculum_2026_pdf_candidate`
  - discovered computer/AI requirement attachments
- [ ] Keep `cnu_mobile_food` active, but mark it as official-linked via the central CNU welfare menu link.
- [ ] Run:

```powershell
uv run pytest tests/test_data_expansion_priority_report.py -q
```

- [ ] Commit:

```powershell
git add src/nlp_term/collect/source_inventory.py docs/source_inventory.md tests/test_data_expansion_priority_report.py
git commit -m "feat: expand official source inventory"
```

### Task 2: Raw Fetch And Fetch Audit

**Files:**

- Modify: `src/nlp_term/collect/run_collect.py` only if needed
- Generate: `data/sources/source_probe.json`
- Generate: `docs/evidence/source-fetch-audit-2026-06-08.json`

- [ ] Run:

```powershell
uv run python -X utf8 -m nlp_term.collect.run_collect --fetch --stage stage0 --output data/sources/source_probe.json
```

- [ ] Write a fetch audit artifact containing:
  - source id
  - URL
  - status code
  - content type
  - raw path
  - checksum
  - warnings
  - whether the source is official/official-linked
- [ ] Gate:
  - every active Stage 0 source has either status `200` and a raw file, or a recorded failure reason.
  - no failed source is silently replaced without an audit warning.
- [ ] Commit:

```powershell
git add data/sources/source_probe.json docs/evidence/source-fetch-audit-2026-06-08.json data/raw
git commit -m "test: fetch expanded official source snapshots"
```

### Task 3: Structured Dining Parser

**Files:**

- Create: `src/nlp_term/prepare/structured_dining.py`
- Create: `tests/test_structured_dining_parser.py`
- Generate: `data/structured/dining_menu_2026_06.json`

- [ ] Parse visible menu dates, cafeterias, meal sections, user type, prices, and menu items.
- [ ] Do not claim full June coverage unless the endpoint exposes full June data.
- [ ] Gate:
  - at least one row for `2026-06-08`
  - rows include 제1학생회관 and 제2학생회관 if present
  - every row has `fetched_at` and `source_url`
- [ ] Run:

```powershell
uv run pytest tests/test_structured_dining_parser.py -q
```

- [ ] Commit:

```powershell
git add src/nlp_term/prepare/structured_dining.py tests/test_structured_dining_parser.py data/structured/dining_menu_2026_06.json
git commit -m "feat: parse structured dining menu rows"
```

### Task 4: Structured Shuttle Parser

**Files:**

- Create: `src/nlp_term/prepare/structured_shuttle.py`
- Create: `tests/test_structured_shuttle_parser.py`
- Generate: `data/structured/shuttle_2026.json`

- [ ] Parse:
  - operation policy
  - non-operation conditions
  - route names
  - timetable times
  - route stops
  - operation period from corroborating notice if available
- [ ] Gate:
  - at least one row for 교내 순환
  - at least one row for 캠퍼스 순환
  - every parsed departure time matches `HH:MM`
  - source URL is preserved per row
- [ ] Run:

```powershell
uv run pytest tests/test_structured_shuttle_parser.py -q
```

- [ ] Commit:

```powershell
git add src/nlp_term/prepare/structured_shuttle.py tests/test_structured_shuttle_parser.py data/structured/shuttle_2026.json
git commit -m "feat: parse structured shuttle rows"
```

### Task 5: Structured Academic Calendar Parser

**Files:**

- Create: `src/nlp_term/prepare/structured_calendar.py`
- Create: `tests/test_structured_calendar_parser.py`
- Generate: `data/structured/academic_calendar_2026.json`

- [ ] Fetch all available 2026 months from the official endpoint.
- [ ] Parse single-date and date-range events.
- [ ] Normalize dates to ISO `YYYY-MM-DD`.
- [ ] Gate:
  - at least 30 calendar rows, or documented source limitation.
  - every row has `event_name` and `start_date`.
  - if `종강` exists, it is represented as exact row evidence.
  - if `종강` does not exist, absence is recorded in the audit.
- [ ] Run:

```powershell
uv run pytest tests/test_structured_calendar_parser.py -q
```

- [ ] Commit:

```powershell
git add src/nlp_term/prepare/structured_calendar.py tests/test_structured_calendar_parser.py data/structured/academic_calendar_2026.json
git commit -m "feat: parse structured academic calendar rows"
```

### Task 6: Graduation Source And Parser Expansion

**Files:**

- Create or modify: `src/nlp_term/prepare/structured_graduation.py`
- Create: `tests/test_structured_graduation_parser.py`
- Generate: `data/structured/graduation_requirements.json`
- Modify: `docs/representative_departments_2026.md`

- [ ] Parse central graduation credit page.
- [ ] Add official 2023, 2024, 2025 curriculum PDFs.
- [ ] Discover 2026 curriculum PDF if official URL exists.
- [ ] Crawl computer graduation requirements board and download linked requirement attachments.
- [ ] Gate:
  - central 130-credit principle is present.
  - department-specific rows include `department`.
  - curriculum rows include `curriculum_year`.
  - unsupported HWP/HWPX attachments are recorded as failures with reason.
- [ ] Run:

```powershell
uv run pytest tests/test_structured_graduation_parser.py -q
```

- [ ] Commit:

```powershell
git add src/nlp_term/prepare/structured_graduation.py tests/test_structured_graduation_parser.py data/structured/graduation_requirements.json docs/representative_departments_2026.md
git commit -m "feat: expand graduation requirement data"
```

### Task 7: Regenerate Knowledge From Structured Rows

**Files:**

- Modify: `src/nlp_term/prepare/from_sources.py`
- Modify or create: `src/nlp_term/prepare/structured_to_knowledge.py`
- Generate: `data/knowledge_seed.json`
- Generate: `data/source_parse_failures.json`

- [ ] Convert structured rows into `KnowledgeDoc` objects.
- [ ] Preserve structured metadata:
  - dining: `meal_date`, `cafeteria`, `meal_type`
  - shuttle: `route_name`, `stop_name`, `departure_time`, `operation_period`
  - calendar: `event_name`, `start_date`, `end_date`
  - graduation: `department`, `curriculum_year`, `admission_year`, `credits`
- [ ] Gate:
  - current knowledge count increases from the 15-row smoke baseline.
  - all five labels have source-backed docs.
  - no accepted chunk is dominated by page chrome.
- [ ] Run:

```powershell
uv run python -X utf8 -m nlp_term.prepare.from_sources --source-probe data/sources/source_probe.json --output data/knowledge_seed.json --failures-output data/source_parse_failures.json --chunks-per-source 12
uv run pytest tests/test_prepare_from_sources.py tests/test_gold_contracts.py -q
```

- [ ] Commit:

```powershell
git add src/nlp_term/prepare/from_sources.py src/nlp_term/prepare/structured_to_knowledge.py data/knowledge_seed.json data/source_parse_failures.json
git commit -m "feat: build knowledge from expanded structured data"
```

### Task 8: Human Review Report Before Further RAG Work

**Files:**

- Create: `docs/data_expansion_review_2026_06_08.md`

- [ ] Produce a review table:
  - source id
  - source URL
  - parsed row count
  - sample rows
  - known limitations
  - whether it can be used for Task 2
  - whether it can be used for Task 3
- [ ] Include explicit checks for the public probe failures:
  - `오늘 학식`
  - `다음주 학식`
  - `셔틀버스 정상 운행`
  - `이번 학기 종강일`
  - `여름 계절학기 종강일`
  - `졸업까지 몇 학점`
  - `컴퓨터/AI 졸업요건`
- [ ] Run:

```powershell
uv run pytest -q
```

- [ ] Commit:

```powershell
git add docs/data_expansion_review_2026_06_08.md
git commit -m "docs: review expanded campus data coverage"
```

## Stop Condition

Stop after Task 8 and ask for human review.

Do not move to embedding retrieval, reranking, exact-calendar harness hardening, prompt tuning, or Qwen re-baseline until the user confirms that the expanded parsed data looks correct.

## Sources Checked During Planning

- CNU dining menu page: `https://mobileadmin.cnu.ac.kr/food/index.jsp`
- CNU shuttle page: `https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html`
- 2026 shuttle notice: `https://geo.cnu.ac.kr/notice/?vid=956`
- CNU graduation-credit page: `https://plus.cnu.ac.kr/html/kr/sub05/sub05_051202.html`
- CNU 2026 academic calendar endpoint discovered through search: `https://plus.chungnam.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&month=01&site_dvs_cd=kr&year=2026`
- Computer graduation requirements board discovered through search: `https://computer.cnu.ac.kr/computer/edu/requirements.do`

## Self-Review

- Spec coverage: The plan implements the user’s requested priority shift: collect dining, shuttle, academic calendar, and graduation requirements before further harness tuning.
- Scope control: The plan does not add embedding retrieval, LangChain, Qwen prompt changes, or broad agentic tool calling.
- Verification: Each parser has a row-count and schema gate, and the final stop condition requires human review before moving on.
- Risk: Full-month dining coverage may not be available from the visible endpoint. The plan records source limitation instead of fabricating coverage.
