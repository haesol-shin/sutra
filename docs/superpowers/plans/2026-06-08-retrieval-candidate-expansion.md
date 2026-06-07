# Retrieval Candidate Trace Lite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add lightweight pre-filter/post-filter retrieval tracing so data expansion can diagnose whether new sources are missed by ranking, label filtering, or evidence packing.

**Architecture:** This is a measurement goal, not a retrieval optimization goal. Keep the current lexical ranker, current domain/label filter, current evidence sufficiency policy, and current answer generation behavior. Only retrieve a slightly larger diagnostic candidate pool, record candidate metadata in the harness trace, and surface that trace in the public probe artifact.

**Tech Stack:** Python 3.10.12, existing lexical ranker, Pydantic trace models, pytest, `uv`.

---

## Why This Goal Is Lite

The current bottleneck is more likely source coverage and structured data than retrieval algorithm quality:

- public probe answered count stayed `6/14`;
- fail-closed count stayed `8/14`;
- Task 1 label match stayed `13/14`;
- retrieval `top3_source_hit_rate` stayed `0.98`;
- atomic-aware chunking added metadata but did not directly improve public probe answers.

So this goal must not become BM25, embedding retrieval, parent chunk reconstruction, or reranking. It only makes later data expansion easier to debug.

## Non-Goals

- Do not switch to embedding retrieval.
- Do not introduce BM25 or LangChain.
- Do not change answer generation prompts.
- Do not change evidence sufficiency rules.
- Do not implement parent chunk or atomic anchor expansion.
- Do not claim Task 2 quality improvement from this goal alone.

## File Structure

- Modify `src/nlp_term/chat/state_contract.py`
  - Add a small Pydantic model for retrieval candidate trace rows.
  - Add pre-filter and post-filter candidate lists to `HarnessTrace`.
- Modify `src/nlp_term/chat/orchestrator.py`
  - Retrieve a slightly larger candidate pool for diagnostics.
  - Keep final evidence docs selected by the existing label/domain path.
  - Pass candidate trace rows to `_build_trace()`.
- Modify `tests/test_phase_a_harness_contract.py`
  - Add one focused test proving pre-filter candidates include off-route docs while post-filter candidates include only the selected route docs.
- Modify `src/nlp_term/chat/public_probe_experiment.py`
  - Include pre-filter/post-filter candidate IDs and compact candidate metadata in each JSON row.
- Modify `docs/task2_task3_harness_architecture.md`
  - Document that candidate tracing is diagnostic and must not be interpreted as a performance claim.
- Refresh:
  - `docs/evidence/task2-public-probe-harness-2026-06-08.json`
  - `docs/task2_public_probe_harness_diagnosis_2026_06_08.md`

## Task 1: Add Retrieval Candidate Trace Contract

**Files:**
- Modify: `src/nlp_term/chat/state_contract.py`
- Modify: `tests/test_phase_a_harness_contract.py`

- [ ] **Step 1: Add failing harness trace test**

Append this test to `tests/test_phase_a_harness_contract.py`:

```python
def test_harness_trace_records_prefilter_and_postfilter_retrieval_candidates(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        json.dumps(
            [
                {
                    "doc_id": "notice_doc",
                    "label": 1,
                    "domain": "notices",
                    "title": "공지",
                    "body": "토익 장학금 성적 기준은 공지사항에서 확인한다.",
                    "source_url": "https://plus.cnu.ac.kr/notice",
                    "source_id": "notices_main",
                    "metadata": {
                        "source_name": "공지사항",
                        "chunking_strategy": "recursive_prose",
                        "boundary_type": "prose_sentence",
                        "chunk_confidence": "medium",
                    },
                },
                {
                    "doc_id": "grad_doc",
                    "label": 0,
                    "domain": "graduation",
                    "title": "졸업요건",
                    "body": "토익 졸업인증 기준은 학과별로 다르다.",
                    "source_url": "https://biochemistry.cnu.ac.kr/biochemistry/info/requirements.do",
                    "source_id": "graduation_biochemistry_requirements",
                    "metadata": {
                        "source_department": "생화학과",
                        "chunking_strategy": "fallback_window",
                        "boundary_type": "fallback_window",
                        "chunk_confidence": "low",
                    },
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = answer_with_harness(
        "토익 장학금을 받으려면 성적이 몇 점 이상이어야 하나요?",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "토익 장학금 성적 기준은 공지사항에서 확인해야 합니다.",
    )

    prefilter_ids = [candidate.doc_id for candidate in result.trace.prefilter_retrieved_candidates]
    postfilter_ids = [candidate.doc_id for candidate in result.trace.postfilter_retrieved_candidates]

    assert "notice_doc" in prefilter_ids
    assert "grad_doc" in prefilter_ids
    assert postfilter_ids == result.trace.retrieved_doc_ids
    assert "grad_doc" not in postfilter_ids
    assert result.trace.prefilter_retrieved_candidates[0].score >= 0
    assert {candidate.chunk_confidence for candidate in result.trace.prefilter_retrieved_candidates} >= {"medium", "low"}
```

