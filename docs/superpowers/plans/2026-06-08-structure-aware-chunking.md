# Atomic-Unit-First Chunking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current mostly fixed-window source chunking path with an atomic-unit-first chunker before running retrieval candidate expansion.

**Architecture:** Do not assume recursive text splitting preserves meaning. The chunker first extracts domain-specific atomic units such as calendar rows, dining rows, shuttle time rows, notice title/date/body units, and graduation requirement blocks. Recursive section-aware splitting is only a prose fallback, and fixed-size sliding windows are the final fallback.

**Tech Stack:** Python 3.10.12, standard library only, pytest, `uv`.

---

## Why This Plan Changed

The earlier plan treated recursive splitting as the main improvement. That is risky. Recursive splitting can still separate the exact fields Task 2/3 need, such as:

- `06.19(금)` from `제1학기 종강일`
- `2학생회관` from `중식` and menu items
- a shuttle stop name from its departure times
- `2024학번` from project-course or credit requirements
- a notice title from its posted date

This plan therefore promotes atomic unit preservation to the primary acceptance criterion. Recursive chunking is useful for prose, but it is not the correctness boundary.

## File Structure

- Add `src/nlp_term/prepare/chunking.py`
  - Owns `SourceUnit`, `SourceChunk`, atomic unit extraction, recursive prose splitting, fallback windowing, and chunk selection.
- Modify `src/nlp_term/prepare/from_sources.py`
  - Calls `split_source_text()` instead of local `_chunk_text()`.
  - Preserves chunk provenance metadata in every `KnowledgeDoc`.
- Add `tests/test_atomic_unit_chunking.py`
  - Domain-specific atomic unit tests for graduation, calendar, notice, dining, and shuttle.
- Modify `tests/test_prepare_from_sources.py`
  - Verifies parsed `KnowledgeDoc.metadata` includes chunk provenance.
- Modify `docs/task2_task3_harness_architecture.md`
  - Records that prompt-facing evidence quality depends on atomic chunk boundaries.

## Task 1: Lock Atomic Unit Tests Before Implementing

**Files:**
- Add: `tests/test_atomic_unit_chunking.py`

- [ ] **Step 1: Create failing tests**

Create `tests/test_atomic_unit_chunking.py` with these tests:

```python
from __future__ import annotations

from nlp_term.prepare.chunking import split_source_text


def _texts(chunks):
    return [chunk.text for chunk in chunks]


def test_graduation_chunk_preserves_requirement_scope() -> None:
    text = (
        "컴퓨터융합학부 졸업요건\n"
        "2024학번은 프로젝트 관련 전공 교과목 2개 이상을 이수해야 한다.\n"
        "총 졸업학점은 130학점 이상이다.\n"
        "기타 유의사항은 학과 사무실에 문의한다."
    )

    chunks = split_source_text(text, label=0, max_chunk_chars=140, max_chunks=5)

    assert any("2024학번" in chunk and "프로젝트" in chunk and "2개 이상" in chunk for chunk in _texts(chunks))
    assert any("총 졸업학점" in chunk and "130학점" in chunk for chunk in _texts(chunks))


def test_calendar_chunk_preserves_date_and_event_name() -> None:
    text = (
        "03.03(화) 제1학기 개강일\n"
        "06.19(금) 제1학기 종강일\n"
        "06.22(월) 하기 계절학기 개강\n"
    )

    chunks = split_source_text(text, label=2, max_chunk_chars=80, max_chunks=5)

    assert any("06.19(금) 제1학기 종강일" in chunk for chunk in _texts(chunks))


def test_notice_chunk_preserves_title_posted_date_and_body() -> None:
    text = (
        "제목: 2026학년도 하기 계절학기 수강신청 안내\n"
        "작성일: 2026-05-01\n"
        "본문: 수강신청 기간은 2026년 5월 7일부터 5월 9일까지입니다.\n"
        "목록으로 돌아가기"
    )

    chunks = split_source_text(text, label=1, max_chunk_chars=160, max_chunks=5)

    assert any("하기 계절학기 수강신청 안내" in chunk and "2026-05-01" in chunk for chunk in _texts(chunks))
    assert any("2026년 5월 7일" in chunk and "5월 9일" in chunk for chunk in _texts(chunks))


def test_dining_chunk_preserves_date_location_meal_and_menu() -> None:
    text = (
        "2026-06-16 2학생회관 중식\n"
        "백반, 된장국, 제육볶음\n"
        "2026-06-16 3학생회관 석식\n"
        "김치찌개, 계란말이\n"
    )

    chunks = split_source_text(text, label=3, max_chunk_chars=100, max_chunks=5)

    assert any("2026-06-16" in chunk and "2학생회관" in chunk and "중식" in chunk and "제육볶음" in chunk for chunk in _texts(chunks))


def test_shuttle_chunk_preserves_stop_and_departure_times() -> None:
    text = (
        "교내순환 셔틀버스\n"
        "월평역: 08:20 09:30 10:30\n"
        "도서관: 08:35 09:45 10:45\n"
    )

    chunks = split_source_text(text, label=4, max_chunk_chars=100, max_chunks=5)

    assert any("월평역" in chunk and "08:20" in chunk and "09:30" in chunk for chunk in _texts(chunks))
```

