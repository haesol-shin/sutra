# Simple Evidence Units Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the QA pipeline simple by only creating Qwen-facing structured evidence when the source structure is already explicit, and by bundling existing dining/shuttle rows instead of adding heuristic confidence classifiers.

**Architecture:** Do not add `high_confidence`, `needs_review`, or `reject` labels. Remove unsafe prose-to-graduation-row promotion, preserve ambiguous prose as raw source chunks, and use existing `row_type` metadata to make Qwen see answer-sized evidence units. The only new behavior is deterministic structural composition from already parsed rows.

**Tech Stack:** Python 3.10.12, `uv`, existing `src/nlp_term` package, pytest.

---

## Revision Notes From 2026-06-09 Complexity Audit

The previous tool-use and single-tool experiment paths are no longer part of the active implementation direction. Keep Qwen as the answer writer and make the project win by passing clean, official, relevant evidence to the model.

Before executing this plan, revise the implementation direction as follows:

- Remove mechanical routing from the Task 2 answer path where it blocks or reshapes generation. Routing may remain only as a lightweight retrieval hint if it demonstrably improves evidence selection without suppressing Qwen's answer.
- Remove duplicate ranking logic that performs another classification pass. Retrieval ranking should be lexical/metadata based, or receive an already known route label explicitly.
- Remove unsafe graduation prose-to-structured-row extraction. Graduation prose may remain as clean source text unless it comes from an explicit table/list structure.
- Simplify chunking to plain chunking. Do not attach confidence labels or keyword-derived quality labels to chunks.
- Keep date handling as context injection and exact date arithmetic, not as a policy gate. The prompt should state the current date, timezone, and how relative dates were resolved.
- Revisit aggregate rows separately. They can be useful answer-sized evidence units, but they must be clearly treated as derived bundles, not source-native structured facts.
- Split source inventory responsibilities: active runtime sources should be separate from exploratory candidate sources.
- Make `build_all` deterministic. It should not silently reuse old generated `source_parse` artifacts.

---

## File Structure

- Modify `src/nlp_term/structured/graduation.py`
  - Stop regex/prose snippets from becoming `graduation_requirement` rows.
  - Only return structured graduation rows from explicit table-like extraction if such a parser already exists or is added in a narrow later step.
  - For this plan's first implementation, the safest minimal action is to disable current prose row creation and let existing `source_parse` chunks remain available.
- Modify `tests/test_graduation_requirement_adapter.py`
  - Replace tests that expect prose-derived rows with tests proving prose snippets do not become structured requirements.
- Modify `src/nlp_term/chat/orchestrator.py`
  - Use existing `row_type` metadata to prefer broad answer units:
    - dining: `dining_weekly_menu` before `dining_menu` for broad questions.
    - shuttle: `shuttle_route` before `shuttle_segment` for broad questions.
  - No new classifier; only deterministic sort weights based on existing row types.
- Modify `src/nlp_term/chat/evidence_pack.py`
  - Keep evidence pack formatting unchanged unless needed for route/menu bundle grouping.
  - If grouping is required, group only by existing `source_id`, `week_start/week_end/cafeteria`, or route metadata.
- Create or modify `tests/test_simple_evidence_units.py`
  - Add regression tests for no unsafe graduation row, dining weekly preference, and shuttle route preference.
- Regenerate data only after tests pass:
  - `data/knowledge_seed.json`
  - `data/source_parse_failures.json`
  - `docs/evidence/source-fetch-audit-2026-06-08.json`
  - `docs/source_fetch_audit_2026_06_08.md`

---

### Task 1: Stop Unsafe Graduation Prose Rows

**Files:**
- Modify: `src/nlp_term/structured/graduation.py`
- Modify: `tests/test_graduation_requirement_adapter.py`

- [ ] **Step 1: Write the failing test**

Add a test proving the current dangerous behavior is no longer allowed. The important case is a prose sentence containing multiple credit numbers where the first number is not the requirement value.

```python
def test_graduation_adapter_does_not_promote_prose_credit_mentions_to_requirement_rows():
    snippet = (
        "13학년도 교육과정 이전학생은 교양에서 국어 관련 3학점, "
        "영어 관련 6학점 이상 이수하여 교양이 합계 24학점이 되어야 합니다."
    )

    assert _requirement_snippets(snippet) == []
```

If private helper imports are undesirable, test through `GraduationRequirementAdapter.parse()` using a temporary raw HTML file containing the same prose and assert it raises `ValueError("graduation requirement rows not found")`.

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```powershell
uv run pytest tests/test_graduation_requirement_adapter.py -q
```

Expected before implementation: the test fails because current snippet logic accepts prose with credit values.

- [ ] **Step 3: Implement the minimal change**

In `src/nlp_term/structured/graduation.py`, remove prose snippet extraction from the Qwen-ready structured path.

