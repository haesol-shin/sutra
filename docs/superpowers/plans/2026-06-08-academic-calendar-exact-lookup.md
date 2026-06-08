# Academic Calendar Exact Lookup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Task 2 academic-calendar date questions require exact event evidence, so the harness answers `여름 계절학기 종강일` from a matched calendar period end date and fail-closes `이번 학기 종강일` when the required event is absent.

**Architecture:** Add a small deterministic academic-calendar event extractor and matcher before broad data expansion. The matcher converts existing calendar chunks such as `06.22(월) ~ 07.10(금) 하기 계절학기` into structured event evidence. Evidence sufficiency must stop treating loosely related calendar chunks as enough for exact `date_lookup` questions.

**Tech Stack:** Python 3.10.12, uv, Pydantic/dataclasses, existing `KnowledgeDoc`, current harness/orchestrator, pytest.

---

## Why This Is The Next Improvement

Qwen baseline after `max_tokens=1024` still shows:

- public probe 11, `이번 학기 종강일이 언제인가요?`, is marked `answered`, but the answer says the evidence does not contain the date. That should not count as a good answer.
- public probe 12, `이번 여름 계절학기 종강일이 언제인 가요?`, has enough existing evidence to infer `2026-07-10` from `06.22(월) ~ 07.10(금) 하기 계절학기`, but Qwen did not reliably use the period end as the requested end date.

This is not primarily a model-size issue. It is an evidence contract issue.

## Non-Goals

- Do not crawl new sources in this goal.
- Do not add embedding retrieval, BM25, reranking, or LangChain.
- Do not change Qwen model, server settings, or decoding parameters.
- Do not make broad Task 1 classifier changes here.
- Do not claim final Task 2 performance improvement; this is a targeted probe fix and sufficiency hardening.

## File Structure

- Create `src/nlp_term/chat/calendar_evidence.py`
  - Extracts structured calendar events from retrieved `KnowledgeDoc` rows.
  - Matches user questions to exact calendar events.
  - Builds a synthetic `KnowledgeDoc` when the match is exact.
- Modify `src/nlp_term/chat/orchestrator.py`
  - For `academic_calendar` + `date_lookup`, prefer exact calendar event evidence when available.
  - If the question requires an exact event and no exact event is found, fail-close before calling Qwen.
- Modify `src/nlp_term/chat/evidence_sufficiency.py`
  - Enforce exact event evidence for academic-calendar `date_lookup` questions.
- Modify `src/nlp_term/chat/state_contract.py`
  - Add a new failure reason only if needed through existing string field; no enum change is required.
- Test `tests/test_academic_calendar_exact_lookup.py`
  - Unit tests for extraction and matching.
  - Harness tests for public probe 11/12 behavior.
- Refresh:
  - `docs/evidence/task2-public-probe-harness-2026-06-08.json`
  - `docs/task2_public_probe_harness_diagnosis_2026_06_08.md`
  - `docs/evidence/task2-public-probe-qwen-baseline-2026-06-08.json`
  - `docs/task2_public_probe_qwen_baseline_2026_06_08.md`
- Modify `docs/task2_improvement_sequence_after_probe.md`
  - Record that academic-calendar exact lookup was inserted before broad data expansion.

## Expected Behavior Changes

| Probe | Current | Target |
| --- | --- | --- |
| public_probe_11 `이번 학기 종강일` | answered but says evidence missing | fail_closed until semester-end source exists |
| public_probe_12 `여름 계절학기 종강일` | answered but does not extract end date | answered with `2026-07-10` from matched period end |

---

## Task 1: Calendar Event Extraction Contract

**Files:**
- Create: `src/nlp_term/chat/calendar_evidence.py`
- Create: `tests/test_academic_calendar_exact_lookup.py`

- [ ] **Step 1: Write failing unit tests**

Create `tests/test_academic_calendar_exact_lookup.py`:

```python
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from nlp_term.chat.calendar_evidence import extract_calendar_events, match_calendar_event
from nlp_term.schemas import KnowledgeDoc


def _calendar_doc(doc_id: str, body: str) -> KnowledgeDoc:
    return KnowledgeDoc(
        doc_id=doc_id,
        label=2,
        domain="academic_calendar",
        title="학사일정",
        body=body,
        source_url="https://plus.cnu.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&site_dvs_cd=kr",
        source_id="academic_calendar",
    )


def test_extract_calendar_events_parses_period_end_date() -> None:
    docs = [_calendar_doc("calendar_9", "06.22(월) ~ 07.10(금) 하기 계절학기")]

    events = extract_calendar_events(
        docs,
        reference_time=datetime(2026, 6, 8, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert len(events) == 1
    assert events[0].source_doc_id == "calendar_9"
    assert events[0].event_name == "하기 계절학기"
    assert events[0].start_date == "2026-06-22"
    assert events[0].end_date == "2026-07-10"


def test_match_calendar_event_returns_period_end_for_summer_session_end_question() -> None:
    docs = [_calendar_doc("calendar_9", "06.22(월) ~ 07.10(금) 하기 계절학기")]
    events = extract_calendar_events(
        docs,
        reference_time=datetime(2026, 6, 8, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    match = match_calendar_event("이번 여름 계절학기 종강일이 언제인 가요?", events)

    assert match is not None
    assert match.answer_date == "2026-07-10"
    assert match.answer_basis == "period_end"
    assert match.event.event_name == "하기 계절학기"


def test_match_calendar_event_returns_none_when_semester_end_event_is_absent() -> None:
    docs = [
        _calendar_doc("calendar_4", "01.26(월) ~ 01.28(수) 2026학년도 제1학기 예비수강신청"),
        _calendar_doc("calendar_5", "02.02(월) ~ 02.06(금) 2026학년도 제1학기 수강신청"),
    ]
    events = extract_calendar_events(
        docs,
        reference_time=datetime(2026, 6, 8, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    match = match_calendar_event("이번 학기 종강일이 언제인가요?", events)

    assert match is None
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
uv run pytest tests/test_academic_calendar_exact_lookup.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'nlp_term.chat.calendar_evidence'
```

- [ ] **Step 3: Implement calendar event extraction**

Create `src/nlp_term/chat/calendar_evidence.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from nlp_term.schemas import KnowledgeDoc


PERIOD_RE = re.compile(
    r"(?P<start_month>\d{2})\.(?P<start_day>\d{2})\([^)]*\)\s*~\s*"
    r"(?P<end_month>\d{2})\.(?P<end_day>\d{2})\([^)]*\)\s*(?P<name>.+)"
)
SINGLE_DATE_RE = re.compile(r"(?P<month>\d{2})\.(?P<day>\d{2})\([^)]*\)\s*(?P<name>.+)")


@dataclass(frozen=True)
class CalendarEvent:
    source_doc_id: str
    source_url: str
    event_name: str
    start_date: str
    end_date: str
    raw_text: str


@dataclass(frozen=True)
class CalendarEventMatch:
    event: CalendarEvent
    answer_date: str
    answer_basis: str


def extract_calendar_events(docs: list[KnowledgeDoc], *, reference_time: datetime) -> list[CalendarEvent]:
    year = reference_time.year
    events: list[CalendarEvent] = []
    for doc in docs:
        if doc.domain != "academic_calendar":
            continue
        text = " ".join(doc.body.split())
        period = PERIOD_RE.search(text)
        if period:
            events.append(
                CalendarEvent(
                    source_doc_id=doc.doc_id,
                    source_url=doc.source_url,
                    event_name=period.group("name").strip(),
                    start_date=_iso_date(year, period.group("start_month"), period.group("start_day")),
                    end_date=_iso_date(year, period.group("end_month"), period.group("end_day")),
                    raw_text=text,
                )
            )
            continue
        single = SINGLE_DATE_RE.search(text)
        if single:
            date = _iso_date(year, single.group("month"), single.group("day"))
            events.append(
                CalendarEvent(
                    source_doc_id=doc.doc_id,
                    source_url=doc.source_url,
                    event_name=single.group("name").strip(),
                    start_date=date,
                    end_date=date,
                    raw_text=text,
                )
            )
    return events


def match_calendar_event(question: str, events: list[CalendarEvent]) -> CalendarEventMatch | None:
    compact = question.replace(" ", "")
    if "계절학기" in compact and any(token in compact for token in ("여름", "하기")) and "종강" in compact:
        for event in events:
            if "하기" in event.event_name and "계절학기" in event.event_name:
                return CalendarEventMatch(event=event, answer_date=event.end_date, answer_basis="period_end")
    if "수강신청" in compact:
        for event in events:
            event_compact = event.event_name.replace(" ", "")
            if "수강신청" in event_compact and "예비" not in event_compact:
                return CalendarEventMatch(event=event, answer_date=event.start_date, answer_basis="period_start")
    if "종강" in compact:
        for event in events:
            if any(token in event.event_name for token in ("종강", "수업종료", "수업 종료")):
                return CalendarEventMatch(event=event, answer_date=event.end_date, answer_basis="event_date")
    return None


def _iso_date(year: int, month: str, day: str) -> str:
    return f"{year:04d}-{int(month):02d}-{int(day):02d}"
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
uv run pytest tests/test_academic_calendar_exact_lookup.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```powershell
git add src/nlp_term/chat/calendar_evidence.py tests/test_academic_calendar_exact_lookup.py
git commit -m "feat: extract academic calendar events"
```

---

## Task 2: Harness Uses Exact Calendar Evidence

**Files:**
- Modify: `src/nlp_term/chat/orchestrator.py`
- Modify: `tests/test_academic_calendar_exact_lookup.py`

- [ ] **Step 1: Add failing harness tests**

Append to `tests/test_academic_calendar_exact_lookup.py`:

```python
from pathlib import Path
import json

