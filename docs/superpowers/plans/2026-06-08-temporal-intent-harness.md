# Temporal Intent Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic temporal intent handling to the Task 2/Task 3 harness so single-turn campus questions resolve dates, route retrieval, validate evidence, and produce natural answers without exposing internal reasoning.

**Architecture:** Introduce a focused temporal parser that produces `TemporalIntent` before retrieval. The orchestrator will use `TemporalIntent` to choose retrieval requirements, evidence sufficiency will verify date/freshness/version needs after RAG, and the prompt will expose only a short user-safe time context to Qwen. Qwen remains a writer, not a tool-calling planner.

**Tech Stack:** Python 3.10.12, `uv`, Pydantic models, existing `src/nlp_term/chat` harness, pytest.

---

## File Structure

- Create `src/nlp_term/chat/temporal_intent.py`: deterministic temporal expression parser and routing requirement builder.
- Modify `src/nlp_term/chat/state_contract.py`: add temporal enums/models and trace fields.
- Modify `src/nlp_term/chat/orchestrator.py`: call temporal parser, pass temporal state into retrieval/evidence/prompt/trace.
- Modify `src/nlp_term/chat/evidence_sufficiency.py`: make sufficiency aware of temporal retrieval requirements, freshness, and version matching.
- Modify `src/nlp_term/chat/evidence_pack.py`: carry user-safe temporal context into prompt text.
- Modify `src/nlp_term/chat/prompts.py`: tell Qwen to use the rendered time context without exposing internal trace words.
- Modify `src/nlp_term/chat/answer_validation.py`: reject internal temporal/trace leakage and unsupported target-date claims.
- Create `tests/test_temporal_intent.py`: parser and confidence tests.
- Modify `tests/test_phase_a_harness_contract.py`: orchestrator/evidence integration tests.
- Create `data/gold/task2_public_probe_eval.json`: fixed 14-question public probe set from the discussion.
- Create `tests/test_task2_public_probe_contract.py`: validate the public probe schema and expected temporal labels.
- Modify `docs/task2_task3_harness_architecture.md`: document the approved temporal design and routing policy.

## Task 1: Temporal Contract Types

**Files:**
- Modify: `src/nlp_term/chat/state_contract.py`
- Test: `tests/test_temporal_intent.py`

- [ ] **Step 1: Write the failing enum/model tests**

Add `tests/test_temporal_intent.py` with the initial contract check:

```python
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from nlp_term.chat.state_contract import (
    TemporalConfidence,
    TemporalIntent,
    TemporalType,
    RetrievalRequirement,
)


def test_temporal_intent_contract_stores_iso_week_resolution() -> None:
    intent = TemporalIntent(
        reference_time=datetime(2026, 6, 8, tzinfo=ZoneInfo("Asia/Seoul")),
        timezone="Asia/Seoul",
        week_policy="iso_monday_to_sunday",
        original_expression="다음주 화요일",
        temporal_type=TemporalType.FUTURE_SCHEDULE,
        explicitness="relative",
        target_start=date(2026, 6, 16),
        target_end=date(2026, 6, 16),
        granularity="day",
        resolution_policy="next_iso_week_weekday",
        freshness_required=True,
        version_match_required=False,
        retrieval_requirements=[
            RetrievalRequirement.DATE_FILTERED_EVIDENCE_NEEDED,
            RetrievalRequirement.STRUCTURED_SOURCE_PREFERRED,
        ],
        confidence=TemporalConfidence.HIGH,
        confidence_reasons=["relative_weekday_expression_resolved", "single_day_target"],
    )

    assert intent.week_policy == "iso_monday_to_sunday"
    assert intent.target_start.isoformat() == "2026-06-16"
    assert intent.retrieval_requirements == [
        RetrievalRequirement.DATE_FILTERED_EVIDENCE_NEEDED,
        RetrievalRequirement.STRUCTURED_SOURCE_PREFERRED,
    ]
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
uv run pytest tests/test_temporal_intent.py::test_temporal_intent_contract_stores_iso_week_resolution -q
```

Expected: fail with import errors for the new temporal types.

- [ ] **Step 3: Add the temporal enums and model**

In `src/nlp_term/chat/state_contract.py`, add these definitions near the other `_StrEnum` classes:

```python
class TemporalType(_StrEnum):
    NONE = "none"
    DATE_LOOKUP = "date_lookup"
    CURRENT_SNAPSHOT = "current_snapshot"
    FUTURE_SCHEDULE = "future_schedule"
    LATEST_ITEM = "latest_item"
    CHANGED_SINCE = "changed_since"
    ONGOING_STATUS = "ongoing_status"
    PERIOD_SUMMARY = "period_summary"


class TemporalConfidence(_StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RetrievalRequirement(_StrEnum):
    RAG_OK = "rag_ok"
    DATE_FILTERED_EVIDENCE_NEEDED = "date_filtered_evidence_needed"
    LATEST_LIST_NEEDED = "latest_list_needed"
    STRUCTURED_SOURCE_PREFERRED = "structured_source_preferred"
    VERSION_MATCH_NEEDED = "version_match_needed"
    CHANGE_WINDOW_NEEDED = "change_window_needed"
```

