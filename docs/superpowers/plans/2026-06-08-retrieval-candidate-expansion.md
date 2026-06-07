# Retrieval Candidate Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand retrieval candidates and trace pre/post domain filtering so Task 2 can diagnose whether failures come from ranking, label filtering, or evidence pack compression.

**Architecture:** Keep the current lexical ranker for this goal, but stop treating `top_k=6` and final pack size as the same decision. Retrieve a larger candidate pool, preserve pre-filter trace rows, then select route-domain evidence for sufficiency and pack building.

**Tech Stack:** Python 3.10.12, existing lexical ranker, Pydantic trace model, pytest, `uv`.

---

## File Structure

- Modify `src/nlp_term/chat/state_contract.py`: add pre-filter retrieval trace fields.
- Modify `src/nlp_term/chat/orchestrator.py`: retrieve a larger candidate pool and expose pre/post-filter docs.
- Modify `tests/test_phase_a_harness_contract.py`: assert pre-filter candidates are traced and route-domain filtering is visible.
- Modify `src/nlp_term/chat/public_probe_experiment.py`: include pre-filter candidate IDs in JSON rows.
- Modify `docs/task2_task3_harness_architecture.md`: document candidate vs pack separation.

## Task 1: Add Pre-filter Retrieval Trace Fields

**Files:**
- Modify: `src/nlp_term/chat/state_contract.py`
- Modify: `tests/test_phase_a_harness_contract.py`

- [ ] **Step 1: Add failing trace test**

Append to `tests/test_phase_a_harness_contract.py`:

```python
def test_harness_trace_records_prefilter_and_postfilter_retrieval(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        "["
        "{"
        '"doc_id":"notice_doc",'
        '"label":1,'
        '"domain":"notices",'
        '"title":"공지",'
        '"body":"토익 장학금 성적 기준은 공지사항에서 확인한다.",'
        '"source_url":"https://plus.cnu.ac.kr/notice",'
        '"source_id":"notices_main",'
        '"metadata":{"source_name":"공지사항"}'
        "},"
        "{"
        '"doc_id":"grad_doc",'
        '"label":0,'
        '"domain":"graduation",'
        '"title":"졸업요건",'
        '"body":"토익 졸업인증 기준은 학과별로 다르다.",'
        '"source_url":"https://biochemistry.cnu.ac.kr/biochemistry/info/requirements.do",'
        '"source_id":"graduation_biochemistry_requirements",'
        '"metadata":{"source_department":"생화학과"}'
        "}"
        "]",
        encoding="utf-8",
    )

    result = answer_with_harness(
        "토익 장학금을 받으려면 성적이 몇 점 이상이어야 하나요?",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "토익 장학금 성적 기준은 공지사항에서 확인해야 합니다.",
    )

    assert "notice_doc" in result.trace.prefilter_retrieved_doc_ids
    assert result.trace.retrieved_doc_ids
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
uv run pytest tests/test_phase_a_harness_contract.py::test_harness_trace_records_prefilter_and_postfilter_retrieval -q
```

Expected: fail because `prefilter_retrieved_doc_ids` does not exist.

- [ ] **Step 3: Add trace fields**

In `src/nlp_term/chat/state_contract.py`, add to `HarnessTrace`:

```python
    prefilter_retrieved_doc_ids: list[str] = Field(default_factory=list)
    prefilter_retrieved_labels: list[int] = Field(default_factory=list)
    prefilter_retrieved_scores: list[float] = Field(default_factory=list)
```

- [ ] **Step 4: Commit**

Run:

```powershell
git add src/nlp_term/chat/state_contract.py tests/test_phase_a_harness_contract.py
git commit -m "feat: add prefilter retrieval trace fields"
```

## Task 2: Retrieve Larger Candidate Pool

**Files:**
- Modify: `src/nlp_term/chat/orchestrator.py`
- Modify: `tests/test_phase_a_harness_contract.py`

- [ ] **Step 1: Add large-candidate behavior test**

Append:

```python
def test_harness_retrieves_more_than_six_candidates_before_filtering(tmp_path: Path) -> None:
    docs = []
    for index in range(10):
        docs.append(
            "{"
            f'"doc_id":"notice_doc_{index}",'
            '"label":1,'
            '"domain":"notices",'
            f'"title":"공지 {index}",'
            f'"body":"공지사항 장학금 토익 기준 안내 자료 {index}.",'
            '"source_url":"https://plus.cnu.ac.kr/notice",'
            '"source_id":"notices_main",'
            f'"metadata":{{"source_name":"공지 {index}"}}'
            "}"
        )
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text("[" + ",".join(docs) + "]", encoding="utf-8")

    result = answer_with_harness(
        "토익 장학금을 받으려면 성적이 몇 점 이상이어야 하나요?",
        knowledge_path=knowledge_path,
        generator=lambda prompt: "토익 장학금 기준은 공지사항에서 확인해야 합니다.",
    )

    assert len(result.trace.prefilter_retrieved_doc_ids) >= 10
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
uv run pytest tests/test_phase_a_harness_contract.py::test_harness_retrieves_more_than_six_candidates_before_filtering -q
```