- [ ] **Step 2: Run failing tests**

```powershell
uv run pytest tests/test_atomic_unit_chunking.py -q
```

Expected: fail because `nlp_term.prepare.chunking` does not exist yet.

- [ ] **Step 3: Commit tests once they fail for the expected reason**

```powershell
git add tests/test_atomic_unit_chunking.py
git commit -m "test: define atomic source chunking contract"
```

## Task 2: Implement Atomic-Unit-First Chunking Module

**Files:**
- Add: `src/nlp_term/prepare/chunking.py`
- Test: `tests/test_atomic_unit_chunking.py`

- [ ] **Step 1: Add chunking module skeleton**

Create `src/nlp_term/prepare/chunking.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SourceUnit:
    text: str
    unit_type: str
    char_start: int | None = None
    char_end: int | None = None


@dataclass(frozen=True)
class SourceChunk:
    text: str
    strategy: str
    index: int
    boundary_type: str
    char_start: int | None = None
    char_end: int | None = None


def split_source_text(
    text: str,
    *,
    label: int,
    max_chunk_chars: int = 300,
    max_chunks: int = 9,
) -> list[SourceChunk]:
    units = extract_atomic_units(text, label=label)
    if units:
        return _chunks_from_units(units, max_chunk_chars=max_chunk_chars, max_chunks=max_chunks)
    prose_units = _recursive_prose_units(text, max_chunk_chars=max_chunk_chars)
    if prose_units:
        return _chunks_from_units(prose_units, max_chunk_chars=max_chunk_chars, max_chunks=max_chunks)
    return _fallback_window_chunks(text, max_chunk_chars=max_chunk_chars, max_chunks=max_chunks)
```

- [ ] **Step 2: Implement atomic unit extraction**

Add these helpers to the same file:

```python
DATE_ROW_RE = re.compile(r"(?:20\d{2}[-.]\d{1,2}[-.]\d{1,2}|\d{2}\.\d{2})")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
DINING_HEADER_RE = re.compile(r"20\d{2}-\d{2}-\d{2}.*(?:학생회관|생활관|푸드코트).*(?:조식|중식|석식|점심|저녁|아침)")
NOTICE_FIELD_RE = re.compile(r"^(제목|작성일|게시일|본문)\s*[:：]")
GRAD_REQUIREMENT_RE = re.compile(r"(?:학번|졸업|전공|교양|학점|프로젝트|이수)")


def extract_atomic_units(text: str, *, label: int) -> list[SourceUnit]:
    lines = _clean_lines(text)
    if label == 0:
        return _graduation_units(lines)
    if label == 1:
        return _notice_units(lines)
    if label == 2:
        return _calendar_units(lines)
    if label == 3:
        return _dining_units(lines)
    if label == 4:
        return _shuttle_units(lines)
    return []


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]


def _graduation_units(lines: list[str]) -> list[SourceUnit]:
    units: list[SourceUnit] = []
    current_heading = ""
    for line in lines:
        if len(line) <= 30 and any(term in line for term in ("졸업", "교육과정", "요건")):
            current_heading = line
            continue
        if GRAD_REQUIREMENT_RE.search(line):
            text = f"{current_heading} {line}".strip()
            units.append(SourceUnit(text=text, unit_type="graduation_requirement"))
    return units


def _notice_units(lines: list[str]) -> list[SourceUnit]:
    fields: list[str] = []
    for line in lines:
        if NOTICE_FIELD_RE.search(line):
            fields.append(line)
    if len(fields) >= 2:
        return [SourceUnit(text=" ".join(fields), unit_type="notice_detail")]
    return []


def _calendar_units(lines: list[str]) -> list[SourceUnit]:
    return [SourceUnit(text=line, unit_type="calendar_row") for line in lines if DATE_ROW_RE.search(line)]


def _dining_units(lines: list[str]) -> list[SourceUnit]:
    units: list[SourceUnit] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if DINING_HEADER_RE.search(line):
            menu = lines[index + 1] if index + 1 < len(lines) else ""
            units.append(SourceUnit(text=f"{line} {menu}".strip(), unit_type="dining_menu_row"))
            index += 2
            continue
        index += 1
    return units


def _shuttle_units(lines: list[str]) -> list[SourceUnit]:
    units = [SourceUnit(text=line, unit_type="shuttle_time_row") for line in lines if TIME_RE.search(line)]
    if units:
        heading = next((line for line in lines if "셔틀" in line or "버스" in line), "")
        if heading:
            return [SourceUnit(text=f"{heading} {unit.text}", unit_type=unit.unit_type) for unit in units]
    return units
```