Then add the model below `IntentState`:

```python
class TemporalIntent(BaseModel):
    reference_time: datetime
    timezone: str = "Asia/Seoul"
    week_policy: Literal["iso_monday_to_sunday"] = "iso_monday_to_sunday"
    original_expression: str | None = None
    temporal_type: TemporalType = TemporalType.NONE
    explicitness: Literal["none", "absolute", "relative", "mixed_conflict"] = "none"
    target_start: date | None = None
    target_end: date | None = None
    granularity: Literal["none", "day", "week", "month", "semester", "year"] = "none"
    resolution_policy: str | None = None
    freshness_required: bool = False
    version_match_required: bool = False
    retrieval_requirements: list[RetrievalRequirement] = Field(default_factory=lambda: [RetrievalRequirement.RAG_OK])
    confidence: TemporalConfidence = TemporalConfidence.HIGH
    confidence_reasons: list[str] = Field(default_factory=list)
```

Also import `date` at the top:

```python
from datetime import date, datetime
```

- [ ] **Step 4: Run the contract test**

Run:

```powershell
uv run pytest tests/test_temporal_intent.py::test_temporal_intent_contract_stores_iso_week_resolution -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/nlp_term/chat/state_contract.py tests/test_temporal_intent.py
git commit -m "feat: add temporal intent contract"
```

## Task 2: Deterministic Temporal Parser

**Files:**
- Create: `src/nlp_term/chat/temporal_intent.py`
- Modify: `tests/test_temporal_intent.py`

- [ ] **Step 1: Add parser tests for approved examples**

Append these tests to `tests/test_temporal_intent.py`:

```python
from nlp_term.chat.temporal_intent import resolve_temporal_intent


REFERENCE_TIME = datetime(2026, 6, 8, tzinfo=ZoneInfo("Asia/Seoul"))


def test_next_week_tuesday_uses_iso_week_policy() -> None:
    intent = resolve_temporal_intent(
        "다음주 화요일 2학생회관 메뉴가 어떻게 되나요?",
        route_domain="dining",
        reference_time=REFERENCE_TIME,
    )

    assert intent.temporal_type == TemporalType.FUTURE_SCHEDULE
    assert intent.target_start == date(2026, 6, 16)
    assert intent.target_end == date(2026, 6, 16)
    assert intent.confidence == TemporalConfidence.HIGH
    assert RetrievalRequirement.DATE_FILTERED_EVIDENCE_NEEDED in intent.retrieval_requirements
    assert RetrievalRequirement.STRUCTURED_SOURCE_PREFERRED in intent.retrieval_requirements


def test_changed_since_defaults_to_recent_30_day_window() -> None:
    intent = resolve_temporal_intent(
        "최근에 바뀐 학사일정 있어요?",
        route_domain="academic_calendar",
        reference_time=REFERENCE_TIME,
    )

    assert intent.temporal_type == TemporalType.CHANGED_SINCE
    assert intent.target_start == date(2026, 5, 9)
    assert intent.target_end == date(2026, 6, 8)
    assert intent.confidence == TemporalConfidence.MEDIUM
    assert RetrievalRequirement.CHANGE_WINDOW_NEEDED in intent.retrieval_requirements


def test_graduation_credit_question_has_no_temporal_requirement() -> None:
    intent = resolve_temporal_intent(
        "졸업까지 몇 학점 들어야 하나요?",
        route_domain="graduation",
        reference_time=REFERENCE_TIME,
    )

    assert intent.temporal_type == TemporalType.NONE
    assert intent.freshness_required is False
    assert intent.target_start is None
    assert intent.retrieval_requirements == [RetrievalRequirement.RAG_OK]
```

- [ ] **Step 2: Run parser tests and confirm they fail**

Run:

```powershell
uv run pytest tests/test_temporal_intent.py -q
```

Expected: fail because `temporal_intent.py` does not exist.

- [ ] **Step 3: Implement the minimal parser**

Create `src/nlp_term/chat/temporal_intent.py`:

