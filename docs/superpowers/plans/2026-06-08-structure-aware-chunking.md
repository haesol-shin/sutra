# Structure-Aware Chunking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current mostly fixed-window source chunking path with a deterministic structure-aware chunker before running retrieval candidate expansion.

**Why now:** Retrieval and Qwen answer quality are distorted if source text is cut across headings, table rows, dates, credit requirements, or menu/timetable rows. Data expansion should not proceed on top of unstable chunk boundaries.

**Architecture:** Keep `prepare.from_sources` as the source-to-`KnowledgeDoc` entrypoint, but move chunk splitting into a small reusable chunking module. The default strategy should prefer structured boundaries and recursive text splitting, then fall back to fixed-size sliding windows only when structure cannot be detected.

**Tech Stack:** Python 3.10.12, standard library only, pytest, `uv`.

---

## File Structure

- Add or modify `src/nlp_term/prepare/chunking.py`: structure-aware chunk splitting helpers.
- Modify `src/nlp_term/prepare/from_sources.py`: use the new chunker and preserve chunking metadata.
- Modify `tests/test_prepare_from_sources.py` or create `tests/test_structure_aware_chunking.py`: prove headings, table-like rows, and recursive text boundaries survive.
- Modify `docs/task2_task3_harness_architecture.md`: record the chunking policy if implementation changes prompt-facing behavior.

## Task 1: Extract Chunking Module

**Files:**
- Add: `src/nlp_term/prepare/chunking.py`
- Modify: `src/nlp_term/prepare/from_sources.py`
- Test: `tests/test_structure_aware_chunking.py`

- [ ] **Step 1: Write failing tests for recursive and row-aware chunking**

Create tests that assert:

- paragraph/heading boundaries are preferred over arbitrary character cuts.
- table-like rows with dates or times are not split when under the max size.
- fallback sliding-window behavior still produces chunks when no structure exists.

Minimum examples:

```python
def test_chunker_preserves_heading_with_nearby_credit_requirement() -> None:
    text = "졸업요건\n전공 78학점 이상 이수해야 한다.\n교양은 42학점까지 인정한다."
    chunks = split_source_text(text, label=0, max_chunk_chars=120, max_chunks=3)
    assert any("졸업요건" in chunk.text and "전공 78학점" in chunk.text for chunk in chunks)


def test_chunker_preserves_calendar_rows() -> None:
    text = "03.03(화) 제1학기 개강일\n06.19(금) 제1학기 종강일\n06.22(월) 하기 계절학기 개강"
    chunks = split_source_text(text, label=2, max_chunk_chars=80, max_chunks=3)
    assert any("06.19(금) 제1학기 종강일" in chunk.text for chunk in chunks)
```

- [ ] **Step 2: Implement minimal chunk object**

Use a small dataclass:

```python
@dataclass(frozen=True)
class SourceChunk:
    text: str
    strategy: str
    index: int
    char_start: int | None = None
    char_end: int | None = None
```

- [ ] **Step 3: Implement structure-aware splitter**

Recommended order:

1. normalize whitespace while preserving line boundaries for row detection.
2. split into blocks by blank lines and headings.
3. detect row-like lines for calendar, dining, shuttle, and notices.
4. recursively split oversized blocks by Korean sentence endings, newline, then whitespace.
5. use fixed-window overlap only as fallback.
6. score/select chunks with the existing label keyword scoring rules or a compatible helper.

- [ ] **Step 4: Run focused chunking tests**

```powershell
uv run pytest tests/test_structure_aware_chunking.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/nlp_term/prepare/chunking.py src/nlp_term/prepare/from_sources.py tests/test_structure_aware_chunking.py
git commit -m "feat: add structure-aware source chunking"
```

## Task 2: Preserve Chunking Metadata In KnowledgeDocs

**Files:**
- Modify: `src/nlp_term/prepare/from_sources.py`
- Modify: relevant tests

- [ ] **Step 1: Add tests for chunk metadata**

Assert every parsed `KnowledgeDoc.metadata` includes:

- `chunking_strategy`
- `chunk_index`
- `char_start`
- `char_end`

When offsets are unavailable, `char_start` and `char_end` may be null, but the keys should exist.

- [ ] **Step 2: Wire metadata into `parse_source`**

When creating `KnowledgeDoc`, preserve the chunk strategy and offsets in metadata. Do not expose these internal fields in user-facing prompts.

- [ ] **Step 3: Verify source parsing smoke**

```powershell
uv run pytest tests/test_prepare_from_sources.py tests/test_structure_aware_chunking.py -q
```

- [ ] **Step 4: Commit**

```powershell
git add src/nlp_term/prepare/from_sources.py tests/test_prepare_from_sources.py tests/test_structure_aware_chunking.py
git commit -m "feat: record source chunking provenance"
```

## Task 3: Rebuild Seed Knowledge And Compare Retrieval

**Files:**
- Modify: `data/knowledge_seed.json`
- Modify: `data/source_parse_failures.json` if regenerated
- Modify: retrieval metrics artifact if the project currently tracks one

- [ ] **Step 1: Rebuild source-backed knowledge**

```powershell
uv run python -m nlp_term.prepare.from_sources --source-probe data/sources/source_probe.json --output data/knowledge_seed.json --failures-output data/source_parse_failures.json --chunks-per-source 9
```

- [ ] **Step 2: Run quality gates**

```powershell
uv run python -m nlp_term.validators --knowledge-quality data/knowledge_seed.json --source-probe data/sources/source_probe.json --min-total-docs 50 --min-docs-per-label 1 --min-body-chars 80 --min-source-parse-ratio 0.9
uv run python -m nlp_term.retrieve.evaluate --knowledge data/knowledge_seed.json --qa data/qa_seed.json --output model/retrieval_metrics.json
uv run python -m nlp_term.validators --retrieval-metrics model/retrieval_metrics.json --knowledge data/knowledge_seed.json --qa data/qa_seed.json --require-metadata-aware --min-top1-label-accuracy 0.80 --min-top3-source-hit-rate 0.75
```

- [ ] **Step 3: Public probe sanity check**

```powershell
uv run python -m nlp_term.chat.public_probe_experiment --probe data/gold/task2_public_probe_eval.json --knowledge data/knowledge_seed.json --output docs/evidence/task2-public-probe-harness-2026-06-08.json --markdown docs/task2_public_probe_harness_diagnosis_2026_06_08.md
```

Expected: answered count should not regress. If it regresses, inspect whether chunking removed relevant text or whether retrieval scoring changed.

- [ ] **Step 4: Full verification**

```powershell
uv run ruff check src tests
uv run pytest -q
```

- [ ] **Step 5: Commit**

```powershell
git add data/knowledge_seed.json data/source_parse_failures.json model/retrieval_metrics.json docs/evidence/task2-public-probe-harness-2026-06-08.json docs/task2_public_probe_harness_diagnosis_2026_06_08.md
git commit -m "test: refresh corpus after structure-aware chunking"
```

## Non-Goals

- Do not implement full source-specific parsers for every source family in this goal.
- Do not introduce LangChain as a dependency just for splitting.
- Do not switch to embedding retrieval in this goal.
- Do not claim Task 2 answer quality improvement unless public probe or retrieval metrics show it.

## Self-Review

- Spec coverage: Covers chunk boundary quality, provenance metadata, source rebuild, retrieval check, and public probe sanity.
- Risk: Regenerating `data/knowledge_seed.json` can touch many downstream artifacts; keep the final artifact commit separate.
- Success criterion: Structure-aware chunking passes tests and does not regress knowledge quality or retrieval gates.
