# Task 2 Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal Task 2 pipeline where retrieval produces a clean evidence pack, a local llama-server backend writes the final Korean answer, and deterministic validators measure whether the output is natural enough without hiding failures behind fallback behavior.

**Architecture:** Keep retrieval as a material selector, not the answer writer. Convert retrieved docs into an `EvidencePack` that hides internal doc IDs, then send only clean facts/source names/cautions to a local llama-server answer writer. Validate the raw answer deterministically and record failures instead of retrying or falling back.

**Tech Stack:** Python 3.10.12, uv, pydantic, requests, pytest, llama.cpp server HTTP API, existing `nlp_term.chat`, `nlp_term.retrieve`, and `nlp_term.validators` modules.

---

## Architecture And Critic Review

### Round 1

Architect verdict: `WATCH`

- Direction is right, but schema boundaries need to be explicit before implementation.
- `rank_docs()` returns `RetrievedDoc` rows with ranking/provenance fields only; it does not include source body or metadata.
- The orchestrator must map `RetrievedDoc.doc_id` back to full `KnowledgeDoc` rows before building an `EvidencePack`.
- `answer_chars` may be recorded as metadata, but answer length must not decide pass/fail.

Critic verdict: `REQUEST_CHANGES`

- Remove the arbitrary `too_short` / 30-character validator gate.
- Prevent real current titles like `graduation source 1` or `dining source 1` from leaking into prompts.
- Specify the retrieval-to-evidence join boundary.
- Test llama-server health, malformed responses, trailing slash URL normalization, and no-fallback failure recording.
- Either make unsupported date/number validation evidence-aware or remove it from the minimal slice.

Round 1 resolution:

- `too_short` is removed from the new validator contract.
- `answer_chars` remains metadata only.
- `EvidencePack` receives full `KnowledgeDoc` material, while `RetrievedDoc` stays artifact provenance only.
- Generic source names matching `source \d+`, `chunk_`, or internal IDs must be sanitized before prompt text.
- Minimal vertical slice does not reject unsupported dates/numbers yet; it records `must_not_claim` violations and leaves stronger evidence-aware numeric validation for a later step.

### Round 2

Architect verdict: `REQUEST_CHANGES`

- The amended plan fixed the main schema boundaries and llama-server tests.
- Blocking issue: `not_enough_korean_text` still used a fixed Korean-character threshold, which reintroduced an arbitrary length gate under another name.
- Watch item: route/retrieval label filtering must be explicit because existing composer behavior filters evidence to the routed label.

Critic verdict: `REQUEST_CHANGES`

- The vertical-slice artifact contract must include all fields required by `validate_metric_claim()`: `evaluation_set_type`, `dataset_origin`, `claim_level`, `input_path`, and `input_checksum`.
- The answer validator must not fail on fixed Korean character count.

Round 2 resolution:

- Remove all fixed answer-length and fixed Korean-character-count failure gates.
- Keep only non-length structural validation: empty/whitespace answer, no Hangul at all, raw JSON/template leakage, internal ID leakage, system/fallback leakage, and exact `must_not_claim` violations.
- Add metric-claim fields and checksum binding to the vertical-slice artifact contract.
- Do not match the current composer's hard label filtering in the vertical slice. Treat the classifier/router as a soft hint: retrieval remains the evidence selector, label matches may be recorded or used as a tie-breaker, and label mismatches must not silently remove otherwise relevant retrieved documents.

## LangChain-Inspired Architecture

This plan uses LangChain-style RAG boundaries without adding `langchain` as a dependency.

- Retriever boundary mirrors `BaseRetriever`: retrieval accepts an unstructured question and returns document candidates/provenance, not an answer.
- Combine-docs boundary mirrors `create_stuff_documents_chain`: `build_evidence_pack()` formats full `KnowledgeDoc` rows into clean prompt context.
- Orchestrator boundary mirrors `create_retrieval_chain`: `run_task2_vertical_slice()` returns both retrieved context/evidence metadata and the generated answer.
- Source-return behavior mirrors source-aware QA chains: artifacts retain source URLs, retrieved doc IDs, and ranking scores even though prompt text hides internal IDs.
- Do not use LangChain structured-output agent/tool strategies for answer generation; the natural-answer path must not retry, fallback, or force tool/schema output.
- Pydantic is acceptable only for local evidence, artifact, and validation models.