```python
from __future__ import annotations

from datetime import date, datetime, timedelta
import re

from nlp_term.chat.state_contract import (
    RetrievalRequirement,
    TemporalConfidence,
    TemporalIntent,
    TemporalType,
)
from nlp_term.schemas import Domain


KST_TIMEZONE = "Asia/Seoul"
WEEKDAY_INDEX = {
    "월요일": 0,
    "월": 0,
    "화요일": 1,
    "화": 1,
    "수요일": 2,
    "수": 2,
    "목요일": 3,
    "목": 3,
    "금요일": 4,
    "금": 4,
    "토요일": 5,
    "토": 5,
    "일요일": 6,
    "일": 6,
}


def resolve_temporal_intent(
    question: str,
    *,
    route_domain: Domain,
    reference_time: datetime,
) -> TemporalIntent:
    compact = question.replace(" ", "")
    reference_date = reference_time.date()

    changed = _is_changed_since(compact)
    if changed:
        start = reference_date - timedelta(days=30)
        return TemporalIntent(
            reference_time=reference_time,
            original_expression=_original_expression(question, default="최근"),
            temporal_type=TemporalType.CHANGED_SINCE,
            explicitness="relative",
            target_start=start,
            target_end=reference_date,
            granularity="day",
            resolution_policy="recent_30_days_default",
            freshness_required=True,
            retrieval_requirements=[
                RetrievalRequirement.DATE_FILTERED_EVIDENCE_NEEDED,
                RetrievalRequirement.CHANGE_WINDOW_NEEDED,
            ],
            confidence=TemporalConfidence.MEDIUM,
            confidence_reasons=["ambiguous_recent_resolved_by_30_day_policy", f"domain_{route_domain}"],
        )

    weekday = _extract_weekday(compact)
    if "다음주" in compact and weekday is not None:
        target = _iso_week_start(reference_date) + timedelta(days=7 + weekday)
        return TemporalIntent(
            reference_time=reference_time,
            original_expression=_original_expression(question, default="다음주"),
            temporal_type=_schedule_type(route_domain, compact, granularity="day"),
            explicitness="relative",
            target_start=target,
            target_end=target,
            granularity="day",
            resolution_policy="next_iso_week_weekday",
            freshness_required=route_domain in {"dining", "shuttle", "notices", "academic_calendar"},
            retrieval_requirements=_requirements_for(route_domain, TemporalType.FUTURE_SCHEDULE),
            confidence=TemporalConfidence.HIGH,
            confidence_reasons=["relative_weekday_expression_resolved", f"domain_{route_domain}", "single_day_target"],
        )

    if "다음주" in compact:
        start = _iso_week_start(reference_date) + timedelta(days=7)
        end = start + timedelta(days=6)
        return TemporalIntent(
            reference_time=reference_time,
            original_expression=_original_expression(question, default="다음주"),
            temporal_type=TemporalType.PERIOD_SUMMARY,
            explicitness="relative",
            target_start=start,
            target_end=end,
            granularity="week",
            resolution_policy="next_iso_week",
            freshness_required=route_domain in {"dining", "shuttle", "notices", "academic_calendar"},
            retrieval_requirements=_requirements_for(route_domain, TemporalType.PERIOD_SUMMARY),
            confidence=TemporalConfidence.HIGH,
            confidence_reasons=["relative_week_expression_resolved", f"domain_{route_domain}", "week_range_target"],
        )

    if any(token in compact for token in ("오늘", "현재", "지금")):
        return TemporalIntent(
            reference_time=reference_time,
            original_expression=_original_expression(question, default="오늘"),
            temporal_type=TemporalType.CURRENT_SNAPSHOT,
            explicitness="relative",
            target_start=reference_date,
            target_end=reference_date,
            granularity="day",
            resolution_policy="current_date",
            freshness_required=True,
            retrieval_requirements=_requirements_for(route_domain, TemporalType.CURRENT_SNAPSHOT),
            confidence=TemporalConfidence.HIGH,
            confidence_reasons=["current_expression_resolved", f"domain_{route_domain}"],
        )

    if route_domain == "academic_calendar" and any(token in compact for token in ("이번학기", "종강일", "수강신청")):
        return TemporalIntent(
            reference_time=reference_time,
            original_expression=_original_expression(question, default="이번 학기"),
            temporal_type=TemporalType.DATE_LOOKUP,
            explicitness="relative",
            granularity="semester",
            resolution_policy="academic_semester_lookup_required",
            freshness_required=False,
            retrieval_requirements=[RetrievalRequirement.DATE_FILTERED_EVIDENCE_NEEDED],
            confidence=TemporalConfidence.MEDIUM,
            confidence_reasons=["academic_calendar_event_lookup", "semester_requires_calendar_evidence"],
        )

    version_match = route_domain == "graduation" and bool(re.search(r"\\d{2,4}학번|\\d{4}", compact))
    requirements = [RetrievalRequirement.VERSION_MATCH_NEEDED] if version_match else [RetrievalRequirement.RAG_OK]
    return TemporalIntent(
        reference_time=reference_time,
        temporal_type=TemporalType.NONE,
        version_match_required=version_match,
        retrieval_requirements=requirements,
        confidence=TemporalConfidence.HIGH,
        confidence_reasons=["no_temporal_expression_detected"],
    )


def _iso_week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _extract_weekday(compact: str) -> int | None:
    for text, index in sorted(WEEKDAY_INDEX.items(), key=lambda item: len(item[0]), reverse=True):
        if text in compact:
            return index
    return None


def _is_changed_since(compact: str) -> bool:
    change_cues = ("바뀐", "변동", "변경", "업데이트", "새로")
    range_cues = ("최근", "이후", "부터")
    return any(cue in compact for cue in change_cues) and any(cue in compact for cue in range_cues)


def _schedule_type(route_domain: Domain, compact: str, *, granularity: str) -> TemporalType:
    if route_domain == "shuttle" and any(token in compact for token in ("정상운행", "운행하", "운영하")):
        return TemporalType.ONGOING_STATUS
    if granularity == "day":
        return TemporalType.FUTURE_SCHEDULE
    return TemporalType.PERIOD_SUMMARY


def _requirements_for(route_domain: Domain, temporal_type: TemporalType) -> list[RetrievalRequirement]:
    requirements = [RetrievalRequirement.DATE_FILTERED_EVIDENCE_NEEDED]
    if route_domain in {"dining", "shuttle"} or temporal_type in {TemporalType.CURRENT_SNAPSHOT, TemporalType.FUTURE_SCHEDULE}:
        requirements.append(RetrievalRequirement.STRUCTURED_SOURCE_PREFERRED)
    if temporal_type == TemporalType.LATEST_ITEM:
        requirements.append(RetrievalRequirement.LATEST_LIST_NEEDED)
    return requirements


def _original_expression(question: str, *, default: str) -> str:
    for token in ("다음주 화요일", "다음주", "이번 학기", "오늘", "최근"):
        if token in question:
            return token
    return default
```