- [ ] **Step 2: Run the failing test**

```powershell
uv run pytest tests/test_phase_a_harness_contract.py::test_harness_trace_records_prefilter_and_postfilter_retrieval_candidates -q
```

Expected: fail with `AttributeError` or Pydantic model error because `prefilter_retrieved_candidates` does not exist yet.

- [ ] **Step 3: Add trace model fields**

In `src/nlp_term/chat/state_contract.py`, add this model before `HarnessTrace`:

```python
class RetrievalCandidateTrace(BaseModel):
    doc_id: str
    score: float
    label: int = Field(ge=0, le=4)
    domain: Domain
    source_id: str
    chunking_strategy: str | None = None
    boundary_type: str | None = None
    chunk_confidence: str | None = None
```

Then add these fields to `HarnessTrace`:

```python
    prefilter_retrieved_candidates: list[RetrievalCandidateTrace] = Field(default_factory=list)
    postfilter_retrieved_candidates: list[RetrievalCandidateTrace] = Field(default_factory=list)
```

- [ ] **Step 4: Run the test again**

```powershell
uv run pytest tests/test_phase_a_harness_contract.py::test_harness_trace_records_prefilter_and_postfilter_retrieval_candidates -q
```

Expected: still fail because orchestrator does not populate the new fields.

- [ ] **Step 5: Commit the failing contract and schema**

```powershell
git add src/nlp_term/chat/state_contract.py tests/test_phase_a_harness_contract.py
git commit -m "test: define retrieval candidate trace contract"
```

## Task 2: Populate Candidate Trace Without Changing Retrieval Behavior

**Files:**
- Modify: `src/nlp_term/chat/orchestrator.py`
- Test: `tests/test_phase_a_harness_contract.py`

- [ ] **Step 1: Import the trace model**

In `src/nlp_term/chat/orchestrator.py`, update the state contract import:

```python
from nlp_term.chat.state_contract import (
    AnswerKind,
    AnswerValidationStatus,
    EvidenceLookupStatus,
    EvidenceSufficiencyStatus,
    GenerationStatus,
    HarnessResult,
    HarnessTrace,
    OutputStatus,
    PackStatus,
    RetrievalCandidateTrace,
    SourceStatus,
)
```

- [ ] **Step 2: Retrieve a diagnostic candidate pool**

Replace:

```python
    retrieved = rank_docs(question, knowledge.docs, top_k=max(6, evidence_pack_size))
```

with:

```python
    diagnostic_top_k = max(12, evidence_pack_size * 3)
    retrieved = rank_docs(question, knowledge.docs, top_k=diagnostic_top_k)
```

This does not change final evidence pack size. It only lets the trace show what ranking saw before the route-label filter.

- [ ] **Step 3: Build pre-filter and post-filter trace rows**

Add this helper near `_candidate_specs()`:

```python
def _candidate_trace_rows(rows, docs_by_id: dict[str, KnowledgeDoc]) -> list[RetrievalCandidateTrace]:
    trace_rows: list[RetrievalCandidateTrace] = []
    for row in rows:
        doc = docs_by_id.get(row.doc_id)
        if doc is None:
            continue
        trace_rows.append(
            RetrievalCandidateTrace(
                doc_id=doc.doc_id,
                score=row.score,
                label=doc.label,
                domain=doc.domain,
                source_id=doc.source_id,
                chunking_strategy=_optional_metadata_text(doc, "chunking_strategy"),
                boundary_type=_optional_metadata_text(doc, "boundary_type"),
                chunk_confidence=_optional_metadata_text(doc, "chunk_confidence"),
            )
        )
    return trace_rows


def _optional_metadata_text(doc: KnowledgeDoc, key: str) -> str | None:
    value = doc.metadata.get(key)
    return str(value) if value is not None else None
```

After `docs_by_id = {doc.doc_id: doc for doc in knowledge.docs}`, add:

```python
    prefilter_candidates = _candidate_trace_rows(retrieved, docs_by_id)
```

After `retrieved_pairs = ...`, add:

```python
    postfilter_candidates = [
        RetrievalCandidateTrace(
            doc_id=doc.doc_id,
            score=score,
            label=doc.label,
            domain=doc.domain,
            source_id=doc.source_id,
            chunking_strategy=_optional_metadata_text(doc, "chunking_strategy"),
            boundary_type=_optional_metadata_text(doc, "boundary_type"),
            chunk_confidence=_optional_metadata_text(doc, "chunk_confidence"),
        )
        for doc, score in retrieved_pairs
    ]
```