---

## File Structure

- Create `src/nlp_term/chat/evidence_pack.py`
  - Owns `EvidenceItem`, `EvidencePack`, and `build_evidence_pack`.
  - Converts ranked retrieval docs into clean answer material.
  - Must not expose internal `doc_id`, `chunk_`, or `source 1` strings in the LLM-facing text.
  - Receives full `KnowledgeDoc` rows, not `RetrievedDoc` rows.

- Create `src/nlp_term/chat/prompts.py`
  - Owns Task 2 system prompt and prompt builder.
  - Defines the LLM role: answer naturally in Korean, use evidence, do not invent dates/numbers, hide internal IDs.

- Create `src/nlp_term/chat/llama_server_backend.py`
  - Owns llama-server health check and HTTP generation.
  - No external LLM API.
  - No deterministic fallback inside this backend.

- Create `src/nlp_term/chat/answer_validation.py`
  - Owns deterministic answer checks.
  - Detects internal ID exposure, JSON/template leakage, explicit forbidden claims, and missing Korean natural text.
  - Records answer length as metadata only; length is not a pass/fail criterion.
  - Does not use any fixed minimum character-count threshold.

- Create `src/nlp_term/chat/vertical_slice.py`
  - Orchestrates route -> retrieval -> evidence pack -> llama-server generation -> validation -> artifact row.
  - Resolves ranked `RetrievedDoc.doc_id` rows back to full `KnowledgeDoc` rows before building the evidence pack.
  - Uses `route.label` as a soft ranking/metadata hint only. Do not discard retrieved documents solely because their label differs from the classifier/router output. Prefer label-matched docs when scores are otherwise comparable, but preserve the retriever's top evidence candidates and record label match/mismatch metadata.
  - Writes metric-claim-compatible top-level fields and checksums.
  - Provides CLI for evaluating Task 2 gold rows.

- Modify `src/nlp_term/chat/compare_backends.py`
  - Keep existing backend comparison intact.
  - Add optional input from the new vertical-slice artifact only if needed after the new path works.

- Test files:
  - Create `tests/test_task2_evidence_pack.py`
  - Create `tests/test_task2_prompt_contract.py`
  - Create `tests/test_llama_server_backend.py`
  - Create `tests/test_task2_answer_validation.py`
  - Create `tests/test_task2_vertical_slice.py`

- Docs/evidence:
  - Create `docs/evidence/task2-vertical-slice-2026-06-07.json`
  - Update `docs/task2_llm_backend_plan.md` or create `docs/task2_vertical_slice_notes.md`

---

### Task 1: Evidence Pack Schema And Builder

**Files:**
- Create: `src/nlp_term/chat/evidence_pack.py`
- Test: `tests/test_task2_evidence_pack.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from nlp_term.chat.evidence_pack import build_evidence_pack
from nlp_term.retrieve.knowledge import KnowledgeDoc


def test_evidence_pack_hides_internal_ids_and_keeps_clean_source_material() -> None:
    docs = [
        KnowledgeDoc(
            doc_id="academic_calendar_chunk_1",
            label=2,
            domain="academic_calendar",
            title="학사일정",
            body="2026학년도 제1학기 수강신청은 공식 학사일정에서 확인한다.",
            source_url="https://plus.cnu.ac.kr/calendar",
            source_id="academic_calendar",
            metadata={"source_name": "충남대학교 학사일정"},
        )
    ]

    pack = build_evidence_pack(
        question="이번 학기 수강신청 일정은 어디서 확인해?",
        label=2,
        domain="academic_calendar",
        docs=docs,
        max_items=1,
    )

    prompt_text = pack.to_prompt_text()
    assert pack.question == "이번 학기 수강신청 일정은 어디서 확인해?"
    assert pack.intent_label == 2
    assert pack.intent_domain == "academic_calendar"
    assert pack.items[0].source_name == "충남대학교 학사일정"
    assert "수강신청" in pack.items[0].facts[0]
    assert "academic_calendar_chunk_1" not in prompt_text
    assert "chunk_" not in prompt_text
    assert "source 1" not in prompt_text.lower()
    assert "https://plus.cnu.ac.kr/calendar" in prompt_text


def test_evidence_pack_sanitizes_generic_source_titles() -> None:
    docs = [
        KnowledgeDoc(
            doc_id="graduation_curriculum_pdf_chunk_3",
            label=0,
            domain="graduation",
            title="graduation source 1",
            body="생화학과 졸업요건은 입학연도별 교육과정표를 함께 확인해야 한다.",
            source_url="https://biochemistry.cnu.ac.kr/grad",
            source_id="graduation_biochemistry_requirements",
            metadata={"source_department": "생화학과", "source_parser_type": "pdf"},
        )
    ]

    pack = build_evidence_pack(
        question="생화학과 졸업요건 알려줘",
        label=0,
        domain="graduation",
        docs=docs,
        max_items=1,
    )

    prompt_text = pack.to_prompt_text()
    assert "graduation source 1" not in prompt_text
    assert "source 1" not in prompt_text.lower()
    assert "chunk_" not in prompt_text
    assert pack.items[0].source_name == "생화학과 졸업요건"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/test_task2_evidence_pack.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'nlp_term.chat.evidence_pack'
```