- [ ] **Step 4: Run temporal parser tests**

Run:

```powershell
uv run pytest tests/test_temporal_intent.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/nlp_term/chat/temporal_intent.py tests/test_temporal_intent.py
git commit -m "feat: resolve temporal intent deterministically"
```

## Task 3: Orchestrator Integration and Trace

**Files:**
- Modify: `src/nlp_term/chat/state_contract.py`
- Modify: `src/nlp_term/chat/orchestrator.py`
- Modify: `tests/test_phase_a_harness_contract.py`

- [ ] **Step 1: Add integration tests**

Append to `tests/test_phase_a_harness_contract.py`:

```python
def test_harness_trace_records_next_week_temporal_intent(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        "["
        "{"
        '"doc_id":"dining_doc",'
        '"label":3,'
        '"domain":"dining",'
        '"title":"식단",'
        '"body":"2026-06-16 2학생회관 점심 메뉴는 공식 식단 페이지에서 확인한다.",'
        '"source_url":"https://mobileadmin.cnu.ac.kr/food/index.jsp",'
        '"source_id":"cnu_mobile_food",'
        '"metadata":{"menu_date":"2026-06-16","location":"2학생회관","raw_fetched_at":"2026-06-08T00:00:00+09:00"}'
        "}"
        "]",
        encoding="utf-8",
    )

    result = answer_with_harness(
        "다음주 화요일 2학생회관 메뉴가 어떻게 되나요?",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "다음주 화요일인 2026년 6월 16일 2학생회관 메뉴는 공식 식단 페이지에서 확인하면 됩니다.",
        question_time=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )

    assert result.trace.temporal_type == "future_schedule"
    assert result.trace.temporal_confidence == "high"
    assert result.trace.target_start == "2026-06-16"
    assert result.trace.target_end == "2026-06-16"
    assert "date_filtered_evidence_needed" in result.trace.retrieval_requirements
```

- [ ] **Step 2: Run the failing integration test**

Run:

```powershell
uv run pytest tests/test_phase_a_harness_contract.py::test_harness_trace_records_next_week_temporal_intent -q
```

Expected: fail because `HarnessTrace` has no temporal fields and orchestrator does not call the parser.

- [ ] **Step 3: Add temporal trace fields**

In `src/nlp_term/chat/state_contract.py`, add to `HarnessTrace`:

```python
    temporal_type: TemporalType = TemporalType.NONE
    temporal_confidence: TemporalConfidence = TemporalConfidence.HIGH
    temporal_confidence_reasons: list[str] = Field(default_factory=list)
    target_start: str | None = None
    target_end: str | None = None
    retrieval_requirements: list[RetrievalRequirement] = Field(default_factory=list)
```

- [ ] **Step 4: Wire temporal parsing into orchestrator**

In `src/nlp_term/chat/orchestrator.py`, import:

```python
from datetime import datetime, timezone
from nlp_term.chat.temporal_intent import resolve_temporal_intent
```

Inside `answer_with_harness`, after `route_domain` is set, add:

```python
    resolved_question_time = question_time or datetime.now(timezone.utc)
    temporal_intent = resolve_temporal_intent(
        question,
        route_domain=route_domain,
        reference_time=resolved_question_time,
    )
```