- [ ] **Step 4: Extend `_build_trace()` signature**

Add parameters:

```python
    prefilter_candidates: list[RetrievalCandidateTrace],
    postfilter_candidates: list[RetrievalCandidateTrace],
```

Add fields inside the returned `HarnessTrace`:

```python
        prefilter_retrieved_candidates=prefilter_candidates,
        postfilter_retrieved_candidates=postfilter_candidates,
```

Update every `_build_trace(...)` call in `answer_with_harness()` to pass:

```python
            prefilter_candidates=prefilter_candidates,
            postfilter_candidates=postfilter_candidates,
```

- [ ] **Step 5: Run the focused test**

```powershell
uv run pytest tests/test_phase_a_harness_contract.py::test_harness_trace_records_prefilter_and_postfilter_retrieval_candidates -q
```

Expected: pass.

- [ ] **Step 6: Run harness contract tests**

```powershell
uv run pytest tests/test_phase_a_harness_contract.py -q
```

Expected: pass.

- [ ] **Step 7: Commit implementation**

```powershell
git add src/nlp_term/chat/orchestrator.py tests/test_phase_a_harness_contract.py
git commit -m "feat: trace retrieval candidates before filtering"
```

## Task 3: Surface Candidate Trace In Public Probe Artifact

**Files:**
- Modify: `src/nlp_term/chat/public_probe_experiment.py`
- Test: `tests/test_public_probe_experiment.py`

- [ ] **Step 1: Add failing public probe trace assertion**

In `tests/test_public_probe_experiment.py`, add assertions to the existing public probe test after `row = ...` or equivalent row lookup:

```python
    assert "prefilter_retrieved_doc_ids" in row
    assert "postfilter_retrieved_doc_ids" in row
    assert "prefilter_retrieved_candidates" in row
    assert isinstance(row["prefilter_retrieved_candidates"], list)
```

If the test currently uses two rows, assert this on the row for a question with at least one retrieved doc.

- [ ] **Step 2: Run failing test**

```powershell
uv run pytest tests/test_public_probe_experiment.py -q
```

Expected: fail because the row fields are missing.

- [ ] **Step 3: Add compact serializer**

In `src/nlp_term/chat/public_probe_experiment.py`, add:

```python
def _candidate_rows(candidates) -> list[dict[str, object]]:
    return [
        {
            "doc_id": candidate.doc_id,
            "score": candidate.score,
            "label": candidate.label,
            "domain": candidate.domain,
            "source_id": candidate.source_id,
            "chunking_strategy": candidate.chunking_strategy,
            "boundary_type": candidate.boundary_type,
            "chunk_confidence": candidate.chunk_confidence,
        }
        for candidate in candidates
    ]
```

- [ ] **Step 4: Add fields to each report row**

In the `rows.append({...})` payload, add:

```python
                "prefilter_retrieved_doc_ids": [candidate.doc_id for candidate in trace.prefilter_retrieved_candidates],
                "postfilter_retrieved_doc_ids": [candidate.doc_id for candidate in trace.postfilter_retrieved_candidates],
                "prefilter_retrieved_candidates": _candidate_rows(trace.prefilter_retrieved_candidates),
                "postfilter_retrieved_candidates": _candidate_rows(trace.postfilter_retrieved_candidates),
```

Do not remove the existing `retrieved_doc_ids` and `retrieved_scores` fields. They remain the historical post-filter compact fields.

- [ ] **Step 5: Run public probe tests**

```powershell
uv run pytest tests/test_public_probe_experiment.py -q
```

Expected: pass.

- [ ] **Step 6: Commit artifact support**

```powershell
git add src/nlp_term/chat/public_probe_experiment.py tests/test_public_probe_experiment.py
git commit -m "feat: include retrieval candidate trace in public probe"
```

## Task 4: Refresh Public Probe And Verify Non-Regression

**Files:**
- Modify: `docs/evidence/task2-public-probe-harness-2026-06-08.json`
- Modify: `docs/task2_public_probe_harness_diagnosis_2026_06_08.md`

- [ ] **Step 1: Capture current public probe summary**

Run:

```powershell
$before = Get-Content docs\evidence\task2-public-probe-harness-2026-06-08.json | ConvertFrom-Json
[pscustomobject]@{
  answered=$before.answered_count
  fail_closed=$before.fail_close_count
  label_match=$before.label_match_count
  temporal_match=$before.temporal_match_count
} | Format-List
```

Expected current baseline:

```text
answered: 6
fail_closed: 8
label_match: 13
```

- [ ] **Step 2: Regenerate public probe artifact**