- [ ] **Step 3: Write minimal implementation**

Implement `EvidenceItem`, `EvidencePack`, and `build_evidence_pack` using pydantic models. Extract facts by taking the first clean sentence-like body segment. Use source names in this order:

1. `metadata["source_name"]` if present and clean
2. `{source_department} 졸업요건` for graduation docs with `source_department`
3. a domain-specific Korean label such as `충남대학교 학사일정`, `충남대학교 공지사항`, `충남대학교 식단`, or `충남대학교 셔틀 안내`
4. the URL hostname

Never use raw titles that match `source \d+`, include `chunk_`, or look like internal debug/source labels.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
uv run pytest tests/test_task2_evidence_pack.py -v
uv run ruff check src tests
```

Expected: test passes and ruff reports `All checks passed!`

- [ ] **Step 5: Commit**

```powershell
git add src/nlp_term/chat/evidence_pack.py tests/test_task2_evidence_pack.py
git commit -m "feat: add task2 evidence pack"
```

---

### Task 2: Task 2 System Prompt Contract

**Files:**
- Create: `src/nlp_term/chat/prompts.py`
- Test: `tests/test_task2_prompt_contract.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from nlp_term.chat.evidence_pack import EvidenceItem, EvidencePack
from nlp_term.chat.prompts import build_task2_prompt


def test_task2_prompt_defines_llm_as_natural_answer_writer_not_tool_agent() -> None:
    pack = EvidencePack(
        question="졸업 전공 학점 기준 알려줘",
        intent_label=0,
        intent_domain="graduation",
        items=[
            EvidenceItem(
                source_name="생화학과 졸업요건",
                source_url="https://biochemistry.cnu.ac.kr/grad",
                facts=["졸업 기준은 전공과 교양 이수 기준을 함께 확인해야 한다."],
                cautions=["근거에 없는 세부 학점 숫자는 단정하지 않는다."],
            )
        ],
    )

    prompt = build_task2_prompt(pack)

    assert "충남대학교 학생을 돕는 캠퍼스 챗봇" in prompt
    assert "자연스럽게" in prompt
    assert "도구를 호출하지 않는다" in prompt
    assert "근거에 없는 날짜, 학점, 장소는 단정하지 않는다" in prompt
    assert "내부 문서 ID" in prompt
    assert "academic_calendar_chunk_1" not in prompt
    assert "생화학과 졸업요건" in prompt
    assert "https://biochemistry.cnu.ac.kr/grad" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