Pass `temporal_intent=temporal_intent` into every `_build_trace(...)` call.

Update `_build_trace` signature:

```python
    temporal_intent,
```

Then set the trace fields:

```python
        temporal_type=temporal_intent.temporal_type,
        temporal_confidence=temporal_intent.confidence,
        temporal_confidence_reasons=temporal_intent.confidence_reasons,
        target_start=temporal_intent.target_start.isoformat() if temporal_intent.target_start else None,
        target_end=temporal_intent.target_end.isoformat() if temporal_intent.target_end else None,
        retrieval_requirements=temporal_intent.retrieval_requirements,
```

- [ ] **Step 5: Run the integration test**

Run:

```powershell
uv run pytest tests/test_phase_a_harness_contract.py::test_harness_trace_records_next_week_temporal_intent -q
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/nlp_term/chat/state_contract.py src/nlp_term/chat/orchestrator.py tests/test_phase_a_harness_contract.py
git commit -m "feat: trace temporal intent in harness"
```

## Task 4: Evidence Sufficiency Uses Temporal Requirements

**Files:**
- Modify: `src/nlp_term/chat/evidence_sufficiency.py`
- Modify: `src/nlp_term/chat/orchestrator.py`
- Modify: `tests/test_phase_a_harness_contract.py`

- [ ] **Step 1: Add evidence checks for target-date mismatch**

Append to `tests/test_phase_a_harness_contract.py`:

```python
def test_harness_blocks_dining_evidence_for_wrong_target_date(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        "["
        "{"
        '"doc_id":"dining_doc",'
        '"label":3,'
        '"domain":"dining",'
        '"title":"식단",'
        '"body":"2026-06-09 2학생회관 점심 메뉴는 백반입니다.",'
        '"source_url":"https://mobileadmin.cnu.ac.kr/food/index.jsp",'
        '"source_id":"cnu_mobile_food",'
        '"metadata":{"menu_date":"2026-06-09","location":"2학생회관","raw_fetched_at":"2026-06-08T00:00:00+09:00"}'
        "}"
        "]",
        encoding="utf-8",
    )

    result = answer_with_harness(
        "다음주 화요일 2학생회관 메뉴가 어떻게 되나요?",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "2026년 6월 9일 2학생회관 점심은 백반입니다.",
        question_time=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )

    assert result.output_status == OutputStatus.FAIL_CLOSED
    assert result.trace.target_start == "2026-06-16"
    assert result.trace.evidence_sufficiency_status == EvidenceSufficiencyStatus.INSUFFICIENT
    assert "백반" not in result.output.model
```

- [ ] **Step 2: Run the failing evidence test**

Run:

```powershell
uv run pytest tests/test_phase_a_harness_contract.py::test_harness_blocks_dining_evidence_for_wrong_target_date -q
```

Expected: fail because evidence sufficiency does not compare `menu_date` to `target_start`.

- [ ] **Step 3: Pass temporal intent into evidence sufficiency**

In `src/nlp_term/chat/evidence_sufficiency.py`, import:

```python
from nlp_term.chat.state_contract import RetrievalRequirement, TemporalIntent
```

Add a parameter to `evaluate_evidence_sufficiency`:

```python
    temporal_intent: TemporalIntent | None = None,
```

In `src/nlp_term/chat/orchestrator.py`, pass:

```python
        temporal_intent=temporal_intent,
```

- [ ] **Step 4: Implement target-date requirement check**

In `src/nlp_term/chat/evidence_sufficiency.py`, before the final sufficient return, add:

```python
    if temporal_intent and RetrievalRequirement.DATE_FILTERED_EVIDENCE_NEEDED in temporal_intent.retrieval_requirements:
        if not _docs_match_temporal_target(docs, temporal_intent=temporal_intent):
            return EvidenceSufficiencyDecision(
                status=EvidenceSufficiencyStatus.INSUFFICIENT,
                fetch_decision=FetchDecision.FETCH_REQUIRED_BUT_NOT_IMPLEMENTED,
                freshness_status=FreshnessStatus.UNKNOWN,
                reasons=["date_filtered_evidence_missing_or_mismatched"],
            )
```

Add helper:

```python
def _docs_match_temporal_target(docs: list[KnowledgeDoc], *, temporal_intent: TemporalIntent) -> bool:
    if temporal_intent.target_start is None:
        return True
    target = temporal_intent.target_start.isoformat()
    date_keys = ("menu_date", "operation_date", "valid_at", "effective_date", "date_span", "posted_date")
    for doc in docs:
        values = [doc.date, *(str(doc.metadata.get(key, "")) for key in date_keys)]
        if any(target in value for value in values if value):
            return True
    return False
```

- [ ] **Step 5: Run the evidence tests**

Run:

```powershell
uv run pytest tests/test_phase_a_harness_contract.py::test_harness_blocks_dining_evidence_for_wrong_target_date tests/test_phase_a_harness_contract.py::test_harness_trace_records_next_week_temporal_intent -q
```

Expected: both pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/nlp_term/chat/evidence_sufficiency.py src/nlp_term/chat/orchestrator.py tests/test_phase_a_harness_contract.py
git commit -m "feat: enforce temporal evidence checks"
```

## Task 5: User-Safe Temporal Prompt Context

**Files:**
- Modify: `src/nlp_term/chat/evidence_pack.py`
- Modify: `src/nlp_term/chat/prompts.py`
- Modify: `src/nlp_term/chat/orchestrator.py`
- Modify: `src/nlp_term/chat/answer_validation.py`
- Modify: `tests/test_phase_a_harness_contract.py`
- Test: `tests/test_task2_answer_validation.py`

- [ ] **Step 1: Add prompt and validator tests**

Append to `tests/test_phase_a_harness_contract.py`:

```python
def test_harness_prompt_contains_user_safe_temporal_context(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        "["
        "{"
        '"doc_id":"dining_doc",'
        '"label":3,'
        '"domain":"dining",'
        '"title":"식단",'
        '"body":"2026-06-16 2학생회관 점심 메뉴는 공식 식단 페이지에서 확인한다.",'
        '"source_url":"https://mobileadmin.cnu.ac.kr/food/index.jsp",'
        '"source_id":"cnu_mobile_food",'
        '"metadata":{"menu_date":"2026-06-16","location":"2학생회관","raw_fetched_at":"2026-06-08T00:00:00+09:00"}'
        "}"
        "]",
        encoding="utf-8",
    )
    captured: dict[str, str] = {}

    def writer(prompt: str) -> str:
        captured["prompt"] = prompt
        return "다음주 화요일인 2026년 6월 16일 기준으로 2학생회관 식단은 공식 식단 페이지에서 확인하면 됩니다."

    result = answer_with_harness(
        "다음주 화요일 2학생회관 메뉴가 어떻게 되나요?",
        knowledge_path=knowledge_path,
        generator=writer,
        question_time=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )

    assert result.output_status == OutputStatus.ANSWERED
    assert "2026년 6월 16일" in captured["prompt"]
    assert "TemporalIntent" not in captured["prompt"]
    assert "confidence" not in captured["prompt"]
```

Append to `tests/test_task2_answer_validation.py`:

```python
def test_answer_validation_rejects_internal_temporal_trace_leak() -> None:
    result = validate_task2_answer("TemporalIntent confidence high 이므로 2026년 6월 16일로 답합니다.")

    assert result.passed is False
    assert "internal_trace_leak" in result.failures
```

- [ ] **Step 2: Run failing prompt tests**

Run:

```powershell
uv run pytest tests/test_phase_a_harness_contract.py::test_harness_prompt_contains_user_safe_temporal_context tests/test_task2_answer_validation.py::test_answer_validation_rejects_internal_temporal_trace_leak -q
```

Expected: fail because prompt has no temporal context and validator does not reject trace terms.

- [ ] **Step 3: Add temporal context to EvidencePack**

In `src/nlp_term/chat/evidence_pack.py`, add field:

```python
    temporal_context: str | None = None
```

In `to_prompt_text`, after domain lines, add:

```python
        if self.temporal_context:
            lines.extend(["시간 기준:", self.temporal_context])
```

Update `build_evidence_pack` signature:

```python
    temporal_context: str | None = None,
```

Pass the value into `EvidencePack(...)`.

- [ ] **Step 4: Render temporal context in orchestrator**

In `src/nlp_term/chat/orchestrator.py`, add helper:

```python
def _render_temporal_context(temporal_intent) -> str | None:
    if temporal_intent.temporal_type == "none":
        return None
    lines = [f"- 현재 기준일: {temporal_intent.reference_time.date().isoformat()}"]
    if temporal_intent.original_expression:
        lines.append(f"- 질문의 시간 표현: {temporal_intent.original_expression}")
    if temporal_intent.target_start and temporal_intent.target_end:
        if temporal_intent.target_start == temporal_intent.target_end:
            lines.append(f"- 해석된 날짜: {temporal_intent.target_start.isoformat()}")
        else:
            lines.append(f"- 해석된 기간: {temporal_intent.target_start.isoformat()} ~ {temporal_intent.target_end.isoformat()}")
    lines.append("- 해석된 날짜 또는 기간과 맞지 않는 근거로는 날짜, 메뉴, 운행 여부를 단정하지 않는다.")
    return "\n".join(lines)
```

When calling `build_evidence_pack`, pass:

```python
        temporal_context=_render_temporal_context(temporal_intent),
