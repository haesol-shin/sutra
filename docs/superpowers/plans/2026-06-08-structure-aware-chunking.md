# Atomic-Aware Chunking Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conservative atomic-aware chunking smoke stage that protects only obvious source patterns before retrieval candidate expansion, without claiming full source-specific parser coverage.

**Architecture:** Keep recursive prose splitting as the general default. Add lightweight atomic guards only for clear, repeated patterns where splitting would obviously break meaning, such as calendar date rows, dining date/location/meal rows, shuttle time rows, notice title/date/body blocks, and graduation requirement lines with a nearby heading. Fixed-window fallback remains only as low-confidence source preservation when neither atomic guards nor recursive splitting can produce usable chunks.

**Tech Stack:** Python 3.10.12, standard library only, pytest, `uv`.

---

## Why This Is A Smoke Stage

The corpus is still small. We should not overfit a full parser strategy to a few seed sources. This goal therefore does **not** implement production domain-specific parsers.

The goal is narrower:

1. Protect source patterns that are already obvious in the current task scope.
2. Keep general prose handled by recursive splitting.
3. Preserve badly extracted text only with `fallback_window` metadata and low confidence.
4. Verify that retrieval/public-probe behavior does not regress.

Domain-specific parsers remain Phase 2 work in `docs/data_expansion_goal_plan.md`. This smoke stage is a bridge, not a replacement.

## Definitions

- `atomic_guard`: a lightweight rule that keeps a clearly connected text unit together.
- `recursive_prose`: sentence/paragraph-aware splitting for ordinary explanatory text.
- `fallback_window`: fixed-size preservation chunk used only when no better boundary is found.
- `chunk_confidence`: `high` for atomic guards, `medium` for recursive prose, `low` for fallback windows.

If a mixed document partially matches atomic guards but public-probe or retrieval non-regression fails because nearby prose disappeared, revise the implementation to merge atomic guard chunks with recursive prose chunks before continuing to retrieval candidate expansion.

## File Structure

- Add `src/nlp_term/prepare/chunking.py`
  - Owns `SourceChunk`, atomic guard extraction, recursive prose splitting, fallback windowing, and chunk metadata.
- Modify `src/nlp_term/prepare/from_sources.py`
  - Calls `split_source_text()` instead of local `_chunk_text()`.
  - Preserves chunk provenance metadata in every `KnowledgeDoc`.
- Add `tests/test_atomic_aware_chunking.py`
  - Smoke fixtures for only obvious atomic patterns.
  - Regression fixtures proving prose still uses recursive behavior.
  - Regression fixtures proving fallback chunks are marked low confidence.
- Modify `tests/test_prepare_from_sources.py`
  - Verifies parsed `KnowledgeDoc.metadata` includes chunking provenance.
- Modify `docs/task2_task3_harness_architecture.md`
  - Records that fallback chunks are lower-confidence evidence, not strong current-fact support.

## Task 1: Lock Conservative Smoke Tests

**Files:**
- Add: `tests/test_atomic_aware_chunking.py`

- [ ] **Step 1: Create failing tests**

Create `tests/test_atomic_aware_chunking.py`:

```python
from __future__ import annotations

from nlp_term.prepare.chunking import split_source_text


def _texts(chunks):
    return [chunk.text for chunk in chunks]


def test_calendar_guard_preserves_date_and_event_name() -> None:
    text = "03.03(화) 제1학기 개강일\n06.19(금) 제1학기 종강일\n06.22(월) 하기 계절학기 개강"

    chunks = split_source_text(text, label=2, max_chunk_chars=80, max_chunks=5)

    assert any("06.19(금) 제1학기 종강일" in chunk for chunk in _texts(chunks))
    assert any(chunk.boundary_type == "calendar_row" and chunk.chunk_confidence == "high" for chunk in chunks)


def test_dining_guard_preserves_obvious_date_location_meal_and_menu() -> None:
    text = (
        "2026-06-16 2학생회관 중식\n"
        "백반, 된장국, 제육볶음\n"
        "2026-06-16 3학생회관 석식\n"
        "김치찌개, 계란말이"
    )

    chunks = split_source_text(text, label=3, max_chunk_chars=120, max_chunks=5)

    assert any("2026-06-16" in chunk and "2학생회관" in chunk and "중식" in chunk and "제육볶음" in chunk for chunk in _texts(chunks))
    assert any(chunk.boundary_type == "dining_menu_row" and chunk.chunk_confidence == "high" for chunk in chunks)


def test_shuttle_guard_preserves_stop_and_departure_times() -> None:
    text = "교내순환 셔틀버스\n월평역: 08:20 09:30 10:30\n도서관: 08:35 09:45 10:45"

    chunks = split_source_text(text, label=4, max_chunk_chars=120, max_chunks=5)

    assert any("월평역" in chunk and "08:20" in chunk and "09:30" in chunk for chunk in _texts(chunks))
    assert any(chunk.boundary_type == "shuttle_time_row" and chunk.chunk_confidence == "high" for chunk in chunks)


def test_notice_guard_preserves_obvious_title_date_body_block() -> None:
    text = (
        "제목: 2026학년도 하기 계절학기 수강신청 안내\n"
        "작성일: 2026-05-01\n"
        "본문: 수강신청 기간은 2026년 5월 7일부터 5월 9일까지입니다."
    )

    chunks = split_source_text(text, label=1, max_chunk_chars=180, max_chunks=5)

    assert any("하기 계절학기 수강신청 안내" in chunk and "2026-05-01" in chunk for chunk in _texts(chunks))
    assert any(chunk.boundary_type == "notice_detail" and chunk.chunk_confidence == "high" for chunk in chunks)


def test_graduation_guard_preserves_heading_with_obvious_requirement_line() -> None:
    text = (
        "컴퓨터융합학부 졸업요건\n"
        "2024학번은 프로젝트 관련 전공 교과목 2개 이상을 이수해야 한다.\n"
        "총 졸업학점은 130학점 이상이다."
    )

    chunks = split_source_text(text, label=0, max_chunk_chars=160, max_chunks=5)

    assert any("컴퓨터융합학부 졸업요건" in chunk and "2024학번" in chunk and "2개 이상" in chunk for chunk in _texts(chunks))
    assert any(chunk.boundary_type == "graduation_requirement" and chunk.chunk_confidence == "high" for chunk in chunks)


def test_general_prose_uses_recursive_medium_confidence_chunks() -> None:
    text = "졸업요건은 학과와 입학연도에 따라 다릅니다. 본인의 교육과정 적용 연도를 확인해야 합니다."

    chunks = split_source_text(text, label=0, max_chunk_chars=80, max_chunks=5)

    assert chunks
    assert all(chunk.chunk_confidence == "medium" for chunk in chunks)
    assert all(chunk.strategy == "recursive_prose" for chunk in chunks)


def test_unstructured_text_falls_back_with_low_confidence() -> None:
    text = "2026학년도교육과정표전공필수전공선택교양핵심" * 20

    chunks = split_source_text(text, label=0, max_chunk_chars=100, max_chunks=3)

    assert chunks
    assert all(chunk.strategy == "fallback_window" for chunk in chunks)
    assert all(chunk.chunk_confidence == "low" for chunk in chunks)
```

- [ ] **Step 2: Run failing tests**

```powershell
uv run pytest tests/test_atomic_aware_chunking.py -q
```

Expected: fail because `nlp_term.prepare.chunking` does not exist yet.

- [ ] **Step 3: Commit tests after confirming expected failure**

```powershell
git add tests/test_atomic_aware_chunking.py
git commit -m "test: define atomic-aware chunking smoke contract"
```

## Task 2: Implement Minimal Atomic Guards And Recursive Fallback

**Files:**
- Add: `src/nlp_term/prepare/chunking.py`
- Test: `tests/test_atomic_aware_chunking.py`

- [ ] **Step 1: Add chunking dataclass and public function**