uv run pytest tests/test_task2_prompt_contract.py -v
```

Expected: import failure for `nlp_term.chat.prompts`.

- [ ] **Step 3: Write minimal implementation**

Implement:

```python
TASK2_SYSTEM_PROMPT = """너는 충남대학교 학생을 돕는 캠퍼스 챗봇이다.
역할은 검색된 근거를 바탕으로 자연스러운 한국어 답변을 작성하는 것이다.
도구를 호출하지 않는다.
근거에 없는 날짜, 학점, 장소는 단정하지 않는다.
내부 문서 ID, chunk ID, source 번호를 답변에 노출하지 않는다.
답변은 2-5문장으로 작성한다."""
```

`build_task2_prompt(pack)` should append the evidence pack prompt text and the user question.

- [ ] **Step 4: Run test to verify it passes**

```powershell
uv run pytest tests/test_task2_prompt_contract.py tests/test_task2_evidence_pack.py -v
uv run ruff check src tests
```

- [ ] **Step 5: Commit**

```powershell
git add src/nlp_term/chat/prompts.py tests/test_task2_prompt_contract.py
git commit -m "feat: define task2 answer prompt"
```

---

### Task 3: Llama Server Backend

**Files:**
- Create: `src/nlp_term/chat/llama_server_backend.py`
- Test: `tests/test_llama_server_backend.py`

- [ ] **Step 1: Write failing tests with monkeypatch**

```python
from __future__ import annotations

import pytest

from nlp_term.chat.llama_server_backend import (
    LlamaServerUnavailable,
    check_llama_server_health,
    generate_with_llama_server,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(self.text)


def test_generate_with_llama_server_reads_content_from_openai_compatible_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        assert url == "http://127.0.0.1:8080/v1/chat/completions"
        assert json["temperature"] == 0.2
        return FakeResponse(
            200,
            {"choices": [{"message": {"content": "공식 학사일정 페이지에서 확인하면 됩니다."}}]},
        )

    monkeypatch.setattr("requests.post", fake_post)

    answer = generate_with_llama_server(
        prompt="질문: 수강신청 일정은?",
        base_url="http://127.0.0.1:8080",
        timeout_seconds=5,
    )

    assert answer == "공식 학사일정 페이지에서 확인하면 됩니다."


def test_llama_server_base_url_trailing_slash_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        assert url == "http://127.0.0.1:8080/v1/chat/completions"
        return FakeResponse(200, {"choices": [{"message": {"content": "정상 답변"}}]})

    monkeypatch.setattr("requests.post", fake_post)

    assert generate_with_llama_server(prompt="질문", base_url="http://127.0.0.1:8080/") == "정상 답변"


def test_generate_with_llama_server_does_not_fallback_on_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        raise OSError("connection refused")

    monkeypatch.setattr("requests.post", fake_post)

    with pytest.raises(LlamaServerUnavailable, match="connection refused"):
        generate_with_llama_server(prompt="질문", base_url="http://127.0.0.1:8080")


def test_generate_with_llama_server_rejects_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        return FakeResponse(200, {"choices": []})

    monkeypatch.setattr("requests.post", fake_post)

    with pytest.raises(LlamaServerUnavailable, match="malformed"):
        generate_with_llama_server(prompt="질문", base_url="http://127.0.0.1:8080")


def test_check_llama_server_health_uses_health_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, timeout: int) -> FakeResponse:
        assert url == "http://127.0.0.1:8080/health"
        return FakeResponse(200, {"status": "ok"})

    monkeypatch.setattr("requests.get", fake_get)

    assert check_llama_server_health("http://127.0.0.1:8080") is True
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
uv run pytest tests/test_llama_server_backend.py -v
```

Expected: import failure.

- [ ] **Step 3: Write minimal implementation**

Use `requests.post` against `/v1/chat/completions`. Normalize trailing slashes in `base_url`. Return `choices[0].message.content`. Raise `LlamaServerUnavailable` on request errors, HTTP errors, empty content, or malformed content. Add `check_llama_server_health(base_url)` using `/health`. Do not call deterministic composer.

- [ ] **Step 4: Run test to verify it passes**

```powershell
uv run pytest tests/test_llama_server_backend.py -v
uv run ruff check src tests
```

- [ ] **Step 5: Commit**

```powershell
git add src/nlp_term/chat/llama_server_backend.py tests/test_llama_server_backend.py
git commit -m "feat: add llama server backend"
```

---

### Task 4: Deterministic Answer Validator

**Files:**
- Create: `src/nlp_term/chat/answer_validation.py`
- Test: `tests/test_task2_answer_validation.py`

- [ ] **Step 1: Write failing tests**

```python
from __future__ import annotations

