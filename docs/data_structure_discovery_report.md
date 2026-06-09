# CNU Data Structure Discovery Report

> Generated: 2026-06-09  
> Purpose: Read-only discovery to decide how to rebuild the CNU Sutra RAG index

## Executive Summary

**Diagnosis: rebuild from raw HTML with domain-specific parsers, using `knowledge_seed.json` only as a legacy reference for field mapping.**

The existing `knowledge_seed.json` (2414 docs) has **substantial contamination** — 566 items (23%) come from notice list/candidate pages, 936 items (39%) have bodies under 50 characters, and navigation boilerplate (login, sitemap, menus) is embedded in the 892 recursive-plain-text chunks. The raw HTML source files preserve enough DOM structure (tables with CSS classes, identifiable content containers) to re-parse cleanly for four of the five domains. A hybrid approach — domain-specific deterministic parsers for dining/calendar/shuttle/graduation and recursive chunking from notice detail pages — would produce a significantly cleaner index than the current corpus.

The existing `examples/cnu-campus/data/processed/knowledge-index.jsonl` is a direct field-mapped copy of `knowledge_seed.json` (same 2414 items). It inherits all the same quality problems.

---

## Source Inventory

### A. Raw Source Snapshots (`data/raw/`)

| Path | Format | Count | Size | Category | Domain | Structure Preserved | Metadata Available | Parser Feasibility | Notes |
|------|--------|-------|------|----------|--------|---------------------|--------------------|--------------------|-------|
| `data/raw/dining/` | HTML | 33 | 549 KB | raw | dining | **Yes** — `<table class="menu-tbl">` with `<thead>`, `<colgroup>`, rows per day, columns per restaurant | source_url via probe; filename has date | **High** — deterministic CSS selector parsing | 2 tables: daily menu grid + notice. 13 rows, 51 cells. Restaurant names: 학생회관, 교직원, 생활과학, 기숙사. Prices, ingredients, operation status preserved. |
| `data/raw/notices/` | HTML (75) + PDF (2) | 77 | 8.07 MB | raw | notices | **Partial** — detail pages have content; list pages have template boilerplate | source_url, date from HTML | **Medium** — detail pages parseable; list pages should be skipped | 4 notice detail pages, 5 list pages (board/candidate), 46 candidate department pages, 10 AI-specific candidate pages, plus FAQ/scholarship/loan overviews. |
| `data/raw/academic_calendar/` | HTML | 7 | 643 KB | raw | academic_calendar | **Partial** — div-based layout, no tables; JSON-like data attributes in module version | source_url, year from filename | **Medium** — module version has structured data-* attributes; main page needs HTML parser | 6 year pages (2023-2026 + generic) + 1 homepage module. Module HTML has `data-calendar` attributes. |
| `data/raw/graduation/` | HTML (7) + PDF (3) | 10 | 19.4 MB | raw | graduation | **Yes** — `<table>` structure for requirements; full page layout | source_url, department from path | **High** — deterministic table parsing for department requirements | HTML per department + large PDFs (central curriculum, 6.7 MB and 12 MB). The PDFs are substantial but not parsed by current pipeline. |
| `data/raw/shuttle/` | HTML | 2 | 304 KB | raw | shuttle | **Yes** — `<table>` structure with route info + geo notice page | source_url via probe | **High** — table parsing for routes | `shuttle_bus.html` has 2 tables (7 rows, 24 cells). `shuttle_geo_notice_2026.html` is a WordPress page with 3 tables (geo/map related). |
| `data/raw/admission/` | PDF + TXT | 2 | 19.4 MB | raw | admission | N/A (no parser consumer) | N/A | **Defer** — no consumer pipeline yet | Large "megastudy" PDF. Currently unused. |
| `data/raw/tmp/` | PDF + PNG | 2 | 1.04 MB | scratch | other | N/A | N/A | **Ignore** — scratch files | `computer_ai_2026_graduation_requirements_260319.pdf` + screenshot PNG. Exploratory only. |