from nlp_term.chat.orchestrator import answer_with_harness
from nlp_term.chat.state_contract import OutputStatus


def _write_knowledge(path: Path, docs: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(docs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_harness_injects_exact_summer_session_end_evidence(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    _write_knowledge(
        knowledge_path,
        [
            {
                "doc_id": "calendar_9",
                "label": 2,
                "domain": "academic_calendar",
                "title": "학사일정",
                "body": "06.22(월) ~ 07.10(금) 하기 계절학기",
                "source_url": "https://plus.cnu.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&site_dvs_cd=kr",
                "source_id": "academic_calendar",
                "metadata": {"chunk_confidence": "high"},
            }
        ],
    )
    captured: dict[str, str] = {}

    def writer(prompt: str) -> str:
        captured["prompt"] = prompt
        return "2026학년도 하기 계절학기 종강일은 2026년 7월 10일입니다."

    result = answer_with_harness(
        "이번 여름 계절학기 종강일이 언제인 가요?",
        knowledge_path=knowledge_path,
        generator=writer,
        question_time=datetime(2026, 6, 8, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert result.output_status == OutputStatus.ANSWERED
    assert "2026-07-10" in captured["prompt"]
    assert result.trace.retrieved_doc_ids[0] == "calendar_9__exact_calendar_match"


def test_harness_fails_closed_when_semester_end_event_is_absent(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    _write_knowledge(
        knowledge_path,
        [
            {
                "doc_id": "calendar_5",
                "label": 2,
                "domain": "academic_calendar",
                "title": "학사일정",
                "body": "02.02(월) ~ 02.06(금) 2026학년도 제1학기 수강신청",
                "source_url": "https://plus.cnu.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&site_dvs_cd=kr",
                "source_id": "academic_calendar",
                "metadata": {"chunk_confidence": "high"},
            }
        ],
    )

    result = answer_with_harness(
        "이번 학기 종강일이 언제인가요?",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "이번 학기 종강일은 2026년 6월 19일입니다.",
        question_time=datetime(2026, 6, 8, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert result.output_status == OutputStatus.FAIL_CLOSED
    assert "2026년 6월 19일" not in result.output.model
    assert result.trace.failure_reason == "exact_calendar_event_missing"
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
uv run pytest tests/test_academic_calendar_exact_lookup.py::test_harness_injects_exact_summer_session_end_evidence tests/test_academic_calendar_exact_lookup.py::test_harness_fails_closed_when_semester_end_event_is_absent -q
```

Expected:

```text
FAIL
```

The first test should fail because no synthetic exact calendar evidence is injected. The second should fail because the current sufficiency path treats loose calendar chunks as sufficient.

- [ ] **Step 3: Add exact calendar evidence helper in orchestrator**

In `src/nlp_term/chat/orchestrator.py`, import:

```python
from nlp_term.chat.calendar_evidence import extract_calendar_events, match_calendar_event
```

Add this helper near `_selected_candidate_trace_rows()`:

```python
def _exact_calendar_doc(
    question: str,
    docs: list[KnowledgeDoc],
    *,
    question_time: datetime,
) -> KnowledgeDoc | None:
    events = extract_calendar_events(docs, reference_time=question_time)
    match = match_calendar_event(question, events)
    if match is None:
        return None
    event = match.event
    return KnowledgeDoc(
        doc_id=f"{event.source_doc_id}__exact_calendar_match",
        label=2,
        domain="academic_calendar",
        title="학사일정 정확 일자",
        body=(
            f"{event.event_name}의 기준 기간은 {event.start_date}부터 {event.end_date}까지입니다. "
            f"질문에서 요구한 날짜는 {match.answer_date}입니다."
        ),
        date=match.answer_date,
        source_url=event.source_url,
        source_id="academic_calendar",
        metadata={
            "calendar_event_name": event.event_name,
            "calendar_start_date": event.start_date,
            "calendar_end_date": event.end_date,
            "calendar_answer_date": match.answer_date,
            "calendar_answer_basis": match.answer_basis,
            "source_doc_id": event.source_doc_id,
            "structured_fields": ["calendar_event_name", "calendar_start_date", "calendar_end_date", "calendar_answer_date"],
            "chunk_confidence": "high",
        },
    )
```

- [ ] **Step 4: Use exact calendar doc before sufficiency**

In `answer_with_harness()`, after `retrieved_docs` and `retrieved_scores` are built and before `source_statuses`, add:

```python
    exact_calendar_required = (
        route_domain == "academic_calendar"
        and temporal_intent.temporal_type == "date_lookup"
        and any(token in question.replace(" ", "") for token in ("종강일", "수강신청"))
    )
    exact_calendar_doc = None
    if exact_calendar_required:
        exact_calendar_doc = _exact_calendar_doc(
            question,
            retrieved_docs,
            question_time=resolved_question_time,
        )
        if exact_calendar_doc is not None:
            retrieved_docs = [exact_calendar_doc, *retrieved_docs]
            retrieved_scores = [1.0, *retrieved_scores]
            postfilter_candidates = [
                RetrievalCandidateTrace(
                    doc_id=exact_calendar_doc.doc_id,
                    score=1.0,
                    label=exact_calendar_doc.label,
                    domain=exact_calendar_doc.domain,
                    source_id=exact_calendar_doc.source_id,
                    chunking_strategy="exact_calendar_match",
                    boundary_type="calendar_event",
                    chunk_confidence="high",
                ),
                *postfilter_candidates,
            ]
```

Also pass `exact_calendar_required=exact_calendar_required` and `exact_calendar_matched=exact_calendar_doc is not None` into `evaluate_evidence_sufficiency()`. That change is implemented in Task 3.

- [ ] **Step 5: Run first harness test**

Run:

```powershell
uv run pytest tests/test_academic_calendar_exact_lookup.py::test_harness_injects_exact_summer_session_end_evidence -q
```

Expected:

```text
PASS
```

- [ ] **Step 6: Commit**

```powershell
git add src/nlp_term/chat/orchestrator.py tests/test_academic_calendar_exact_lookup.py
git commit -m "feat: inject exact academic calendar evidence"
```

---

## Task 3: Exact Date Lookup Sufficiency Gate

**Files:**
- Modify: `src/nlp_term/chat/evidence_sufficiency.py`
- Modify: `src/nlp_term/chat/orchestrator.py`
- Test: `tests/test_academic_calendar_exact_lookup.py`

- [ ] **Step 1: Extend sufficiency signature**

Modify `evaluate_evidence_sufficiency()` signature:

```python
def evaluate_evidence_sufficiency(
    *,
    answer_kind: AnswerKind,
    docs: list[KnowledgeDoc],
    retrieved_scores: list[float],
    source_statuses: list[SourceStatus],
    candidate_specs: Iterable[SourceSpec],
    route_domain: Domain,
    min_top_score: float = 0.20,
    question_time: datetime | None = None,
    temporal_intent: TemporalIntent | None = None,
    exact_calendar_required: bool = False,
    exact_calendar_matched: bool = False,
) -> EvidenceSufficiencyDecision:
```

- [ ] **Step 2: Add exact calendar fail-closed rule**

In `evaluate_evidence_sufficiency()`, after `if not docs:` and before source-navigation shortcut:

```python
    if exact_calendar_required and not exact_calendar_matched:
        return EvidenceSufficiencyDecision(
            status=EvidenceSufficiencyStatus.INSUFFICIENT,
            fetch_decision=FetchDecision.FETCH_REQUIRED_BUT_NOT_IMPLEMENTED,
            freshness_status=FreshnessStatus.UNKNOWN,
            reasons=["exact_calendar_event_missing"],
        )
```

- [ ] **Step 3: Pass flags from orchestrator**

In `answer_with_harness()`, update the `evaluate_evidence_sufficiency()` call:

```python
        exact_calendar_required=exact_calendar_required,
        exact_calendar_matched=exact_calendar_doc is not None,
```

- [ ] **Step 4: Run missing-event test**

Run:

```powershell
uv run pytest tests/test_academic_calendar_exact_lookup.py::test_harness_fails_closed_when_semester_end_event_is_absent -q
```

Expected:

```text
PASS
```

- [ ] **Step 5: Run related tests**

Run:

```powershell
uv run pytest tests/test_academic_calendar_exact_lookup.py tests/test_phase_a_harness_contract.py tests/test_public_probe_experiment.py -q
```

Expected:

```text
PASS
```

- [ ] **Step 6: Commit**

```powershell
git add src/nlp_term/chat/evidence_sufficiency.py src/nlp_term/chat/orchestrator.py tests/test_academic_calendar_exact_lookup.py
git commit -m "fix: require exact academic calendar event evidence"
```

---

## Task 4: Refresh Public Probe Diagnostics

**Files:**
- Modify: `docs/evidence/task2-public-probe-harness-2026-06-08.json`
- Modify: `docs/task2_public_probe_harness_diagnosis_2026_06_08.md`

- [ ] **Step 1: Regenerate deterministic harness public probe**

Run:

```powershell
uv run python -X utf8 -m nlp_term.chat.public_probe_experiment --probe data/gold/task2_public_probe_eval.json --knowledge data/knowledge_seed.json --output docs/evidence/task2-public-probe-harness-2026-06-08.json --markdown docs/task2_public_probe_harness_diagnosis_2026_06_08.md
```

Expected:

```text
wrote docs\evidence\task2-public-probe-harness-2026-06-08.json
wrote docs\task2_public_probe_harness_diagnosis_2026_06_08.md
```

- [ ] **Step 2: Check targeted public probe behavior**

Run:

```powershell
$r = Get-Content docs\evidence\task2-public-probe-harness-2026-06-08.json | ConvertFrom-Json
$r.rows | Where-Object {$_.id -in @("public_probe_11","public_probe_12")} |
  Select-Object id,output_status,bottleneck,failure_reason,retrieved_doc_ids,answer |
  Format-List
```

Expected:

```text
public_probe_11: fail_closed, failure_reason exact_calendar_event_missing
public_probe_12: answered, answer or evidence contains 2026-07-10
```

- [ ] **Step 3: Commit deterministic artifacts**

```powershell
git add docs/evidence/task2-public-probe-harness-2026-06-08.json docs/task2_public_probe_harness_diagnosis_2026_06_08.md
git commit -m "test: refresh calendar exact lookup probe diagnostics"
```

---

## Task 5: Refresh Qwen Baseline With Existing Llama Server Workflow

**Files:**
- Modify: `docs/evidence/task2-public-probe-qwen-baseline-2026-06-08.json`
- Modify: `docs/task2_public_probe_qwen_baseline_2026_06_08.md`

- [ ] **Step 1: Start llama-server if not already running**

Run:

```powershell
$llama = (& uv run python -X utf8 -c "from nlp_term.llm.env_probe import executable_path; print(executable_path('llama-server') or '')").Trim()
$model = "model\generator\Qwen3.5-9B-Q4_K_M.gguf"
Start-Process -FilePath $llama -ArgumentList @("-m", $model, "-c", "4096", "-ngl", "auto", "--cache-type-k", "q8_0", "--cache-type-v", "q8_0", "--host", "127.0.0.1", "--port", "18080", "--reasoning", "off", "--reasoning-budget", "0") -RedirectStandardOutput "model\llama_server_18080.out.log" -RedirectStandardError "model\llama_server_18080.err.log" -WindowStyle Hidden
```

- [ ] **Step 2: Health check**

Run:

```powershell
Invoke-WebRequest http://127.0.0.1:18080/health -UseBasicParsing
```

Expected status code:

```text
200
```

- [ ] **Step 3: Regenerate Qwen baseline**

Run:

```powershell
uv run python -X utf8 -m nlp_term.chat.qwen_public_probe_baseline --probe data/gold/task2_public_probe_eval.json --knowledge data/knowledge_seed.json --output docs/evidence/task2-public-probe-qwen-baseline-2026-06-08.json --markdown docs/task2_public_probe_qwen_baseline_2026_06_08.md --llama-server-url http://127.0.0.1:18080 --timeout-seconds 300
```

Expected:

```text
writer_called remains limited to questions passing harness sufficiency
max_tokens remains 1024
public_probe_12 answer includes 2026-07-10
public_probe_11 is fail_closed
```

- [ ] **Step 4: Stop llama-server**

Run:

```powershell
Get-Process | Where-Object { $_.ProcessName -like '*llama*' } | Stop-Process
```

- [ ] **Step 5: Commit Qwen artifacts**

```powershell
git add docs/evidence/task2-public-probe-qwen-baseline-2026-06-08.json docs/task2_public_probe_qwen_baseline_2026_06_08.md
git commit -m "test: refresh qwen calendar exact lookup baseline"
```

---

## Task 6: Document Result And Next Data Expansion Boundary

**Files:**
- Modify: `docs/task2_improvement_sequence_after_probe.md`

- [ ] **Step 1: Add result section**

Add under the Qwen baseline section:

```markdown
### Academic Calendar Exact Lookup Result

The next improvement after Qwen baseline was academic-calendar exact lookup. It prevents exact date questions from being counted as answered when the evidence only contains loosely related calendar chunks.

Targeted outcome:

- `public_probe_11` now fail-closes until a `이번 학기 종강일` source row exists.
- `public_probe_12` uses the existing `하기 계절학기` period row and exposes `2026-07-10` as the period end date.

This confirms that the next broad work should be source expansion and parser hardening, not Qwen prompt tuning.
```

- [ ] **Step 2: Run docs grep**

Run:

```powershell
rg -n "Academic Calendar Exact Lookup|public_probe_11|public_probe_12|2026-07-10" docs/task2_improvement_sequence_after_probe.md docs/task2_public_probe_qwen_baseline_2026_06_08.md
```

Expected:

```text
All target strings are present.
```

- [ ] **Step 3: Commit docs**

```powershell
git add docs/task2_improvement_sequence_after_probe.md
git commit -m "docs: record academic calendar exact lookup result"
```

---

## Task 7: Final Verification And Critic Review

**Files:**
- No new files.

- [ ] **Step 1: Run full tests**

Run:

```powershell
uv run pytest -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 2: Inspect git status**

Run:

```powershell
git status --short
```

Expected:

```text
Only pre-existing unrelated dirty files remain.
```

- [ ] **Step 3: Request critic review**

Ask the existing critic to review:

```text
Review academic-calendar exact lookup implementation.
Check that:
1. exact date questions no longer pass sufficiency from loosely related calendar chunks;
2. public_probe_12 uses 2026-07-10 from the period end;
3. public_probe_11 fail-closes until data expansion adds the missing semester-end row;
4. no broad retrieval, Qwen prompt, or unrelated classifier behavior changed.
Return PASS or REQUEST CHANGES with concrete file/line issues.
```

If critic returns `REQUEST CHANGES`, open the 5-agent meeting workflow before continuing.

## Self-Review

- Spec coverage: The plan targets the next highest-risk issue from the Qwen baseline: false answered status for exact calendar questions. It directly covers probes 11 and 12.
- Placeholder scan: No task uses `TBD`, `TODO`, or vague “add tests” instructions. Each code task includes concrete code or commands.
- Type consistency: `CalendarEvent`, `CalendarEventMatch`, `extract_calendar_events`, and `match_calendar_event` are defined before use. `KnowledgeDoc` fields match `src/nlp_term/schemas.py`.
- Scope control: This plan deliberately does not crawl new data, tune Qwen, or introduce hybrid RAG. Broad data expansion remains the next goal after this sufficiency hardening.