Expected: fail because orchestrator currently calls `rank_docs(... top_k=6)`.

- [ ] **Step 3: Add retrieval pool helper**

In `src/nlp_term/chat/orchestrator.py`, add:

```python
def _retrieval_pool_size(temporal_intent) -> int:
    if temporal_intent.temporal_type in {"period_summary", "changed_since"}:
        return 30
    if temporal_intent.freshness_required or temporal_intent.temporal_type != "none":
        return 20
    return 15
```

Replace:

```python
    retrieved = rank_docs(question, knowledge.docs, top_k=6)
```

with:

```python
    retrieved = rank_docs(question, knowledge.docs, top_k=_retrieval_pool_size(temporal_intent))
```

Before `retrieved_pairs`, add:

```python
    prefilter_docs = [docs_by_id[row.doc_id] for row in retrieved if row.doc_id in docs_by_id]
    prefilter_scores = [row.score for row in retrieved if row.doc_id in docs_by_id]
```

Pass `prefilter_docs=prefilter_docs` and `prefilter_scores=prefilter_scores` to `_build_trace`.

Update `_build_trace` signature and trace fields:

```python
    prefilter_docs: list[KnowledgeDoc],
    prefilter_scores: list[float],
```

```python
        prefilter_retrieved_doc_ids=[doc.doc_id for doc in prefilter_docs],
        prefilter_retrieved_labels=[doc.label for doc in prefilter_docs],
        prefilter_retrieved_scores=prefilter_scores,
```

- [ ] **Step 4: Run retrieval trace tests**

Run:

```powershell
uv run pytest tests/test_phase_a_harness_contract.py::test_harness_trace_records_prefilter_and_postfilter_retrieval tests/test_phase_a_harness_contract.py::test_harness_retrieves_more_than_six_candidates_before_filtering -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/nlp_term/chat/orchestrator.py src/nlp_term/chat/state_contract.py tests/test_phase_a_harness_contract.py
git commit -m "feat: expand retrieval candidate pool"
```

## Task 3: Include Pre-filter Candidates in Public Probe Report

**Files:**
- Modify: `src/nlp_term/chat/public_probe_experiment.py`
- Modify: `docs/evidence/task2-public-probe-harness-2026-06-08.json`
- Modify: `docs/task2_public_probe_harness_diagnosis_2026_06_08.md`
- Modify: `docs/task2_task3_harness_architecture.md`

- [ ] **Step 1: Add report field test**

Modify `tests/test_public_probe_experiment.py` to assert:

```python
    assert "prefilter_retrieved_doc_ids" in by_id["public_probe_13"]
```

- [ ] **Step 2: Implement report field**

In `src/nlp_term/chat/public_probe_experiment.py`, add these row fields:

```python
                "prefilter_retrieved_doc_ids": trace.prefilter_retrieved_doc_ids,
                "prefilter_retrieved_labels": trace.prefilter_retrieved_labels,
                "prefilter_retrieved_scores": trace.prefilter_retrieved_scores,
```

- [ ] **Step 3: Document candidate policy**

Add to `docs/task2_task3_harness_architecture.md`:

```markdown
### Retrieval Candidate Policy

Retrieval candidate count and final evidence pack size are separate. The harness first retrieves 15 candidates for static questions, 20 for date/current questions, and 30 for period/change-summary questions. It records pre-filter candidates before applying route-domain filtering so classifier errors and retrieval errors can be separated in trace diagnostics.
```

- [ ] **Step 4: Re-run public probe diagnosis**

Run:

```powershell
uv run python -m nlp_term.chat.public_probe_experiment --probe data/gold/task2_public_probe_eval.json --knowledge data/knowledge_seed.json --output docs/evidence/task2-public-probe-harness-2026-06-08.json --markdown docs/task2_public_probe_harness_diagnosis_2026_06_08.md
```

Expected: report includes pre-filter candidates.

- [ ] **Step 5: Verify**

Run:

```powershell
uv run pytest tests/test_phase_a_harness_contract.py tests/test_public_probe_experiment.py -q
uv run ruff check src tests
uv run pytest -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/nlp_term/chat/public_probe_experiment.py docs/task2_task3_harness_architecture.md docs/evidence/task2-public-probe-harness-2026-06-08.json docs/task2_public_probe_harness_diagnosis_2026_06_08.md tests/test_public_probe_experiment.py
git commit -m "test: refresh public probe with retrieval candidate traces"
```

## Self-Review

- Spec coverage: Covers larger retrieval pools, pre/post filter trace, public probe reporting, and docs.
- Placeholder scan: No placeholder steps.
- Type consistency: `prefilter_*` trace fields are added before report code uses them.