- [ ] **Step 3: Implement prose fallback and chunk materialization**

Add:

```python
def _recursive_prose_units(text: str, *, max_chunk_chars: int) -> list[SourceUnit]:
    normalized = "\n".join(_clean_lines(text))
    if not normalized:
        return []
    blocks = [block.strip() for block in re.split(r"\n{2,}", normalized) if block.strip()]
    units: list[SourceUnit] = []
    for block in blocks:
        if len(block) <= max_chunk_chars:
            units.append(SourceUnit(text=block, unit_type="prose_block"))
        else:
            units.extend(SourceUnit(text=part, unit_type="prose_sentence") for part in _split_long_block(block, max_chunk_chars=max_chunk_chars))
    return units


def _split_long_block(block: str, *, max_chunk_chars: int) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[다요]\.)\s+", block) if part.strip()]
    if len(sentences) > 1:
        return _merge_parts(sentences, max_chunk_chars=max_chunk_chars)
    words = block.split()
    if len(words) > 1:
        return _merge_parts(words, max_chunk_chars=max_chunk_chars)
    return []


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


def _chunks_from_units(units: list[SourceUnit], *, max_chunk_chars: int, max_chunks: int) -> list[SourceChunk]:
    chunks: list[SourceChunk] = []
    for unit in units:
        text = " ".join(unit.text.split())
        if not text:
            continue
        if len(text) <= max_chunk_chars:
            chunks.append(
                SourceChunk(
                    text=text,
                    strategy="atomic_unit" if unit.unit_type not in {"prose_block", "prose_sentence"} else "recursive_prose",
                    index=len(chunks) + 1,
                    boundary_type=unit.unit_type,
                    char_start=unit.char_start,
                    char_end=unit.char_end,
                )
            )
        else:
            chunks.extend(_fallback_window_chunks(text, max_chunk_chars=max_chunk_chars, max_chunks=max_chunks - len(chunks), boundary_type=unit.unit_type))
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
                char_start=start,
                char_end=start + len(body),
            )
        )
        if len(chunks) >= max_chunks:
            break
    return chunks
```

- [ ] **Step 4: Run atomic tests**

```powershell
uv run pytest tests/test_atomic_unit_chunking.py -q
```

Expected: pass.

- [ ] **Step 5: Commit implementation**

```powershell
git add src/nlp_term/prepare/chunking.py tests/test_atomic_unit_chunking.py
git commit -m "feat: add atomic-unit-first source chunking"
```

## Task 3: Wire Chunker Into Source Parsing

**Files:**
- Modify: `src/nlp_term/prepare/from_sources.py`
- Modify: `tests/test_prepare_from_sources.py`

- [ ] **Step 1: Add provenance test**

Add a test that calls `parse_source()` with a `RawSource` containing a calendar row and asserts metadata:

```python
def test_parse_source_records_chunking_provenance() -> None:
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
    assert docs[0].metadata["chunking_strategy"] == "atomic_unit"
    assert docs[0].metadata["boundary_type"] == "calendar_row"
    assert docs[0].metadata["chunk_index"] == 1
    assert "char_start" in docs[0].metadata
    assert "char_end" in docs[0].metadata
```

If the local `RawSource` schema differs, inspect `src/nlp_term/schemas.py` and adapt field names without changing the assertion intent.

- [ ] **Step 2: Run test and confirm failure**

```powershell
uv run pytest tests/test_prepare_from_sources.py::test_parse_source_records_chunking_provenance -q
```

Expected: fail because `parse_source()` still uses local string chunks.

- [ ] **Step 3: Replace local chunking call**

In `src/nlp_term/prepare/from_sources.py`, import:

```python
from nlp_term.prepare.chunking import SourceChunk, split_source_text
```

Replace the local `_chunk_text()` result with:

```python
chunks = split_source_text(text, label=raw.label, max_chunk_chars=_chunk_chars_for_label(raw.label), max_chunks=chunks_per_source)
```

Add helper:

```python
def _chunk_chars_for_label(label: int) -> int:
    if label == 3:
        return 220
    return 300
```

When creating `KnowledgeDoc`, use `chunk.text` as `body` and add metadata:

```python
metadata={
    **raw.metadata,
    "chunking_strategy": chunk.strategy,
    "boundary_type": chunk.boundary_type,
    "chunk_index": chunk.index,
    "char_start": chunk.char_start,
    "char_end": chunk.char_end,
}
```

- [ ] **Step 4: Keep old scoring only as selection support**

