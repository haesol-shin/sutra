# Evidence Pack Context Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve Task 2 evidence packs so Qwen receives enough grounded context instead of only the first sentence from three tiny chunks.

**Architecture:** Keep `EvidencePack` as the prompt boundary, but change item facts from first-sentence extraction to bounded chunk context. Add configurable `max_items` and `max_fact_chars`, and wire the orchestrator to pass a larger pack for temporal/current questions without flooding the prompt.

**Tech Stack:** Python 3.10.12, Pydantic, pytest, `uv`.

---

## File Structure

- Modify `src/nlp_term/chat/evidence_pack.py`: replace first-sentence `_clean_fact` behavior with bounded context extraction.
- Modify `src/nlp_term/chat/orchestrator.py`: choose `max_items` based on temporal/retrieval needs.
- Modify `tests/test_phase_a_harness_contract.py`: assert pack prompt preserves important later facts.
- Create or modify `tests/test_evidence_pack.py`: unit-test context clipping and item counts.
- Modify `docs/task2_task3_harness_architecture.md`: document evidence pack policy.

## Task 1: Bounded Context Instead of First Sentence

**Files:**
- Modify: `src/nlp_term/chat/evidence_pack.py`
- Create: `tests/test_evidence_pack.py`

- [ ] **Step 1: Write failing evidence pack tests**

Create `tests/test_evidence_pack.py`:

```python
from __future__ import annotations

from nlp_term.chat.evidence_pack import build_evidence_pack
from nlp_term.schemas import KnowledgeDoc


def _doc(body: str, *, doc_id: str = "doc_1") -> KnowledgeDoc:
    return KnowledgeDoc(
        doc_id=doc_id,
        label=2,
        domain="academic_calendar",
        title="학사일정",
        body=body,
        source_url="https://plus.cnu.ac.kr/calendar",
        source_id="academic_calendar",
        metadata={"source_name": "충남대학교 학사일정"},
    )


def test_evidence_pack_keeps_later_relevant_context_in_chunk() -> None:
    pack = build_evidence_pack(
        question="이번 학기 종강일이 언제인가요?",
        label=2,
        domain="academic_calendar",
        docs=[
            _doc(
                "학사일정 안내입니다. 수강신청은 2026년 2월에 진행됩니다. "
                "1학기 종강일은 2026년 6월 19일입니다."
            )
        ],
    )

    text = pack.to_prompt_text()

    assert "1학기 종강일은 2026년 6월 19일입니다" in text
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
uv run pytest tests/test_evidence_pack.py::test_evidence_pack_keeps_later_relevant_context_in_chunk -q
```

Expected: fail because `_clean_fact` only keeps the first sentence.

- [ ] **Step 3: Replace first-sentence extraction with bounded context**

In `src/nlp_term/chat/evidence_pack.py`, change `build_evidence_pack` signature:

```python
def build_evidence_pack(
    *,
    question: str,
    label: int,
    domain: Domain,
    docs: list[KnowledgeDoc],
    max_items: int = 3,
    max_fact_chars: int = 500,
    temporal_context: str | None = None,
) -> EvidencePack:
```

Change item facts:

```python
            facts=[_clean_fact(doc.body, max_chars=max_fact_chars)],
```

Replace `_clean_fact`:

```python
def _clean_fact(body: str, *, max_chars: int = 500) -> str:
    normalized = " ".join(body.replace("\r", " ").replace("\n", " ").split())
    if len(normalized) <= max_chars:
        return normalized
    clipped = normalized[:max_chars].rstrip()
    return clipped + "..."
```

- [ ] **Step 4: Run evidence pack test**

Run:

```powershell
uv run pytest tests/test_evidence_pack.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/nlp_term/chat/evidence_pack.py tests/test_evidence_pack.py
git commit -m "feat: preserve bounded evidence chunk context"
```

## Task 2: Configurable Evidence Pack Size

**Files:**
- Modify: `src/nlp_term/chat/orchestrator.py`
- Modify: `tests/test_phase_a_harness_contract.py`

- [ ] **Step 1: Add prompt item count test**

Append to `tests/test_phase_a_harness_contract.py`:

```python
def test_temporal_questions_can_send_more_than_three_evidence_items(tmp_path: Path) -> None:
    docs = []
    for index in range(5):
        docs.append(
            "{"
            f'"doc_id":"calendar_doc_{index}",'
            '"label":2,'
            '"domain":"academic_calendar",'
            f'"title":"학사일정 {index}",'
            f'"body":"이번 학기 학사일정 참고 자료 {index}. 2026년 6월 19일 종강일 관련 자료입니다.",'
            '"source_url":"https://plus.cnu.ac.kr/calendar",'
            '"source_id":"academic_calendar",'
            f'"metadata":{{"date_span":"2026-06-19","source_name":"학사일정 {index}"}}'
            "}"
        )
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text("[" + ",".join(docs) + "]", encoding="utf-8")
    captured: dict[str, str] = {}

    def writer(prompt: str) -> str:
        captured["prompt"] = prompt
        return "이번 학기 종강일은 2026년 6월 19일입니다."

    answer_with_harness(
        "이번 학기 종강일이 언제인가요?",
        knowledge_path=knowledge_path,
        generator=writer,
        question_time=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )

    assert captured["prompt"].count("핵심 사실:") >= 5
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
uv run pytest tests/test_phase_a_harness_contract.py::test_temporal_questions_can_send_more_than_three_evidence_items -q
```

Expected: fail because orchestrator currently builds a 3-item pack.

- [ ] **Step 3: Add pack size helper in orchestrator**

In `src/nlp_term/chat/orchestrator.py`, add:

```python
def _evidence_pack_size(temporal_intent) -> int:
    if temporal_intent.temporal_type in {"period_summary", "changed_since"}:
        return 8
    if temporal_intent.freshness_required or temporal_intent.temporal_type != "none":
        return 5
    return 3
```

Change `build_evidence_pack` call:

```python
        max_items=_evidence_pack_size(temporal_intent),
        max_fact_chars=500,
```

- [ ] **Step 4: Run test**

Run:

```powershell
uv run pytest tests/test_phase_a_harness_contract.py::test_temporal_questions_can_send_more_than_three_evidence_items -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/nlp_term/chat/orchestrator.py tests/test_phase_a_harness_contract.py
git commit -m "feat: adapt evidence pack size by temporal need"
```

## Task 3: Refresh Diagnosis

**Files:**
- Modify: `docs/evidence/task2-public-probe-harness-2026-06-08.json`
- Modify: `docs/task2_public_probe_harness_diagnosis_2026_06_08.md`
- Modify: `docs/task2_task3_harness_architecture.md`

- [ ] **Step 1: Document evidence pack policy**

Add to `docs/task2_task3_harness_architecture.md`:

```markdown
### Evidence Pack Context Policy

Evidence packs should not reduce every chunk to the first sentence. The pack keeps bounded chunk context so date, credit, location, and condition facts that appear later in a small chunk are still visible to Qwen. Default pack sizes are 3 items for static questions, 5 items for date/current questions, and 8 items for period or change-summary questions.
```

- [ ] **Step 2: Re-run public probe diagnosis**

Run:

```powershell
uv run python -m nlp_term.chat.public_probe_experiment --probe data/gold/task2_public_probe_eval.json --knowledge data/knowledge_seed.json --output docs/evidence/task2-public-probe-harness-2026-06-08.json --markdown docs/task2_public_probe_harness_diagnosis_2026_06_08.md
```

Expected: evidence pack changes should reduce writer failures after Goal 1, and may improve date/calendar answers when relevant facts were clipped.

- [ ] **Step 3: Verify tests**

Run:

```powershell
uv run pytest tests/test_evidence_pack.py tests/test_phase_a_harness_contract.py tests/test_public_probe_experiment.py -q
uv run ruff check src tests
uv run pytest -q
```

Expected: all pass.

- [ ] **Step 4: Commit**

Run:

```powershell
git add docs/task2_task3_harness_architecture.md docs/evidence/task2-public-probe-harness-2026-06-08.json docs/task2_public_probe_harness_diagnosis_2026_06_08.md
git commit -m "docs: record evidence pack context policy"
```

## Self-Review

- Spec coverage: Covers first-sentence information loss, pack size, diagnosis refresh, and documentation.
- Placeholder scan: No placeholder steps.
- Type consistency: `max_fact_chars` and `_evidence_pack_size` are introduced before use.