```powershell
uv run python -m nlp_term.chat.public_probe_experiment --probe data/gold/task2_public_probe_eval.json --knowledge data/knowledge_seed.json --output docs/evidence/task2-public-probe-harness-2026-06-08.json --markdown docs/task2_public_probe_harness_diagnosis_2026_06_08.md
```

Expected: command writes both files.

- [ ] **Step 3: Check non-regression**

Run:

```powershell
$after = Get-Content docs\evidence\task2-public-probe-harness-2026-06-08.json | ConvertFrom-Json
$rows = @($after.rows)
$missing = @($rows | Where-Object {-not $_.prefilter_retrieved_doc_ids -or -not $_.postfilter_retrieved_doc_ids})
[pscustomobject]@{
  answered=$after.answered_count
  fail_closed=$after.fail_close_count
  label_match=$after.label_match_count
  temporal_match=$after.temporal_match_count
  missing_candidate_trace=$missing.Count
} | Format-List
```

Required gates:

- answered count must not decrease below `6`;
- fail-closed count must not increase above `8`;
- label match count must not decrease below `13`;
- every public probe row must include pre-filter and post-filter candidate trace fields.

If a gate fails, do not continue. Record the failure in `docs/data_expansion_failure_log.md`, then fix the trace implementation before continuing.

- [ ] **Step 4: Run focused tests**

```powershell
uv run pytest tests/test_phase_a_harness_contract.py tests/test_public_probe_experiment.py -q
```

Expected: pass.

- [ ] **Step 5: Commit refreshed artifacts**

```powershell
git add docs/evidence/task2-public-probe-harness-2026-06-08.json docs/task2_public_probe_harness_diagnosis_2026_06_08.md
git commit -m "test: refresh public probe with retrieval candidate traces"
```

## Task 5: Document Diagnostic Scope

**Files:**
- Modify: `docs/task2_task3_harness_architecture.md`
- Modify: `docs/task2_improvement_sequence_after_probe.md`

- [ ] **Step 1: Document candidate vs pack separation**

Add this section to `docs/task2_task3_harness_architecture.md` near the evidence pack policy:

```markdown
## Retrieval Candidate Trace Policy

Retrieval candidate tracing is diagnostic only. The harness records pre-filter candidates before route-label filtering and post-filter candidates after the current label/domain selection path.

This does not mean every pre-filter candidate is eligible evidence. The answer writer still receives only the final evidence pack, and evidence sufficiency rules remain unchanged.

Each candidate trace should include `doc_id`, `score`, `label`, `domain`, `source_id`, `chunking_strategy`, `boundary_type`, and `chunk_confidence` when available. During data expansion, this trace is used to tell whether a new source was missed by ranking, filtered by route/domain, or selected but later blocked by sufficiency checks.
```

- [ ] **Step 2: Reword Goal 4 in the improvement sequence**

In `docs/task2_improvement_sequence_after_probe.md`, keep Goal 4 in the sequence but describe it as lite diagnostics:

```markdown
4. Retrieval candidate trace-lite
   - 계획: [`docs/superpowers/plans/2026-06-08-retrieval-candidate-expansion.md`](superpowers/plans/2026-06-08-retrieval-candidate-expansion.md)
   - 목적: retrieval 알고리즘을 바꾸지 않고, pre-filter/post-filter 후보와 `chunk_confidence`를 trace에 남겨 데이터 확장 실패 원인을 분리한다.
```

- [ ] **Step 3: Commit docs**

```powershell
git add docs/task2_task3_harness_architecture.md docs/task2_improvement_sequence_after_probe.md docs/superpowers/plans/2026-06-08-retrieval-candidate-expansion.md
git commit -m "docs: scope retrieval candidate work as trace lite"
```

## Task 6: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run full tests**

```powershell
uv run pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Inspect git status**

```powershell
git status --short
```

Expected: only unrelated pre-existing dirty files remain, if any.

- [ ] **Step 3: Final reviewer check**

Ask critic to review:

- trace fields are diagnostic only;
- public probe metrics did not regress;
- no retrieval optimization or prompt behavior was introduced accidentally;
- candidate trace includes `chunk_confidence` for future data expansion debugging.

## Self-Review

- Spec coverage: The plan implements Goal 4-lite, not full retrieval optimization. It records pre-filter/post-filter candidates and candidate metadata before data expansion.
- Placeholder scan: No `TBD`, `TODO`, or vague implementation steps remain.
- Type consistency: `RetrievalCandidateTrace`, `prefilter_retrieved_candidates`, and `postfilter_retrieved_candidates` are defined before use in orchestrator and public probe rows.
- Risk control: Existing answer behavior and evidence sufficiency are preserved. Public probe non-regression is a hard gate.