### B. Processed/Generated Data (`data/` root)

| Path | Format | Count | Size | Category | Domain | Notes |
|------|--------|-------|------|----------|--------|-------|
| `data/knowledge_seed.json` | JSON array | 2414 | 6.87 MB | processed RAG | mixed | **Primary corpus. Contaminated.** See full audit below. |
| `data/cls_train_seed.json` | JSON array | 1346 | 530 KB | training seed | mixed | Synthetic classifier training questions. Not RAG source. |
| `data/label_audit_seed.json` | JSON array | 1346 | 502 KB | audit | mixed | Human-reviewed label audit. Not RAG source. |
| `data/qa_seed.json` | JSON array | 50 | 42 KB | training seed | mixed | Synthetic QA pairs. Not RAG source. |
| `data/harness_safety_questions.json` | JSON array | 30 | 8 KB | experiment | mixed | Safety harness questions. Not RAG source. |
| `data/model_shortlist.json` | JSON array | 9 | 3 KB | reference | generic | Model selection doc. Not RAG source. |
| `data/test_*.json` | JSON array | 3 | < 1 KB | test fixture | mixed | Stub test data. Not RAG source. |
| `data/collection_failures.json` | JSON array | 0 | 4 B | diagnostic | ephemeral | Empty log. |
| `data/source_parse_failures.json` | JSON array | 14 | 3 KB | diagnostic | ephemeral | Parse error log. |

### C. Source Probe Metadata (`data/sources/`)

| Path | Format | Count | Size | Category | Notes |
|------|--------|-------|------|----------|-------|
| `data/sources/source_probe.json` | JSON array | 123 | 158 KB | source metadata | Maps raw files → parsers. Each entry has `raw`, `verification`, `inventory`. Critical for pipeline understanding. |
| `data/sources/source_probe_stage0_stub.json` | JSON array | ~10 | 12 KB | source metadata | Smaller version for CI testing. |

### D. Evaluation/Evidence Files

| Path | Count | Notes |
|------|-------|-------|
| `data/gold/` (6 files) | 214 items | Human-labeled eval sets for legacy Task 1/2. Not RAG source data. |
| `docs/evidence/` (19 JSON) | 19 reports | Experiment run outputs, audit manifests. Not RAG source data. |
| `outputs/` (8 JSON) | 8 outputs | Runtime chat/classifier output. Already gitignored. |
| `examples/cnu-campus/evals/smoke.json` | 2 questions | Smoke test. Works correctly. |

### E. Sutra Workspace (`examples/cnu-campus/`)

| Path | Format | Count | Notes |
|------|--------|-------|-------|
| `data/processed/knowledge-index.jsonl` | JSONL | 2414 lines | **Direct field-mapped copy of knowledge_seed.json**. Inherits all quality problems. |
| `data/index.jsonl` (STUB — still exists?) | JSONL | 3 lines | Original stub. Check if replaced by migration. |
| `evals/smoke.json` | JSON | 2 | Smoke test — graduation and sugang questions. |
| `prompts/system.md` / `answer.md` | MD | 2 | Prompt templates. Keep as-is. |

### F. Raw vs Generated Classification Summary

| Category | Paths | Description |
|----------|-------|-------------|
| **Raw source** | `data/raw/dining/`, `data/raw/notices/`, `data/raw/academic_calendar/`, `data/raw/graduation/`, `data/raw/shuttle/` | Original fetched HTML/PDF. **These are what we should re-parse.** |
| **Source metadata** | `data/sources/source_probe.json` | Maps sources → parsers. Useful for understanding which raw file maps to which domain. |
| **Processed RAG** | `data/knowledge_seed.json`, `examples/cnu-campus/data/processed/knowledge-index.jsonl` | Chunked/parsed docs. **Contaminated; use as reference only.** |
| **Training/eval** | `data/cls_train_seed.json`, `data/label_audit_seed.json`, `data/qa_seed.json` | Legacy synthetic training data. Not RAG source. |
| **Gold eval** | `data/gold/*` | Human-labeled eval sets. Not RAG source. |
| **Runtime artifacts** | `data/collection_failures.json`, `data/source_parse_failures.json`, `outputs/*`, `model/*` | Ephemeral. Ignore. |
| **Evidence reports** | `docs/evidence/*` | Experiment results. Stay in `docs/evidence/`. |