Create `src/nlp_term/prepare/chunking.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SourceChunk:
    text: str
    strategy: str
    index: int
    boundary_type: str
    chunk_confidence: str
    char_start: int | None = None
    char_end: int | None = None


def split_source_text(
    text: str,
    *,
    label: int,
    max_chunk_chars: int = 300,
    max_chunks: int = 9,
) -> list[SourceChunk]:
    guarded = _atomic_guard_chunks(text, label=label, max_chunk_chars=max_chunk_chars, max_chunks=max_chunks)
    if guarded:
        return guarded
    recursive = _recursive_prose_chunks(text, max_chunk_chars=max_chunk_chars, max_chunks=max_chunks)
    if recursive:
        return recursive
    return _fallback_window_chunks(text, max_chunk_chars=max_chunk_chars, max_chunks=max_chunks)
```

- [ ] **Step 2: Implement only obvious atomic guards**

Add:

```python
DATE_ROW_RE = re.compile(r"(?:20\d{2}[-.]\d{1,2}[-.]\d{1,2}|\d{2}\.\d{2})")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
DINING_HEADER_RE = re.compile(r"20\d{2}-\d{2}-\d{2}.*(?:학생회관|생활관|푸드코트).*(?:조식|중식|석식|점심|저녁|아침)")
NOTICE_FIELD_RE = re.compile(r"^(제목|작성일|게시일|본문)\s*[:：]")
GRAD_REQUIREMENT_RE = re.compile(r"(?:학번|졸업|전공|교양|학점|프로젝트|이수)")


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]


def _atomic_guard_chunks(text: str, *, label: int, max_chunk_chars: int, max_chunks: int) -> list[SourceChunk]:
    lines = _clean_lines(text)
    if label == 0:
        units = _graduation_guard_units(lines)
    elif label == 1:
        units = _notice_guard_units(lines)
    elif label == 2:
        units = [(line, "calendar_row") for line in lines if DATE_ROW_RE.search(line)]
    elif label == 3:
        units = _dining_guard_units(lines)
    elif label == 4:
        units = _shuttle_guard_units(lines)
    else:
        units = []
    return _materialize_units(units, strategy="atomic_guard", confidence="high", max_chunk_chars=max_chunk_chars, max_chunks=max_chunks)


def _graduation_guard_units(lines: list[str]) -> list[tuple[str, str]]:
    units: list[tuple[str, str]] = []
    current_heading = ""
    for line in lines:
        if len(line) <= 40 and any(term in line for term in ("졸업", "교육과정", "요건")):
            current_heading = line
            continue
        if GRAD_REQUIREMENT_RE.search(line):
            units.append((f"{current_heading} {line}".strip(), "graduation_requirement"))
    return units


def _notice_guard_units(lines: list[str]) -> list[tuple[str, str]]:
    fields = [line for line in lines if NOTICE_FIELD_RE.search(line)]
    if len(fields) >= 2:
        return [(" ".join(fields), "notice_detail")]
    return []


def _dining_guard_units(lines: list[str]) -> list[tuple[str, str]]:
    units: list[tuple[str, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if DINING_HEADER_RE.search(line):
            menu = lines[index + 1] if index + 1 < len(lines) else ""
            units.append((f"{line} {menu}".strip(), "dining_menu_row"))
            index += 2
            continue
        index += 1
    return units


def _shuttle_guard_units(lines: list[str]) -> list[tuple[str, str]]:
    heading = next((line for line in lines if "셔틀" in line or "버스" in line), "")
    units = []
    for line in lines:
        if TIME_RE.search(line):
            units.append((f"{heading} {line}".strip(), "shuttle_time_row"))
    return units
```

- [ ] **Step 3: Implement recursive prose and low-confidence fallback**

Add:

```python
def _recursive_prose_chunks(text: str, *, max_chunk_chars: int, max_chunks: int) -> list[SourceChunk]:
    normalized = " ".join(text.split())
    if not normalized or _looks_unstructured(normalized):
        return []
    parts = [part.strip() for part in re.split(r"(?<=[다요]\.)\s+", normalized) if part.strip()]
    if not parts:
        return []
    units = [(part, "prose_sentence") for part in _merge_parts(parts, max_chunk_chars=max_chunk_chars)]
    return _materialize_units(units, strategy="recursive_prose", confidence="medium", max_chunk_chars=max_chunk_chars, max_chunks=max_chunks)


def _looks_unstructured(text: str) -> bool:
    return bool(text) and " " not in text and "\n" not in text and len(text) > 80


def _merge_parts(parts: list[str], *, max_chunk_chars: int) -> list[str]:
    merged: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current} {part}".strip()
        if len(candidate) <= max_chunk_chars:
            current = candidate
            continue
        if current:
            merged.append(current)
        current = part
    if current:
        merged.append(current)
    return merged


def _materialize_units(
    units: list[tuple[str, str]],
    *,
    strategy: str,
    confidence: str,
    max_chunk_chars: int,
    max_chunks: int,
) -> list[SourceChunk]:
    chunks: list[SourceChunk] = []
    for text, boundary_type in units:
        normalized = " ".join(text.split())
        if not normalized:
            continue
        if len(normalized) > max_chunk_chars:
            chunks.extend(_fallback_window_chunks(normalized, max_chunk_chars=max_chunk_chars, max_chunks=max_chunks - len(chunks), boundary_type=boundary_type))
        else:
            chunks.append(
                SourceChunk(
                    text=normalized,
                    strategy=strategy,
                    index=len(chunks) + 1,
                    boundary_type=boundary_type,
                    chunk_confidence=confidence,
                )
            )
        if len(chunks) >= max_chunks:
            break
    return chunks[:max_chunks]


def _fallback_window_chunks(
    text: str,
    *,
    max_chunk_chars: int,
    max_chunks: int,
    boundary_type: str = "fallback_window",
) -> list[SourceChunk]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    step = max(max_chunk_chars // 2, 80)
    chunks: list[SourceChunk] = []
    for start in range(0, len(normalized), step):
        body = normalized[start : start + max_chunk_chars].strip()
        if len(body) < 20:
            continue
        chunks.append(
            SourceChunk(
                text=body,
                strategy="fallback_window",
                index=len(chunks) + 1,
                boundary_type=boundary_type,
                chunk_confidence="low",
                char_start=start,
                char_end=start + len(body),
            )
        )
        if len(chunks) >= max_chunks:
            break
    return chunks
```

- [ ] **Step 4: Run focused tests**

```powershell
uv run pytest tests/test_atomic_aware_chunking.py -q
```

Expected: pass.

- [ ] **Step 5: Commit implementation**

```powershell
git add src/nlp_term/prepare/chunking.py tests/test_atomic_aware_chunking.py
git commit -m "feat: add atomic-aware chunking smoke"
```

## Task 3: Wire Chunker Into Source Parsing Without Changing Parser Claims

**Files:**
- Modify: `src/nlp_term/prepare/from_sources.py`
- Modify: `tests/test_prepare_from_sources.py`

- [ ] **Step 1: Add provenance test**

Add a test that calls `parse_source()` with a `RawSource` containing a clear calendar row and asserts metadata:

```python
def test_parse_source_records_atomic_aware_chunking_provenance() -> None:
    raw = RawSource(
        source_id="academic_calendar",
        label=2,
        domain="academic_calendar",
        url="https://plus.cnu.ac.kr/calendar",
        title="학사일정",
        text="06.19(금) 제1학기 종강일",
        fetched_at="2026-06-08T00:00:00+09:00",
        checksum="abc123",
        verification=SourceVerification(status="verified", notes=[]),
        metadata={},
    )

    docs, failure = parse_source(raw, chunks_per_source=3)

    assert failure is None
    assert docs
    assert docs[0].metadata["chunking_strategy"] == "atomic_guard"
    assert docs[0].metadata["boundary_type"] == "calendar_row"
    assert docs[0].metadata["chunk_confidence"] == "high"
```

If the local `RawSource` schema differs, inspect `src/nlp_term/schemas.py` and adapt field names without changing the assertion intent.

- [ ] **Step 2: Run test and confirm failure**

```powershell
uv run pytest tests/test_prepare_from_sources.py::test_parse_source_records_atomic_aware_chunking_provenance -q
```