from nlp_term.chat.answer_validation import validate_task2_answer


def test_answer_validator_rejects_internal_ids_and_template_leaks() -> None:
    answer = "근거 후보: academic_calendar_chunk_1 source 1"
    result = validate_task2_answer(answer)

    assert result.passed is False
    assert "internal_id_exposed" in result.failures
    assert "too_short" not in result.failures
    assert result.answer_chars == len(answer)


def test_answer_validator_accepts_natural_grounded_korean_answer() -> None:
    result = validate_task2_answer(
        "수강신청 일정은 충남대학교 공식 학사일정 페이지에서 확인하는 게 가장 정확해요. "
        "다만 세부 날짜는 학기마다 달라질 수 있어서, 신청 전에 공식 페이지를 한 번 더 확인해 주세요."
    )

    assert result.passed is True
    assert result.failures == []


def test_answer_validator_rejects_must_not_claims_without_retry() -> None:
    result = validate_task2_answer(
        "수강신청은 3월 2일에 시작합니다.",
        must_not_claim=["3월 2일"],
    )

    assert result.passed is False
    assert "must_not_claim_violation" in result.failures


def test_answer_validator_rejects_empty_or_non_korean_output_without_length_gate() -> None:
    empty = validate_task2_answer("   ")
    english = validate_task2_answer("Check the official page.")

    assert empty.passed is False
    assert "empty_answer" in empty.failures
    assert english.passed is False
    assert "no_hangul_text" in english.failures
    assert "too_short" not in empty.failures
    assert "too_short" not in english.failures
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
uv run pytest tests/test_task2_answer_validation.py -v
```

- [ ] **Step 3: Write minimal implementation**

Create pydantic `AnswerValidationResult` with:

- `passed: bool`
- `failures: list[str]`
- `answer_chars: int`
- `must_not_claim_violations: list[str]`

Checks:

- contains `chunk_`, `doc_`, or `source 1` style internal tokens -> `internal_id_exposed`
- starts with `{` or `[` -> `raw_json_or_template_text`
- contains `fallback` or `system prompt` -> `system_or_fallback_leak`
- answer is empty or whitespace only -> `empty_answer`
- answer contains no Hangul syllables at all -> `no_hangul_text`
- exact `must_not_claim` string appears in answer -> `must_not_claim_violation`

`answer_chars` is always recorded for analysis but never contributes to `passed` by itself. Do not implement a fixed minimum character-count or fixed minimum Hangul-count failure in this task.

- [ ] **Step 4: Run test to verify it passes**

```powershell
uv run pytest tests/test_task2_answer_validation.py -v
uv run ruff check src tests
```

- [ ] **Step 5: Commit**

```powershell
git add src/nlp_term/chat/answer_validation.py tests/test_task2_answer_validation.py
git commit -m "feat: validate task2 generated answers"
```

---

### Task 5: Vertical Slice Orchestrator

**Files:**
- Create: `src/nlp_term/chat/vertical_slice.py`
- Test: `tests/test_task2_vertical_slice.py`

- [ ] **Step 1: Write failing test with fake generator**

```python
from __future__ import annotations

import json
from pathlib import Path

from nlp_term.chat.vertical_slice import run_task2_vertical_slice


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_vertical_slice_records_evidence_pack_answer_and_validation(tmp_path: Path) -> None:
    gold_path = tmp_path / "task2_answer_eval_gold.json"
    facts_path = tmp_path / "task2_fact_gold.json"
    knowledge_path = tmp_path / "knowledge_seed.json"
    output_path = tmp_path / "task2_vertical_slice.json"
    _write_json(
        facts_path,
        [
            {
                "fact_id": "calendar_source",
                "label": 2,
                "source_doc_id": "calendar_doc_1",
                "source_url": "https://plus.cnu.ac.kr/calendar",
                "claim": "수강신청 일정은 공식 학사일정에서 확인한다.",
                "evidence_quote": "공식 학사일정에서 확인",
                "answerable_scope": "static",
            }
        ],
    )
    _write_json(
        gold_path,
        [
            {
                "user": "수강신청 일정 어디서 봐?",
                "expected_fact_ids": ["calendar_source"],
                "must_not_claim": [],
                "naturalness_score": None,
                "factuality_score": None,
            }
        ],
    )
    _write_json(
        knowledge_path,
        [
            {
                "doc_id": "calendar_doc_1",
                "label": 2,
                "domain": "academic_calendar",
                "title": "학사일정",
                "body": "수강신청 일정은 공식 학사일정에서 확인한다.",
                "source_url": "https://plus.cnu.ac.kr/calendar",
                "source_id": "calendar",
                "metadata": {"source_name": "충남대학교 학사일정"},
            }
        ],
    )

    def fake_generate(prompt: str) -> str:
        assert "calendar_doc_1" not in prompt
        assert "충남대학교 학사일정" in prompt
        return "수강신청 일정은 충남대학교 공식 학사일정 페이지에서 확인하면 됩니다."

    report = run_task2_vertical_slice(
        gold_path=gold_path,
        facts_path=facts_path,
        knowledge_path=knowledge_path,
        output_path=output_path,
        generate_answer=fake_generate,
    )

    assert report["evaluation_scope"] == "task2_vertical_slice"
    assert report["evaluation_set_type"] == "task2_gold"
    assert report["dataset_origin"] == "task2_gold"
    assert report["claim_level"] == "qualitative_check"
    assert report["input_path"] == str(gold_path)
    assert report["input_checksum"]
    assert report["knowledge_checksum"]
    assert report["row_count"] == 1
    assert report["generation_backend"] == "llama_server"
    assert report["fallback_used"] is False
    assert report["validation_pass_rate"] == 1.0
    assert report["rows"][0]["validation"]["passed"] is True
    assert "calendar_doc_1" not in report["rows"][0]["prompt"]
    assert report["rows"][0]["retrieved_doc_ids"] == ["calendar_doc_1"]
    assert report["rows"][0]["evidence_items"][0]["source_name"] == "충남대학교 학사일정"
    assert report["rows"][0]["route_used_as_hint"] is True
    assert report["rows"][0]["label_match_count"] == 1
    assert report["rows"][0]["label_mismatch_count"] == 0


def test_vertical_slice_records_generation_failure_without_fallback(tmp_path: Path) -> None:
    gold_path = tmp_path / "task2_answer_eval_gold.json"
    facts_path = tmp_path / "task2_fact_gold.json"
    knowledge_path = tmp_path / "knowledge_seed.json"
    output_path = tmp_path / "task2_vertical_slice.json"
    _write_json(
        facts_path,
        [
            {
                "fact_id": "calendar_source",
                "label": 2,
                "source_doc_id": "calendar_doc_1",
                "source_url": "https://plus.cnu.ac.kr/calendar",
                "claim": "수강신청 일정은 공식 학사일정에서 확인한다.",
                "evidence_quote": "공식 학사일정에서 확인",
                "answerable_scope": "static",
            }
        ],
    )
    _write_json(
        gold_path,
        [
            {
                "user": "수강신청 일정 어디서 봐?",
                "expected_fact_ids": ["calendar_source"],
                "must_not_claim": [],
                "naturalness_score": None,
                "factuality_score": None,
            }
        ],
    )
    _write_json(
        knowledge_path,
        [
            {
                "doc_id": "calendar_doc_1",
                "label": 2,
                "domain": "academic_calendar",
                "title": "academic_calendar source 1",
                "body": "수강신청 일정은 공식 학사일정에서 확인한다.",
                "source_url": "https://plus.cnu.ac.kr/calendar",
                "source_id": "calendar",
                "metadata": {},
            }
        ],
    )

    def failing_generate(prompt: str) -> str:
        raise RuntimeError("llama server unavailable")

    report = run_task2_vertical_slice(
        gold_path=gold_path,
        facts_path=facts_path,
        knowledge_path=knowledge_path,
        output_path=output_path,
        generate_answer=failing_generate,
    )

    assert report["fallback_used"] is False
    assert report["validation_pass_rate"] == 0.0
    assert report["rows"][0]["status"] == "generation_failed"
    assert report["rows"][0]["answer"] == ""
    assert "llama server unavailable" in report["rows"][0]["generation_error"]
    assert "source 1" not in report["rows"][0]["prompt"].lower()


def test_vertical_slice_keeps_retrieved_evidence_when_route_label_differs(tmp_path: Path) -> None:
    gold_path = tmp_path / "task2_answer_eval_gold.json"
    facts_path = tmp_path / "task2_fact_gold.json"
    knowledge_path = tmp_path / "knowledge_seed.json"
    output_path = tmp_path / "task2_vertical_slice.json"
    _write_json(
        facts_path,
        [
            {
                "fact_id": "notice_source",
                "label": 1,
                "source_doc_id": "notice_doc_1",
                "source_url": "https://plus.cnu.ac.kr/notice",
                "claim": "수강신청 변경 공지는 공식 공지사항에서 확인한다.",
                "evidence_quote": "공식 공지사항에서 확인",
                "answerable_scope": "static",
            }
        ],
    )
    _write_json(
        gold_path,
        [
            {
                "user": "수강신청 변경 일정 공지는 어디서 봐?",
                "expected_fact_ids": ["notice_source"],
                "must_not_claim": [],
                "naturalness_score": None,
                "factuality_score": None,
            }
        ],
    )
    _write_json(
        knowledge_path,
        [
            {
                "doc_id": "notice_doc_1",
                "label": 1,
                "domain": "notices",
                "title": "학사 공지사항",
                "body": "수강신청 변경 공지는 공식 공지사항에서 확인한다.",
                "source_url": "https://plus.cnu.ac.kr/notice",
                "source_id": "notice",
                "metadata": {"source_name": "충남대학교 공지사항"},
            }
        ],
    )

    def fake_generate(prompt: str) -> str:
        return "수강신청 변경 공지는 충남대학교 공식 공지사항에서 확인하면 됩니다."

    report = run_task2_vertical_slice(
        gold_path=gold_path,
        facts_path=facts_path,
        knowledge_path=knowledge_path,
        output_path=output_path,
        generate_answer=fake_generate,
        route_label_override_for_test=2,
    )

    assert report["rows"][0]["route_label"] == 2
    assert report["rows"][0]["retrieved_doc_ids"] == ["notice_doc_1"]
    assert report["rows"][0]["evidence_items"][0]["source_name"] == "충남대학교 공지사항"
    assert report["rows"][0]["route_used_as_hint"] is True
    assert report["rows"][0]["label_match_count"] == 0
    assert report["rows"][0]["label_mismatch_count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
uv run pytest tests/test_task2_vertical_slice.py -v
```

- [ ] **Step 3: Write minimal implementation**

Implement `run_task2_vertical_slice`:

1. load Task 2 answer gold rows
2. route question
3. load full `KnowledgeDoc` rows and index them by `doc_id`
4. rank top3 docs with `rank_docs()`
5. resolve ranked `RetrievedDoc.doc_id` values back to full `KnowledgeDoc` rows, preserving rank order
6. annotate resolved `KnowledgeDoc` rows with whether `doc.label == route.label`; record `label_match_count`, `label_mismatch_count`, and `route_used_as_hint=true`
7. build evidence pack from the resolved top retrieved `KnowledgeDoc` rows without hard label filtering; optionally order label-matched rows ahead only when retrieval scores are tied or near-tied
8. build prompt
9. call `generate_answer(prompt)` if provided, otherwise call llama-server backend
10. validate answer with `must_not_claim`
11. write JSON artifact with row-level prompt, answer, evidence source names/URLs, retrieved doc IDs/scores, validation result, and backend status

Top-level artifact fields must include:

- `evaluation_scope: "task2_vertical_slice"`
- `evaluation_set_type: "task2_gold"`
- `dataset_origin: "task2_gold"`
- `claim_level: "qualitative_check"`
- `input_path`
- `input_checksum`
- `facts_path`
- `facts_checksum`
- `knowledge_path`
- `knowledge_checksum`
- `generation_backend: "llama_server"`
- `fallback_used: false`

Do not retry. Do not fallback. If generation fails, record `status="generation_failed"`, empty answer, error type/message, and `fallback_used=False`.

- [ ] **Step 4: Run test to verify it passes**

```powershell
uv run pytest tests/test_task2_vertical_slice.py tests/test_task2_evidence_pack.py tests/test_task2_prompt_contract.py tests/test_task2_answer_validation.py tests/test_llama_server_backend.py -v
uv run ruff check src tests
```

- [ ] **Step 5: Commit**

```powershell
git add src/nlp_term/chat/vertical_slice.py tests/test_task2_vertical_slice.py
git commit -m "feat: add task2 vertical slice pipeline"
```

---

### Task 6: Local Llama Server Smoke Command And Evidence

**Files:**
- Create: `docs/evidence/task2-vertical-slice-2026-06-07.json`
- Modify: `docs/task2_llm_backend_plan.md` or create `docs/task2_vertical_slice_notes.md`

- [ ] **Step 1: Start llama-server manually in a separate terminal**

Run:

```powershell
llama-server -m model\generator\Qwen3.5-9B-Q4_K_M.gguf -c 4096 -ngl auto --cache-type-k q8_0 --cache-type-v q8_0 --host 127.0.0.1 --port 8080 --reasoning off --reasoning-budget 0
```

Expected:

```text
server is listening on 127.0.0.1:8080
```

- [ ] **Step 2: Run the vertical slice on current Task 2 gold**

Run:

```powershell
uv run python -m nlp_term.chat.vertical_slice --gold data/gold/task2_answer_eval_gold.json --facts data/gold/task2_fact_gold.json --knowledge data/knowledge_seed.json --output model/metrics/task2_vertical_slice.json --llama-server-url http://127.0.0.1:8080 --limit 5
```

Expected:

```text
wrote model\metrics\task2_vertical_slice.json
```

- [ ] **Step 3: Validate metric metadata**

Run:

```powershell
uv run python -m nlp_term.validators --metric-claim model/metrics/task2_vertical_slice.json --input data/gold/task2_answer_eval_gold.json --require-dataset-origin task2_gold --require-claim-level qualitative_check
```

Expected:

```text
validation-ok
```

- [ ] **Step 4: Write evidence summary**

Record:

- llama-server command
- model path and checksum
- context size and KV cache setting used
- limit used
- validation pass rate
- internal ID exposure count
- `must_not_claim` violation count
- answer length stats as metadata only; no `too_short` failure count
- generation failure count
- note that this is not final Task 2 quality

- [ ] **Step 5: Commit**

```powershell
git add docs/evidence/task2-vertical-slice-2026-06-07.json docs/task2_vertical_slice_notes.md
git commit -m "docs: record task2 vertical slice evidence"
```

---

### Task 7: Final Verification

**Files:**
- No new files unless a preceding task fails and needs repair.

- [ ] **Step 1: Run focused tests**

```powershell
uv run pytest tests/test_task2_evidence_pack.py tests/test_task2_prompt_contract.py tests/test_llama_server_backend.py tests/test_task2_answer_validation.py tests/test_task2_vertical_slice.py tests/test_task2_answer_eval_artifact.py tests/test_backend_evidence_separation.py tests/test_chat_provenance.py
```

Expected:

```text
passed
```

- [ ] **Step 2: Run lint and compile**

```powershell
uv run ruff check src tests
uv run python -m compileall src\nlp_term
```

Expected:

```text
All checks passed!
```

- [ ] **Step 3: Check git status**

```powershell
git status --short
```

Expected: no unstaged changes.

---

## Self-Review

Spec coverage:

- Retrieval as material selector: Task 1 and Task 5.
- LLM as answer writer: Task 2, Task 3, Task 5.
- Local llama-server backend: Task 3 and Task 6.
- No external LLM API: Task 3 explicitly uses local llama-server URL.
- No fallback masking: Task 3 and Task 5 raise/record failure, no deterministic composer fallback.
- Deterministic validation: Task 4 and Task 5.
- Evidence and metric boundary: Task 6.

Placeholder scan:

- No implementation step depends on "TBD" or unspecified behavior.
- Edge cases are named as explicit validator failures.

Type consistency:

- `EvidencePack`, `EvidenceItem`, `build_evidence_pack`, `build_task2_prompt`, `generate_with_llama_server`, `validate_task2_answer`, and `run_task2_vertical_slice` are introduced before use.