```

- [ ] **Step 5: Reject internal temporal trace leaks**

In `src/nlp_term/chat/answer_validation.py`, add:

```python
INTERNAL_TRACE_RE = re.compile(r"(TemporalIntent|temporal_type|confidence|retrieval_requirement|evidence_status)", re.IGNORECASE)
```

Inside `validate_task2_answer`, after the existing internal checks:

```python
    if INTERNAL_TRACE_RE.search(stripped):
        failures.append("internal_trace_leak")
```

- [ ] **Step 6: Run prompt and validation tests**

Run:

```powershell
uv run pytest tests/test_phase_a_harness_contract.py::test_harness_prompt_contains_user_safe_temporal_context tests/test_task2_answer_validation.py::test_answer_validation_rejects_internal_temporal_trace_leak -q
```

Expected: pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src/nlp_term/chat/evidence_pack.py src/nlp_term/chat/prompts.py src/nlp_term/chat/orchestrator.py src/nlp_term/chat/answer_validation.py tests/test_phase_a_harness_contract.py tests/test_task2_answer_validation.py
git commit -m "feat: add user-safe temporal prompt context"
```

## Task 6: Public Probe Evaluation Fixture

**Files:**
- Create: `data/gold/task2_public_probe_eval.json`
- Create: `tests/test_task2_public_probe_contract.py`

- [ ] **Step 1: Add fixture contract test**

Create `tests/test_task2_public_probe_contract.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


PROBE_PATH = Path("data/gold/task2_public_probe_eval.json")


def test_task2_public_probe_fixture_has_14_discussion_questions() -> None:
    rows = json.loads(PROBE_PATH.read_text(encoding="utf-8"))

    assert len(rows) == 14
    assert {row["id"] for row in rows} == {f"public_probe_{index:02d}" for index in range(1, 15)}
    assert all("question" in row for row in rows)
    assert all("expected_label" in row for row in rows)
    assert all("expected_temporal_type" in row for row in rows)
    assert all("expected_behavior" in row for row in rows)


def test_task2_public_probe_temporal_expectations_cover_current_failures() -> None:
    rows = json.loads(PROBE_PATH.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in rows}

    assert by_id["public_probe_07"]["expected_temporal_type"] == "changed_since"
    assert by_id["public_probe_08"]["expected_temporal_type"] == "period_summary"
    assert by_id["public_probe_11"]["expected_temporal_type"] == "date_lookup"
    assert by_id["public_probe_13"]["expected_temporal_type"] == "future_schedule"
```

- [ ] **Step 2: Run failing fixture test**

Run:

```powershell
uv run pytest tests/test_task2_public_probe_contract.py -q
```

Expected: fail because the fixture does not exist.

- [ ] **Step 3: Create the 14-question public probe fixture**

Create `data/gold/task2_public_probe_eval.json`:

```json
[
  {"id":"public_probe_01","question":"졸업까지 몇 학점 들어야 하나요?","expected_label":0,"expected_temporal_type":"none","expected_behavior":"Answer generally, mention department/admission-year differences, do not cite an unrelated department as if universal."},
  {"id":"public_probe_02","question":"이번 학기 수강신청은 언제 시작하나요?","expected_label":2,"expected_temporal_type":"date_lookup","expected_behavior":"Return the matching course registration start date if calendar evidence supports it."},
  {"id":"public_probe_03","question":"오늘 학식 뭐 나와요?","expected_label":3,"expected_temporal_type":"current_snapshot","expected_behavior":"Resolve today from runtime context and use only same-date dining evidence or controlled fetch."},
  {"id":"public_probe_04","question":"다음주에 셔틀버스는 정상 운행하나요?","expected_label":4,"expected_temporal_type":"ongoing_status","expected_behavior":"Resolve next ISO week and avoid normal-operation claims without timetable or effective-date evidence."},
  {"id":"public_probe_05","question":"이번에 올라온 공지사항 어디서 볼 수 있어요?","expected_label":1,"expected_temporal_type":"latest_item","expected_behavior":"Provide official notice board location or latest item source when available."},
  {"id":"public_probe_06","question":"새로 업데이트된 셔틀버스 정류장이 있을까요?","expected_label":4,"expected_temporal_type":"changed_since","expected_behavior":"Use a declared recent-change window and report verified stop changes only."},
  {"id":"public_probe_07","question":"5월 이후로 변동된 학사일정이 있을까요?","expected_label":2,"expected_temporal_type":"changed_since","expected_behavior":"Search calendar or notice evidence since May and summarize verified changes."},
  {"id":"public_probe_08","question":"다음주 학식 뭐 나와요?","expected_label":3,"expected_temporal_type":"period_summary","expected_behavior":"Resolve next ISO week and summarize date-matched dining evidence, fetching if needed."},
  {"id":"public_probe_09","question":"가장 최근에 올라온 공지사항은 언제 게시되었나요?","expected_label":1,"expected_temporal_type":"latest_item","expected_behavior":"Use posted_date evidence and include the latest verified posted date."},
  {"id":"public_probe_10","question":"충남대학교 인공지능학과 24학번의 경우 프로젝트 수업을 몇 개 들어야 하나요?","expected_label":0,"expected_temporal_type":"none","expected_behavior":"Require department and admission-year matched curriculum evidence; do not answer from unrelated departments."},
  {"id":"public_probe_11","question":"이번 학기 종강일이 언제인가요?","expected_label":2,"expected_temporal_type":"date_lookup","expected_behavior":"Return the semester end date from academic calendar evidence."},
  {"id":"public_probe_12","question":"이번 여름 계절학기 종강일이 언제인 가요?","expected_label":2,"expected_temporal_type":"date_lookup","expected_behavior":"Return the summer session end date, not grade announcement date."},
  {"id":"public_probe_13","question":"다음주 화요일 2학생회관 메뉴가 어떻게 되나요?","expected_label":3,"expected_temporal_type":"future_schedule","expected_behavior":"Resolve next ISO week Tuesday and use same-date same-location dining evidence or fetch."},
  {"id":"public_probe_14","question":"토익 장학금을 받으려면 성적이 몇 점 이상이어야 하나요?","expected_label":1,"expected_temporal_type":"none","expected_behavior":"Answer only from scholarship evidence; do not reuse graduation TOEIC requirements."}
]
```