---

## `knowledge_seed.json` Audit

### Schema

```json
{
  "doc_id": "<domain>_<source>_chunk_<n>",
  "label": 0-4 (classification label),
  "domain": "academic_calendar|dining|graduation|notices|shuttle",
  "title": "<domain> source <n>",
  "body": "<plain text chunk>",
  "date": null | "YYYY-MM-DD",
  "source_url": "<original URL>",
  "source_id": "<unique source identifier>",
  "section": "<chunk type>",
  "metadata": {
    "parser": "html_source_parse|pdf_source_parse|...",
    "generation_method": "source_parse|structured_row|structured_aggregate",
    "content_type": "text/html|application/pdf",
    "chunking_strategy": "recursive_plain_window|recursive_plain|none",
    "boundary_type": "plain_text",
    "chunk_index": 1-9,
    "char_start": <int>,
    "char_end": <int>,
    "source_stage": "stage0|stage1",
    "source_active": true,
    "source_parser_type": "html|pdf|board_detail|calendar|dining|shuttle",
    "source_priority": 100,
    "source_freshness_policy": "snapshot|latest_snapshot",
    "source_index_eligible": true|false,
    "source_notes": "<description>",
    "source_department": "<department name>",
    "source_id": "<same as top-level>",
    "source_url": "<same as top-level>",
    "source_domain": "<same as top-level>",
    "source_label": <same as top-level>,
    "official_chain_ok": true,
    "lifecycle_status": "index_eligible|parsed",
    "index_eligible": true|false,
    "parser_name": "<parser name>",
    "parser_version": "0.1.0",
    "raw_path": "data/raw/<domain>/<source_file>",
    "raw_checksum": "<sha256>",
    "raw_fetched_at": "<ISO timestamp>",
    "raw_status_code": 200,
    "raw_content_type": "text/html|application/pdf",
    "verification_official_chain_ok": true,
    "verification_parser_name": "<parser>",
    "verification_parser_version": "0.1.0",
    "verification_verified_at": "<ISO timestamp>"
  }
}
```

### Counts

| Metric | Value |
|--------|-------|
| Total items | 2414 |
| Unique domains | 5 |
| Unique source_ids | 123 |
| Unique raw source files (in source_probe) | 123 |
| Index eligible (lifecycle_status) | 1912 |
| Parsed (lifecycle_status) | 502 |

### Domain Distribution

| Domain | Items | Items from structured parsers | Items from recursive chunking | Unique sources |
|--------|-------|------------------------------|-------------------------------|----------------|
| dining | 1145 | 950 (structured_row) | 195 (source_parse) | 27 |
| notices | 648 | 60 (structured_row) | 588 (source_parse) | 77 |
| academic_calendar | 480 | 418 (structured_row + structured_aggregate) | 62 (source_parse) | 7 |
| graduation | 85 | 0 | 85 (source_parse) | 10 |
| shuttle | 56 | 41 (structured_row) | 15 (source_parse) | 2 |

### Chunking Strategy Distribution