Expected: fail because `parse_source()` still uses local string chunks.

- [ ] **Step 3: Replace local chunking call**

In `src/nlp_term/prepare/from_sources.py`, import:

```python
from nlp_term.prepare.chunking import split_source_text
```

Replace the local `_chunk_text()` result with:

```python
chunks = split_source_text(text, label=raw.label, max_chunk_chars=_chunk_chars_for_label(raw.label), max_chunks=chunks_per_source)
```

When creating `KnowledgeDoc`, use `chunk.text` as `body` and add metadata:

```python
metadata={
    **raw.metadata,
    "chunking_strategy": chunk.strategy,
    "boundary_type": chunk.boundary_type,
    "chunk_confidence": chunk.chunk_confidence,
    "chunk_index": chunk.index,
    "char_start": chunk.char_start,
    "char_end": chunk.char_end,
}
```

- [ ] **Step 4: Keep fallback chunks visibly lower confidence**

Do not let downstream code treat `chunk_confidence="low"` as structured evidence. This goal only records the metadata; later evidence sufficiency can decide how strongly to use it.

- [ ] **Step 5: Run focused parse tests**

```powershell
uv run pytest tests/test_prepare_from_sources.py tests/test_atomic_aware_chunking.py -q
```

Expected: pass.

- [ ] **Step 6: Commit parser wiring**

```powershell
git add src/nlp_term/prepare/from_sources.py tests/test_prepare_from_sources.py
git commit -m "feat: record atomic-aware chunking provenance"
```

## Task 4: Rebuild Corpus And Compare Before/After

**Files:**
- Modify: `data/knowledge_seed.json`
- Modify: `data/source_parse_failures.json` if regenerated
- Modify: `model/retrieval_metrics.json`
- Modify: `docs/evidence/task2-public-probe-harness-2026-06-08.json`
- Modify: `docs/task2_public_probe_harness_diagnosis_2026_06_08.md`

- [ ] **Step 1: Capture before metrics**

Run and save temporary before snapshots outside the final commit:

```powershell
uv run python -m nlp_term.retrieve.evaluate --knowledge data/knowledge_seed.json --qa data/qa_seed.json --output model/retrieval_metrics.before_chunking.json
uv run python -m nlp_term.chat.public_probe_experiment --probe data/gold/task2_public_probe_eval.json --knowledge data/knowledge_seed.json --output docs/evidence/task2-public-probe-harness.before-chunking.json --markdown docs/task2_public_probe_harness_before_chunking.md
```

- [ ] **Step 2: Rebuild source-backed knowledge**

```powershell
uv run python -m nlp_term.prepare.from_sources --source-probe data/sources/source_probe.json --output data/knowledge_seed.json --failures-output data/source_parse_failures.json --chunks-per-source 9
```

- [ ] **Step 3: Run quality gates**

```powershell
uv run python -m nlp_term.validators --knowledge-quality data/knowledge_seed.json --source-probe data/sources/source_probe.json --min-total-docs 50 --min-docs-per-label 1 --min-body-chars 80 --min-source-parse-ratio 0.9
uv run python -m nlp_term.retrieve.evaluate --knowledge data/knowledge_seed.json --qa data/qa_seed.json --output model/retrieval_metrics.json
uv run python -m nlp_term.validators --retrieval-metrics model/retrieval_metrics.json --knowledge data/knowledge_seed.json --qa data/qa_seed.json --require-metadata-aware --min-top1-label-accuracy 0.80 --min-top3-source-hit-rate 0.75
```

- [ ] **Step 4: Re-run public probe**

```powershell
uv run python -m nlp_term.chat.public_probe_experiment --probe data/gold/task2_public_probe_eval.json --knowledge data/knowledge_seed.json --output docs/evidence/task2-public-probe-harness-2026-06-08.json --markdown docs/task2_public_probe_harness_diagnosis_2026_06_08.md
```

- [ ] **Step 5: Compare non-regression criteria**

Before committing regenerated artifacts, inspect:

- `answered_count` must not decrease.
- `fail_close_count` must not increase.
- `label_match_rate` must not decrease.
- retrieval `top3_source_hit_rate` must not decrease below the existing gate.
- every generated `KnowledgeDoc.metadata` must include `chunking_strategy`, `boundary_type`, and `chunk_confidence`.
- `fallback_window` chunks must have `chunk_confidence="low"`.
- public probe rows with `output_status="answered"` must keep non-empty `retrieved_doc_ids`.
- domain-sensitive probe rows must retain at least one retrieved source from the expected route domain when such a source exists in `data/knowledge_seed.json`.

If any criterion fails, do not continue to retrieval candidate expansion. Record the failure in `docs/data_expansion_failure_log.md` and fix chunking first.

- [ ] **Step 6: Full verification**

```powershell
uv run ruff check src tests
uv run pytest -q
```

- [ ] **Step 7: Commit refreshed corpus artifacts**

```powershell
git add data/knowledge_seed.json data/source_parse_failures.json model/retrieval_metrics.json docs/evidence/task2-public-probe-harness-2026-06-08.json docs/task2_public_probe_harness_diagnosis_2026_06_08.md
git commit -m "test: refresh corpus after atomic-aware chunking"
```

Do not commit the temporary `*.before_chunking.*` files unless the team explicitly wants historical comparison artifacts in git.

## Task 5: Gate Retrieval Candidate Expansion

**Files:**
- Modify: `docs/superpowers/plans/2026-06-08-retrieval-candidate-expansion.md`
- Modify: `docs/task2_task3_harness_architecture.md`

- [ ] **Step 1: Verify retrieval plan prerequisite**

Confirm the top of `docs/superpowers/plans/2026-06-08-retrieval-candidate-expansion.md` contains:

```markdown
**Prerequisite:** Run `docs/superpowers/plans/2026-06-08-structure-aware-chunking.md` first. Retrieval candidate expansion assumes `data/knowledge_seed.json` has been regenerated with atomic-aware chunking metadata, every generated knowledge row has `metadata.chunking_strategy`, `metadata.boundary_type`, and `metadata.chunk_confidence`, and retrieval/public-probe non-regression checks passed.
```

- [ ] **Step 2: Document chunking policy in architecture**

Add to `docs/task2_task3_harness_architecture.md`:

```markdown
## Atomic-Aware Chunk Boundary Policy

Chunking is an evidence correctness boundary, not only a prompt-length optimization. Clear calendar rows, dining rows, shuttle time rows, notice title/date/body blocks, and graduation requirement lines with nearby headings should be protected before recursive prose splitting. Recursive splitting remains the default for general prose. Fixed-window chunking is the final preservation fallback and must be marked with `chunking_strategy="fallback_window"` and `chunk_confidence="low"`.
```

- [ ] **Step 3: Commit plan gate docs**

```powershell
git add docs/superpowers/plans/2026-06-08-retrieval-candidate-expansion.md docs/task2_task3_harness_architecture.md
git commit -m "docs: gate retrieval expansion on atomic-aware chunking"
```

## Non-Goals

- Do not implement full production source-specific parsers for every source family in this goal.
- Do not claim structured calendar, dining, shuttle, notice, or graduation QA quality from this goal alone.
- Do not infer fields such as normalized dates, menu items, route ids, or credit totals beyond preserving obvious text units.
- Do not introduce LangChain as a dependency just for splitting.
- Do not switch to embedding retrieval in this goal.
- Do not claim Task 2 answer quality improvement unless public probe or retrieval metrics show it.

## Self-Review

- Spec coverage: Covers the user concern that recursive splitting alone may not preserve atomic units, without overcommitting to full domain-specific parser implementation.
- Placeholder scan: No `TBD`, `TODO`, or unspecified “write tests” steps remain.
- Type consistency: `SourceChunk`, `split_source_text`, `strategy`, `boundary_type`, and `chunk_confidence` are introduced before later tasks use them.
- Execution risk: `RawSource` schema may differ from the example in Task 3; the plan names the assertion intent so implementers adapt field names without weakening the metadata contract.