- [ ] **Step 4: Run fixture tests**

Run:

```powershell
uv run pytest tests/test_task2_public_probe_contract.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add data/gold/task2_public_probe_eval.json tests/test_task2_public_probe_contract.py
git commit -m "test: add task2 public probe fixture"
```

## Task 7: Documentation and Full Verification

**Files:**
- Modify: `docs/task2_task3_harness_architecture.md`

- [ ] **Step 1: Update architecture documentation**

Add a section to `docs/task2_task3_harness_architecture.md`:

```markdown
## Temporal Intent Policy

Task 2 and Task 3 questions are single-turn. The harness must therefore resolve time expressions, retrieve evidence, and produce the final answer in one pass. Qwen is used as an answer writer, not as the temporal planner.

Week expressions use ISO-style Monday-to-Sunday weeks. With runtime date `2026-06-08`, `다음주 화요일` resolves to `2026-06-16`, not the nearest future Tuesday.

The temporal parser emits `TemporalIntent` with:

- `temporal_type`: one of `none`, `date_lookup`, `current_snapshot`, `future_schedule`, `latest_item`, `changed_since`, `ongoing_status`, `period_summary`.
- `confidence`: `high`, `medium`, or `low`, plus trace reasons.
- `target_start` and `target_end`: normalized date or range when available.
- `freshness_required`: true for current/latest/future volatile information.
- `version_match_required`: true for graduation/curriculum questions that depend on department, admission year, or curriculum year.
- `retrieval_requirements`: a list, not a single enum, because a question can need both date-filtered evidence and structured source preference.

Low temporal confidence does not directly mean a defensive answer. It means the harness must apply an approved default policy, search more carefully, and only become cautious if evidence remains insufficient. Final answers must not expose `TemporalIntent`, confidence, retrieval requirements, or evidence-status names.
```

- [ ] **Step 2: Run focused tests**

Run:

```powershell
uv run pytest tests/test_temporal_intent.py tests/test_phase_a_harness_contract.py tests/test_task2_answer_validation.py tests/test_task2_public_probe_contract.py -q
```

Expected: pass.

- [ ] **Step 3: Run lint**

Run:

```powershell
uv run ruff check src tests
```

Expected: pass.

- [ ] **Step 4: Run full test suite**

Run:

```powershell
uv run pytest -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add docs/task2_task3_harness_architecture.md
git commit -m "docs: document temporal intent harness policy"
```

## Execution Notes

- Keep Qwen reasoning off by default. The harness trace is the private reasoning record.
- Do not expose `TemporalIntent`, `confidence`, `retrieval_requirement`, `evidence_status`, `근거`, or source numbers in final user answers.
- Do not make live web search a free-form agent decision. Controlled fetch must be selected by harness state and source registry.
- If a test reveals that the current keyword parser is too brittle, improve the parser by adding a new deterministic pattern and a confidence reason. Do not replace it with unconstrained LLM classification in this phase.

## Self-Review

- Spec coverage: The plan covers ISO week policy, temporal type selection, confidence, retrieval requirement lists, evidence-status separation, single-turn answer handling, prompt safety, and the 14-question probe fixture.
- Placeholder scan: No implementation step uses placeholder text or open-ended instructions.
- Type consistency: `TemporalIntent`, `TemporalType`, `TemporalConfidence`, and `RetrievalRequirement` are defined before later tasks use them. `retrieval_requirements` is consistently a list.