Remove or bypass local `_ranked_content_chunks()` for chunk boundary creation. If existing `_chunk_score()` quality filtering is still needed, apply it after atomic units are materialized and never drop all chunks of a detected atomic unit family unless they fail hard quality gates such as mojibake/private-use/page-chrome.

- [ ] **Step 5: Run focused parse tests**

```powershell
uv run pytest tests/test_prepare_from_sources.py tests/test_atomic_unit_chunking.py -q
```

Expected: pass.

- [ ] **Step 6: Commit parser wiring**

```powershell
git add src/nlp_term/prepare/from_sources.py tests/test_prepare_from_sources.py
git commit -m "feat: record atomic chunking provenance"
```

## Task 4: Rebuild Corpus And Compare Before/After

**Files:**
- Modify: `data/knowledge_seed.json`
- Modify: `data/source_parse_failures.json` if regenerated
- Modify: `model/retrieval_metrics.json`
- Modify: `docs/evidence/task2-public-probe-harness-2026-06-08.json`
- Modify: `docs/task2_public_probe_harness_diagnosis_2026_06_08.md`

- [ ] **Step 1: Capture before metrics**

Run and save a temporary before snapshot outside the final commit:

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
- every generated `KnowledgeDoc.metadata` must include `chunking_strategy` and `boundary_type`.
- public probe rows with `output_status="answered"` must keep non-empty `retrieved_doc_ids`.
- public probe rows with evidence must keep source URLs in the generated evidence pack path.
- domain-sensitive probe rows must retain at least one retrieved source from the expected route domain when such a source exists in `data/knowledge_seed.json`.
- temporal/calendar/shuttle/dining rows must not lose all date/time/location-bearing evidence compared with the before snapshot.

If any criterion fails, do not continue to retrieval candidate expansion. Record the failure in `docs/data_expansion_failure_log.md` and fix chunking first.

- [ ] **Step 6: Full verification**

```powershell
uv run ruff check src tests
uv run pytest -q
```

- [ ] **Step 7: Commit refreshed corpus artifacts**

```powershell
git add data/knowledge_seed.json data/source_parse_failures.json model/retrieval_metrics.json docs/evidence/task2-public-probe-harness-2026-06-08.json docs/task2_public_probe_harness_diagnosis_2026_06_08.md
git commit -m "test: refresh corpus after atomic chunking"
```

Do not commit the temporary `*.before_chunking.*` files unless the team explicitly wants historical comparison artifacts in git.

## Task 5: Gate Retrieval Candidate Expansion

**Files:**
- Modify: `docs/superpowers/plans/2026-06-08-retrieval-candidate-expansion.md`
- Modify: `docs/task2_task3_harness_architecture.md`

- [ ] **Step 1: Verify retrieval plan prerequisite**

Confirm the top of `docs/superpowers/plans/2026-06-08-retrieval-candidate-expansion.md` contains:

```markdown
**Prerequisite:** Run `docs/superpowers/plans/2026-06-08-structure-aware-chunking.md` first. Retrieval candidate expansion assumes `data/knowledge_seed.json` has been regenerated with atomic chunking metadata, every generated knowledge row has `metadata.chunking_strategy` and `metadata.boundary_type`, and retrieval/public-probe non-regression checks passed.
```

- [ ] **Step 2: Document chunking policy in architecture**

Add to `docs/task2_task3_harness_architecture.md`:

```markdown
## Atomic Chunk Boundary Policy

Chunking is an evidence correctness boundary, not only a prompt-length optimization. Calendar rows, dining rows, shuttle time rows, notice title/date/body units, and graduation requirement blocks should be preserved before recursive prose splitting. Recursive splitting is a fallback for prose. Fixed-window chunking is the final fallback and must be marked with `chunking_strategy="fallback_window"`.
```

- [ ] **Step 3: Commit plan gate docs**

```powershell
git add docs/superpowers/plans/2026-06-08-retrieval-candidate-expansion.md docs/task2_task3_harness_architecture.md
git commit -m "docs: gate retrieval expansion on atomic chunking"
```

## Non-Goals

- Do not implement full production source-specific parsers for every source family in this goal.
- Do not claim structured calendar, dining, shuttle, or notice QA quality from this goal alone.
- Do not introduce LangChain as a dependency just for splitting.
- Do not switch to embedding retrieval in this goal.
- Do not claim Task 2 answer quality improvement unless public probe or retrieval metrics show it.

## Self-Review

- Spec coverage: Covers the critic concern that recursive splitting may not preserve atomic units.
- Placeholder scan: No `TBD`, `TODO`, or unspecified “write tests” steps remain.
- Type consistency: `SourceUnit`, `SourceChunk`, `split_source_text`, `strategy`, and `boundary_type` are introduced before later tasks use them.
- Execution risk: `RawSource` schema may differ from the example in Task 3; the plan names the assertion intent so implementers adapt field names without weakening the metadata contract.