Minimal implementation:

```python
def _requirement_snippets(text: str) -> list[str]:
    return []
```

Do not add a replacement classifier. Do not add confidence labels. The existing raw parser still keeps source text as `source_parse` chunks.

- [ ] **Step 4: Run graduation tests**

Run:

```powershell
uv run pytest tests/test_graduation_requirement_adapter.py -q
```

Expected: tests pass after updating any old expectations that assumed prose-derived `graduation_requirement` rows.

- [ ] **Step 5: Commit**

```powershell
git add src/nlp_term/structured/graduation.py tests/test_graduation_requirement_adapter.py
git commit -m "fix: stop unsafe graduation prose extraction"
```

---

### Task 2: Prefer Existing Dining Weekly Bundles

**Files:**
- Modify: `src/nlp_term/chat/orchestrator.py`
- Create/Modify: `tests/test_simple_evidence_units.py`

- [ ] **Step 1: Write the failing test**

Create a test with one `dining_weekly_menu` doc and one `dining_menu` doc. The broad question should rank/select the weekly doc before the single row.

```python
def test_broad_dining_question_prefers_weekly_bundle_over_single_row():
    docs = [
        _knowledge_doc(
            doc_id="single",
            domain="dining",
            title="2026-06-08 제2학생회관 중식 식단",
            body="2026-06-08 제2학생회관 중식 학생 정식: 김치볶음밥.",
            metadata={"row_type": "dining_menu", "generation_method": "structured_row", "menu_date": "2026-06-08"},
        ),
        _knowledge_doc(
            doc_id="weekly",
            domain="dining",
            title="2026-06-08~2026-06-13 제2학생회관 주간 식단",
            body="2026-06-08~2026-06-13 제2학생회관 주간 식단 요약: ...",
            metadata={
                "row_type": "dining_weekly_menu",
                "generation_method": "structured_aggregate",
                "week_start": "2026-06-08",
                "week_end": "2026-06-13",
                "cafeteria": "제2학생회관",
            },
        ),
    ]

    selected = _select_retrieved_docs(
        docs,
        question="다음주 학식 뭐 나와요?",
        route_domain="dining",
        limit=2,
    )

    assert selected[0].doc_id == "weekly"
```

Use the existing public selection helper if available. If no public helper exists, expose one small helper with a narrow name such as `_domain_unit_priority(doc, question, route_domain)`.

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```powershell
uv run pytest tests/test_simple_evidence_units.py -q
```

Expected before implementation: selection may preserve retrieval order and put `dining_menu` first.

- [ ] **Step 3: Implement minimal row-type priority**

In `src/nlp_term/chat/orchestrator.py`, add a tiny deterministic priority helper.

```python
def _answer_unit_priority(doc: KnowledgeDoc, *, route_domain: str) -> int:
    row_type = doc.metadata.get("row_type")
    if route_domain == "dining":
        if row_type == "dining_weekly_menu":
            return 0
        if row_type == "dining_menu":
            return 1
    if route_domain == "shuttle":
        if row_type == "shuttle_route":
            return 0
        if row_type == "shuttle_segment":
            return 1
    return 0
```

Apply it only as a tie-breaker after domain/temporal filtering, not as a new semantic classifier.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
uv run pytest tests/test_simple_evidence_units.py tests/test_task2_evidence_pack.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/nlp_term/chat/orchestrator.py tests/test_simple_evidence_units.py
git commit -m "fix: prefer dining weekly evidence units"
```

---

### Task 3: Preserve Shuttle Segments Under Route Evidence

**Files:**
- Modify: `src/nlp_term/chat/orchestrator.py`
- Modify: `src/nlp_term/chat/evidence_pack.py` only if route-plus-segment evidence cannot be represented with current fields.
- Modify: `tests/test_simple_evidence_units.py`

- [ ] **Step 1: Write the failing test**

The route summary should be first, and matching segments should remain available as supporting details.

```python
def test_shuttle_question_prefers_route_but_keeps_segments_as_support():
    docs = [
        _knowledge_doc(
            doc_id="segment",
            domain="shuttle",
            title="2026학년도 셔틀버스 교내 순환 출발시각 08:30",
            body="교내 순환의 출발시각: 08:30. 적용 기간은 2026-03-03부터 2026-06-21까지입니다.",
            metadata={"row_type": "shuttle_segment", "route_name": "교내 순환"},
        ),
        _knowledge_doc(
            doc_id="route",
            domain="shuttle",
            title="2026학년도 셔틀버스 교내 순환",
            body="교내 순환은 2026-03-03부터 2026-06-21까지 학기 중 평일 주간에 정상 운행합니다.",
            metadata={"row_type": "shuttle_route", "route_name": "교내 순환"},
        ),
    ]

    selected = _select_retrieved_docs(
        docs,
        question="다음주에 셔틀버스는 정상 운행하나요?",
        route_domain="shuttle",
        limit=2,
    )

    assert [doc.doc_id for doc in selected] == ["route", "segment"]
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```powershell
uv run pytest tests/test_simple_evidence_units.py -q
```