| Strategy | Count | Source |
|----------|-------|--------|
| `none` | 1469 | Structured parser output (doesn't set chunking_strategy) |
| `recursive_plain_window` | 892 | Plain text recursive chunking |
| `recursive_plain` | 53 | Plain text recursive chunking (variant) |

### Generation Method

| Method | Count | Notes |
|--------|-------|-------|
| `structured_row` | 1374 | Domain-specific structured parsers (dining menu items, calendar events, notice board items, shuttle segments) |
| `source_parse` | 945 | Generic text extraction + recursive chunking (9 chunks per source) |
| `structured_aggregate` | 95 | Aggregated/combined structured output (monthly calendars, weekly menus, shuttle routes) |

### Contamination Counts

| Contamination Type | Count | % of Total | Affected Domains |
|-------------------|-------|-----------|------------------|
| **List/candidate page sources** | 566 | 23.4% | notices (566) — `academic_notice_board_page_*`, `academic_notice_candidate_page_*`, `notice_candidate_*` |
| Body < 50 characters | 936 | 38.8% | dining (930), academic_calendar (3), notices (3) |
| Body < 100 characters | 1337 | 55.4% | dining (930), academic_calendar (325), shuttle (39), notices (40), graduation (3) |
| Contains "목록" (list) | 67 | 2.8% | notices (64), academic_calendar (1), dining (0), shuttle (2) |
| Contains "이전" (prev) | 75 | 3.1% | notices (69), graduation (4), academic_calendar (2) |
| Contains "다음" (next) | 82 | 3.4% | notices (77), graduation (3), academic_calendar (1), shuttle (1) |
| Contains "마지막" (last) | 71 | 2.9% | notices (69), graduation (2) |
| Contains "Page=" | 60 | 2.5% | notices (60) |
| Contains "로그인" (login) | 88 | 3.6% | graduation (55), notices (33) |
| Contains "주메뉴" (main menu) | 28 | 1.2% | graduation (28) |
| Contains "본문 바로가기" (skip nav) | 28 | 1.2% | graduation (28) |
| Contains "사이트맵" (sitemap) | 28 | 1.2% | graduation (28) |
| Null date | 945 | 39.1% | dining (925), academic_calendar (15), notices (2), shuttle (1), graduation (2) |
| Missing source_url | 0 | 0% | — |
| Missing domain | 0 | 0% | — |
| Missing/empty body | 0 | 0% | — |

### Contaminated Source IDs Detail (566 items total)

**Notice list pages** — 82 items from 5 pages:
- `academic_notice_board_page_2` through `_6` (16-17 items each)

**Notice candidate pages** — 210 items from 30 pages:
- `academic_notice_candidate_page_7` through `_36` (6-7 items each)

**Department candidate pages** — 180 items from 20 department+AI pages:
- `notice_candidate_chemistry_0` through `_90` (9 items each, 10 pages = 90 items)
- `notice_candidate_ai_0` through `_90` (9 items each, 10 pages = 90 items)
- `notice_candidate_computer_0` through `_90` (??? — also present)

**Homepage module** — 8 items:
- `homepage_academic_calendar_module` (8 items — list page, not detail)

### 10 Representative Bad Rows

1. **List-page template**: `academic_notice_board_page_2__notice_board_item__1808__2026-06-01__...`
   ```
   Body: "2026학년도 DSC공유대학 ... 공유대학 학생 모집 안내 게시판입니다. 등록일 2026-06-01입니다. 작성자는 학생처리..."
   Section: notice_board_item
   ```
   *Problem: Template text "게시판입니다. 등록일 ...입니다. 작성자는 ...입니다." is format boilerplate for every list item.*

2. **Candidate list page**: `academic_notice_candidate_page_10__notice_board_item__...`
   ```
   Body: Similar template — "게시판입니다. 등록일 ... 작성자는 ... 첨부파일이 있습니다. 바로가기: https://..."
   ```
   *Problem: Same template boilerplate, not actual content.*

3. **Empty dining menu**: `cnu_mobile_food__dining_menu__2026-06-08__제1학생회관__중식__...`
   ```
   Body: "2026-06-08 제1학생회관 중식 메뉴: 메뉴는운영중입니다." (41 chars)
   ```
   *Problem: "메뉴는운영중입니다" (menu is operating) — no actual menu data. 930 similar entries.*

4. **Navigation-only graduation chunk**: `graduation_biochemistry_requirements_chunk_1`
   ```
   Body: "생화학과 | 학사정보 | 졸업요건 본문 바로가기 주메뉴 바로가기 서브메뉴 바로가기 충남대학교 정보화본부 CNU With U 도서관 발전기금 로그인 사이트맵..."
   ```
   *Problem: First chunk is mostly navigation menu text before actual content.*

5. **Graduation chunk_2** (overlapping with chunk_1 due to sliding window):
   ```
   Body: "로그인 사이트맵 모바일 메뉴 열기 자연과학대학 생화학과 학과소개 학과소개 학과연혁..."
   ```
   *Problem: Chunk_2 repeats the tail of navigation from chunk_1 due to sliding window overlap.*

6. **Dining menu placeholder**: `cnu_mobile_food__dining_menu__...__교직원__석식__...`
   ```
   Body: "2026-06-08 교직원 석식 메뉴: 메뉴는운영중입니다."
   ```
   *Problem: Many dining entries (930) are 40-50 char placeholders with no food data.*

7. **Notice candidate_chemistry_0 chunk_1**: Full page with navigation, candidate list, and no actual notice content
   ```
   Body: "<full page text with navigation menus, candidate notice titles, dates in table>"
   ```
   *Problem: The source is a list page, chunking produces navigation-heavy fragments.*

8. **Academic calendar module chunk**: `homepage_academic_calendar_module__chunk_1`
   ```
   Body: "학사일정-게시판 | 홈페이지 학사 일정 안내" + navigation
   ```
   *Problem: Module page is a list/embed view, not actual calendar event data.*

9. **Shuttle recursive chunk**: `shuttle_bus__chunk_1`
   ```
   Body: "학생생활 백마포탈 CNU With U 도서관 ..." (navigation)
   ```
   *Problem: Recursive chunk captures navigation, not shuttle route info.*

10. **"운영중입니다" (operating) entries**: ~930 dining entries share the exact pattern:
    ```
    "<date> <cafeteria> <meal_type> 메뉴: 메뉴는운영중입니다."
    ```
    *These are structurally correct (restaurant + meal type + date) but contain zero food data.*

### Pipeline Root Cause

The `build_knowledge_from_probe` function in `src/nlp_term/prepare/from_sources.py:126` combines **both** `parse_structured_source` (domain-specific structured parse) and `parse_source` (generic text extraction + 9-way recursive chunking) for each of the 123 sources. This means:

- For each source with a structured parser, you get structured rows **plus** 9 recursive plain-text chunks of the same source's raw HTML (including navigation, headers, footers).
- For list pages (notice boards, candidate pages), the structured "rows" are template-generated board items with no actual content.
- The recursive chunks from list pages perpetuate navigation noise.

### Recommendation

| Use | Rationale |
|-----|-----------|
| **Do NOT promote directly** | 566 items (23%) are from list/candidate sources. 936 (39%) have < 50 chars. Navigation boilerplate is pervasive. |
| **Use as legacy reference only** | Schema for field mapping. Source metadata (parser, chunking, checksums). Pipeline structure understanding. Do not use body text. |
| **Rebuild from raw HTML** | The raw HTML preserves enough structure (tables, CSS classes, identifiable containers) for deterministic re-parsing. |

---

## Raw Source Feasibility by Domain

### Dining — `data/raw/dining/` (33 HTML files, 549 KB)

**Structure quality**: Excellent. `<table class="menu-tbl type-cap">` with:
- `<colgroup>` with classes `building`, `breakfast`, `lunch`, `dinner`
- `<thead>` with day-of-week headers
- `<tbody>` with restaurant rows (학생회관, 교직원, 생활과학, 기숙사)
- Each cell contains menu text with prices and ingredient notes
- Daily files: `cnu_mobile_food_2026_06_09.html` (one day, all restaurants)
- Weekly files: `cnu_mobile_food_week_2026_06_08_1st.html` through `4th.html` (one week per restaurant, plus `life_science.html`)

**Parser strategy**: Deterministic CSS selector parsing:
- Select `<table class="menu-tbl">` → iterate `<tr>` → map restaurant name from row header → read 7 `<td>` for Mon-Sat → extract menu text, prices, ingredients
- One HTML file = one day or one restaurant/week

**Chunking recommendation**: **Semantic-deterministic** feasible now.
- Chunk unit: weekly cafeteria menu per restaurant (e.g., "1st cafeteria week of June 8")
- Or: daily menu rows per restaurant per meal
- Confidence: **High**
- Blockers: None. HTML structure is clean and consistent.

### Notices — `data/raw/notices/` (77 files, 8.07 MB)

**Structure quality**: Mixed.
- **Detail pages** (4 files: `academic_notice_detail_2511200.html`, `course_registration_notice_2026.html`, `english_ability_criteria.html`, ...): Full article content with title, date, body text in identifiable containers. Also other overview pages (`scholarship_overview.html`, `student_loan_overview.html`, `registration_overload_faq.html`).
- **List pages** (5 files: `academic_notice_board.html`, `_page_2` through `_6`): Table of notice titles, dates, links. Template-generated content. **Should be skipped.**
- **Candidate pages** (46 department + 10 AI = 56 files): Department-level notice list pages. Similarly template-generated. **Should be skipped.**
- **PDFs** (2 files: `course_registration_plan_2025_2_pdf.pdf`, `english_ability_notice_2025_1_pdf.pdf`): Full document PDFs with rich content.

**Parser strategy**: Hybrid:
- For **detail pages**: Parse `<div class="board_view">` or equivalent content container → extract title, date, body HTML → clean HTML to text
- For **overview pages** (scholarship, loan, FAQ): Parse as full text documents
- For **PDFs**: Extract text via `pdfminer` or similar
- Skip all list/candidate pages entirely

**Chunking recommendation**: **Hybrid needed.**
- Detail pages: Semantic chunking by section/paragraph (each notice is "one document" → sub-chunk by section)
- Overview pages: Recursive text chunking
- PDFs: Recursive text chunking with semantic boundary detection
- Chunk unit: notice detail document / FAQ section / scholarship section
- Confidence: **Medium**
- Blockers: Detail page count is very low (only 4 detail files currently fetched). List pages dominate. The current fetcher prioritized list pages over detail pages. A re-fetch strategy is needed for more detail pages.

### Academic Calendar — `data/raw/academic_calendar/` (7 HTML files, 643 KB)

**Structure quality**: Moderate.
- Div-based layout, not table-based. Content structured as event lists with dates and descriptions.
- The `homepage_academic_calendar_module.html` has calendar-like data attributes embedded.
- Year pages (2023-2026) contain full academic year events with date ranges and descriptions.

**Parser strategy**: Deterministic HTML parsing:
- Parse `<div>` containers for each event → extract date range, event title, description
- The module version may have JSON-like `data-*` attributes for event data

**Chunking recommendation**: **Semantic-deterministic feasible now.**
- Chunk unit: semester calendar / monthly event list / individual event
- Confidence: **High**
- Blockers: None. The 6 year pages provide good coverage (2023-2026).

### Graduation — `data/raw/graduation/` (10 files, 19.4 MB)

**Structure quality**: Good for HTML; PDFs are bulk.
- HTML files (7): Department-specific pages with `<table>` structures for requirement categories. Each table row = one requirement (category, subcategory, credit count, notes).
- PDF files (3): Large central curriculum PDFs (2 MB, 6.7 MB, 12 MB). Unstructured text extracted.
- The HTML pages include full site navigation (menus, login, sitemap) in the page chrome, but the requirement tables are identifiable.

**Parser strategy**: Hybrid:
- **HTML**: Deterministic table parsing → extract requirement rows
- **PDF**: PDF text extraction → recursive chunking until better structured source found

**Chunking recommendation**: **Hybrid needed.**
- HTML pages: Semantic-deterministic — one requirement table = one chunk group
- PDFs: Recursive chunking
- Chunk unit: department graduation requirement set / PDF section
- Confidence: **Medium** (high for HTML pages, low for PDFs due to size)
- Blockers: Large PDFs (6.7 MB, 12 MB) will need efficient PDF text extraction. The 7 HTML department pages cover only a subset of departments.

### Shuttle — `data/raw/shuttle/` (2 HTML files, 304 KB)

**Structure quality**: Good.
- `shuttle_bus.html` (102 KB): Table-based route information. 2 tables, 7 rows, 24 cells. Campus shuttle bus schedule with route names, times, stops.
- `shuttle_geo_notice_2026.html` (202 KB): WordPress-based page with geo notice info. 3 tables. Different format.

**Parser strategy**: Deterministic table parsing for `shuttle_bus.html`:
- Extract routes from `<table>` → each row = one route → columns = route name, stops, schedule times

**Chunking recommendation**: **Semantic-deterministic feasible now.**
- Chunk unit: shuttle route/table
- Confidence: **High**
- Blockers: Only 2 source files. Limited coverage (one route snapshot + one geo notice). Would benefit from more frequent snapshots if shuttle schedules change.

---

## Chunking Recommendation

### Comparison

| Approach | Suitability | Best For | Why |
|----------|-------------|----------|-----|
| **Domain-specific semantic-deterministic** | 4 of 5 domains | Dining, calendar, shuttle, graduation HTML | Raw HTML preserves CSS-classed tables, identifiable content containers. Can parse rows to structured records and chunk by natural units (menu/week, event/month, route/table, requirement/department). |
| **Recursive chunking** | 1 of 5 domains | Notice PDFs, some notice details | Detail pages are few; recursive chunking is the fallback for PDFs and large non-tabular HTML pages. But must strip navigation chrome first. |
| **Hybrid deterministic** | Overall recommendation | All domains | Use domain-specific parsers where feasible (dining, calendar, shuttle, graduation HTML); fall back to recursive chunking for PDFs and non-tabular pages. Skip list/candidate pages entirely. |

### Practical Recommendation

1. **Dining**: Deterministic CSS selector → per-restaurant weekly menu chunks. Skip "운영중입니다" entries or flag them.
2. **Academic calendar**: Deterministic event parser → per-semester or per-month calendar chunks.
3. **Shuttle**: Deterministic table parser → per-route chunk.
4. **Graduation HTML**: Deterministic table parser → per-department requirement chunks.
5. **Graduation PDF**: Recursive chunking after PDF text extraction.
6. **Notice detail pages**: HTML content extraction → per-notice document chunks (sub-chunk by section if long).
7. **Notice list/candidate pages**: **Skip entirely** — they contain no real content.
8. **Notice overview pages** (scholarship, loan, FAQ): Hybrid — per-section chunking.
9. **Notice PDFs**: Recursive chunking after PDF text extraction.

This would produce a corpus that is **smaller but far cleaner** than the current 2414 items:
- Expected output: ~300-600 high-quality documents (vs 2414)
- Each document would contain actual content, not navigation boilerplate
- List-page contamination would be eliminated
- "운영중입니다" dining placeholders would be excluded

---

## Quality Gate Rules Applicability

| Rule | Count | Feasible | Notes |
|------|-------|----------|-------|
| Body contains "목록 처음 페이지" | 51 | Easy regex | Already identified |
| Body contains "이전 페이지" | 66 | Easy regex | Already identified |
| Body contains "다음 페이지" | 66 | Easy regex | Already identified |
| Body contains "마지막 페이지" | 51 | Easy regex | Already identified |
| Page number pagination runs | 60 | Easy regex | "Page=\d+" pattern |
| Multiple notice titles/dates in one body | ~530 | Medium | Characteristic of list pages — title + date pairs |
| Missing source_url | 0 | Trivial | All have source_url |
| Missing source_name/domain | 0 | Trivial | All have domain |
| Missing domain | 0 | Trivial | All have domain |
| Empty body | 0 | Trivial | None empty (some are 1 char) |
| Body < 50 chars | 936 | Trivial | Mostly dining "메뉴는운영중입니다" |
| Body < 100 chars | 1337 | Trivial | Additional short entries |
| Contains navigation menu text ("주메뉴", "로그인", "사이트맵") | ~88 | Easy regex | Strong signal for recursive chunks that grabbed navigation |

---

## Risks / Open Questions

| # | Risk / Question | Impact |
|---|-----------------|--------|
| 1 | **Only 4 notice detail pages exist.** The current fetcher collected 56 candidate department list pages + 10 AI candidate pages + 6 board list pages but only 4 actual detail pages. A re-fetch with detail-page-first strategy is needed for notice content. | **High** — Notice is the second-largest domain. Without more detail pages, notice coverage will be poor. |
| 2 | **Graduation PDFs are 19 MB combined** and only 7 HTML department pages exist. The PDFs (central curriculum 2023-2025) are large and unparsed. | **Medium** — Graduation is the smallest domain (85 items), so impact is limited. But the PDFs contain rich data. |
| 3 | **Dining data has temporal coverage** (June 2026 daily files + weekly files for all 5 weeks). This is current but transient. Snapshot freshness depends on the collection timestamp. | **Low** — For the term project, current snapshot is sufficient. |
| 4 | **Raw HTML files are gitignored** (`data/raw/` in `.gitignore`). They exist on disk but won't travel with the repo. The rebuilt index would need either tracked raw files in `examples/cnu-campus/data/raw/` or a documented fetch-then-build workflow. | **Medium** — Decide before committing. |
| 5 | **Parser code for domain-specific adapters exists** in `src/nlp_term/prepare/` (DiningAdapter, CalendarAdapter, ShuttleAdapter, NoticeAdapter, GraduationRequirementAdapter). These are legacy `nlp_term` code. Porting them to Sutra-direct parsing is possible but adds scope. | **Medium** — Can write simpler one-off parsers instead of porting the full adapter framework. |
| 6 | **List/candidate pages are not worthless** — they contain notice titles, dates, and links to detail pages. A hybrid approach could use them as an index to guide detail page fetching. But as content, they are useless. | **Low** — For the current rebuild, skip them entirely. |
| 7 | **Dining "운영중입니다" entries** (930 of 1145 dining items) indicate menus that were "operating" but had no posted menu. Future fetches should distinguish "no data" from "real menu." | **Low** — Easy to filter in a new parser. |
| 8 | **The existing `knowledge-index.jsonl` already has 2414 lines** (migrated from knowledge_seed.json). Rebuilding will require replacing it, not creating it from scratch. | **Low** — Just overwrite with cleaner data. |

---

## Suggested Next Step

**Implement a single-domain deterministic parser for dining as proof of concept, then scale to other domains.**

Concrete action plan:
1. Write a `cnu_dining_parser.py` (standalone script, no dependency on legacy `nlp_term`):
   - Input: `data/raw/dining/cnu_mobile_food_week_2026_06_08_1st.html`
   - Parse: `<table class="menu-tbl">` → extract restaurant name, meal type, daily menu items, prices, ingredients
   - Output: structured JSON lines (one per restaurant-week-meal combination)
   - Filter: skip entries with "운영중입니다" or empty menus
2. Verify on all 33 dining HTML files
3. To count: expected output of ~150-200 clean dining documents (vs 1145 currently)
4. Report: domain reduction %, content quality improvement comparisons

After dining is validated, expand to:
- Academic calendar (next easiest — 6 year pages, deterministic event parsing)
- Shuttle (smallest — 2 HTML files, table parsing)
- Graduation HTML (7 HTML files, table parsing)
- Notice detail pages (only 4 detail files currently — may need fetcher update)

The goal is a clean `examples/cnu-campus/data/processed/knowledge-index.jsonl` of ~300-600 high-quality documents that can be validated via `uv run sutra workspace validate` and `uv run sutra docs check`.