Expected before implementation: segment may appear before route.

- [ ] **Step 3: Reuse the same `_answer_unit_priority` helper**

No new structure should be added if Task 2 already introduced `_answer_unit_priority`. Ensure shuttle route receives priority `0` and segment receives `1`.

- [ ] **Step 4: Run shuttle and evidence tests**

Run:

```powershell
uv run pytest tests/test_simple_evidence_units.py tests/test_shuttle_adapter.py tests/test_task2_evidence_pack.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/nlp_term/chat/orchestrator.py tests/test_simple_evidence_units.py src/nlp_term/chat/evidence_pack.py
git commit -m "fix: keep shuttle route evidence ahead of segments"
```

---

### Task 4: Regenerate Data and Prove the Simpler Shape

**Files:**
- Modify generated data:
  - `data/knowledge_seed.json`
  - `data/source_parse_failures.json`
  - `docs/source_fetch_audit_2026_06_08.md`
  - `docs/evidence/source-fetch-audit-2026-06-08.json`
- Modify docs:
  - `docs/data_readiness_report_2026_06_09.md`
  - `docs/evidence/data-readiness-2026-06-09.json`

- [ ] **Step 1: Regenerate source-backed knowledge**

Run:

```powershell
uv run python -m nlp_term.prepare.from_sources --source-probe data/sources/source_probe.json --output data/knowledge_seed.json --failures-output data/source_parse_failures.json
```

Expected:

```text
wrote <N> knowledge docs to data\knowledge_seed.json
wrote <M> parse failures to data\source_parse_failures.json
```

- [ ] **Step 2: Verify graduation structured rows are gone or reduced to explicit-safe rows**

Run:

```powershell
@'
import json
from collections import Counter
from pathlib import Path
rows = json.loads(Path("data/knowledge_seed.json").read_text(encoding="utf-8"))
print(Counter(d.get("metadata", {}).get("row_type", "<missing>") for d in rows if d["domain"] == "graduation"))
'@ | python -
```

Expected for the minimal first version:

```text
Counter({'<missing>': ...})
```

The exact count may differ because raw chunks remain, but unsafe `graduation_requirement` rows should not be present.

- [ ] **Step 3: Verify dining and shuttle answer units still exist**

Run:

```powershell
@'
import json
from collections import Counter
from pathlib import Path
rows = json.loads(Path("data/knowledge_seed.json").read_text(encoding="utf-8"))
for domain in ("dining", "shuttle"):
    print(domain, Counter(d.get("metadata", {}).get("row_type", "<missing>") for d in rows if d["domain"] == domain))
'@ | python -
```

Expected:

```text
dining Counter({'dining_menu': ..., 'dining_weekly_menu': ..., '<missing>': ...})
shuttle Counter({'shuttle_segment': ..., 'shuttle_route': ..., '<missing>': ...})
```

- [ ] **Step 4: Update readiness report wording**

Update `docs/data_readiness_report_2026_06_09.md` to say:

```markdown
Graduation structured rows are disabled unless extracted from explicit tables. Prose graduation text remains available as raw source context, but it is not treated as Qwen-ready structured fact.
```

Do not introduce confidence labels.

- [ ] **Step 5: Run validation tests**

Run:

```powershell
uv run pytest tests/test_graduation_requirement_adapter.py tests/test_simple_evidence_units.py tests/test_dining_adapter.py tests/test_shuttle_adapter.py tests/test_prepare_from_sources.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add data/knowledge_seed.json data/source_parse_failures.json docs/data_readiness_report_2026_06_09.md docs/evidence/data-readiness-2026-06-09.json docs/source_fetch_audit_2026_06_08.md docs/evidence/source-fetch-audit-2026-06-08.json
git commit -m "data: simplify qwen evidence units"
```

---

## Self-Review

- Spec coverage:
  - Avoids heuristic confidence labels.
  - Keeps implementation simple.
  - Preserves ambiguous prose as raw evidence instead of deleting source material.
  - Treats shuttle segments as useful details, not trash.
- Placeholder scan:
  - No `TBD` or open-ended placeholder implementation steps.
- Type consistency:
  - Uses existing `KnowledgeDoc`, `row_type`, `generation_method`, and metadata fields already present in the repo.

## Stop Condition

Stop after Task 4 if:

- unsafe prose-derived graduation structured rows are no longer Qwen-ready;
- dining weekly bundles still exist;
- shuttle routes and segments still exist;
- focused tests pass;
- no confidence classifier or review-status schema was added.
