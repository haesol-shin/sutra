# Validator Policy Softening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change Task 2 answer validation from over-aggressive fail-close behavior into a policy that hard-blocks internal leakage while recording non-fatal warnings for optional URL/numeric/institution mismatches.

**Architecture:** Keep the existing regex-based validator, but split failures into `failures` and `warnings`. Internal trace/template leakage remains a hard failure. URL, numeric, institution, and menu mismatch checks become warnings unless the caller explicitly opts into strict grounding.

**Tech Stack:** Python 3.10.12, Pydantic, pytest, `uv`.

---

## File Structure

- Modify `src/nlp_term/chat/answer_validation.py`: add warning fields and a `strict_grounding` flag.
- Modify `src/nlp_term/chat/orchestrator.py`: call validator with non-strict grounding for normal Task 2 harness generation.
- Modify `tests/test_task2_answer_validation.py`: update old hard-failure expectations and add leakage hard-block tests.
- Modify `tests/test_public_probe_experiment.py`: assert writer bottlenecks shrink when deterministic answers contain optional URLs/numbers.

## Task 1: Add Warning Channel

**Files:**
- Modify: `src/nlp_term/chat/answer_validation.py`
- Test: `tests/test_task2_answer_validation.py`

- [ ] **Step 1: Write failing tests for warning-only optional claims**

Append to `tests/test_task2_answer_validation.py`:

```python
def test_answer_validator_warns_but_passes_optional_url_and_numeric_claims_by_default() -> None:
    result = validate_task2_answer(
        "졸업 기준은 130학점 이상일 수 있으며 자세한 내용은 https://example.cnu.ac.kr 에서 확인하세요.",
        evidence_texts=["졸업 기준은 학과별 공식 자료에서 확인해야 한다."],
    )

    assert result.passed is True
    assert result.failures == []
    assert "unsupported_url_claim" in result.warnings
    assert "unsupported_numeric_claim" in result.warnings
    assert result.unsupported_urls == ["https://example.cnu.ac.kr"]
    assert result.unsupported_numeric_claims == ["130학점"]


def test_answer_validator_can_still_fail_optional_claims_in_strict_grounding_mode() -> None:
    result = validate_task2_answer(
        "졸업 기준은 130학점 이상입니다.",
        evidence_texts=["졸업 기준은 학과별 공식 자료에서 확인해야 한다."],
        strict_grounding=True,
    )

    assert result.passed is False
    assert "unsupported_numeric_claim" in result.failures
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
uv run pytest tests/test_task2_answer_validation.py::test_answer_validator_warns_but_passes_optional_url_and_numeric_claims_by_default tests/test_task2_answer_validation.py::test_answer_validator_can_still_fail_optional_claims_in_strict_grounding_mode -q
```

Expected: fail because `warnings` and `strict_grounding` do not exist.

- [ ] **Step 3: Implement warnings and strict grounding**

In `src/nlp_term/chat/answer_validation.py`, modify `Task2AnswerValidationResult`:

```python
class Task2AnswerValidationResult(BaseModel):
    passed: bool
    failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    answer_chars: int
    must_not_claim_violations: list[str] = Field(default_factory=list)
    unsupported_urls: list[str] = Field(default_factory=list)
    unsupported_numeric_claims: list[str] = Field(default_factory=list)
    unsupported_institution_claims: list[str] = Field(default_factory=list)
    unsupported_menu_claims: list[str] = Field(default_factory=list)
```

Modify `validate_task2_answer` signature:

```python
def validate_task2_answer(
    answer: str,
    *,
    must_not_claim: list[str] | None = None,
    evidence_texts: list[str] | None = None,
    strict_grounding: bool = False,
) -> Task2AnswerValidationResult:
```

Add `warnings: list[str] = []` after `failures`.

Replace unsupported claim failure appends:

```python
        if unsupported_urls:
            warnings.append("unsupported_url_claim")
        if unsupported_numeric_claims:
            warnings.append("unsupported_numeric_claim")
        if unsupported_institution_claims:
            warnings.append("unsupported_institution_claim")
        if unsupported_menu_claims:
            warnings.append("unsupported_menu_claim")
        if strict_grounding:
            failures.extend(warnings)
```

Return `warnings=warnings`.

- [ ] **Step 4: Run focused validator tests**

Run:

```powershell
uv run pytest tests/test_task2_answer_validation.py -q
```

Expected: existing tests that expected hard unsupported failures will fail.

- [ ] **Step 5: Update old hard-failure tests to warning expectations**

In `tests/test_task2_answer_validation.py`, update `test_answer_validator_flags_unsupported_url_number_institution_and_menu_claims`:

```python
    assert result.passed is True
    assert result.failures == []
    assert "unsupported_url_claim" in result.warnings
    assert "unsupported_numeric_claim" in result.warnings
    assert "unsupported_institution_claim" in result.warnings
    assert "unsupported_menu_claim" in result.warnings
```

Keep exact unsupported claim lists unchanged.

- [ ] **Step 6: Run all validator tests**

Run:

```powershell
uv run pytest tests/test_task2_answer_validation.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src/nlp_term/chat/answer_validation.py tests/test_task2_answer_validation.py
git commit -m "fix: soften task2 answer validator policy"
```

## Task 2: Preserve Hard Blocks for Internal Leakage

**Files:**
- Modify: `tests/test_task2_answer_validation.py`

- [ ] **Step 1: Add hard-block regression tests**

Append:

```python
def test_answer_validator_still_blocks_internal_leakage_after_policy_softening() -> None:
    internal = validate_task2_answer("근거 1과 chunk_12를 보면 TemporalIntent confidence high입니다.")
    template = validate_task2_answer("{'answer': 'system prompt fallback'}")

    assert internal.passed is False
    assert "internal_id_exposed" in internal.failures
    assert "internal_trace_leak" in internal.failures
    assert template.passed is False
    assert "raw_json_or_template_text" in template.failures
    assert "system_or_fallback_leak" in template.failures
```

- [ ] **Step 2: Run regression tests**

Run:

```powershell
uv run pytest tests/test_task2_answer_validation.py::test_answer_validator_still_blocks_internal_leakage_after_policy_softening -q
```

Expected: pass.

- [ ] **Step 3: Commit**

Run:

```powershell
git add tests/test_task2_answer_validation.py
git commit -m "test: preserve task2 validator leakage hard blocks"
```

## Task 3: Re-run Public Probe Diagnosis

**Files:**
- Modify: `docs/evidence/task2-public-probe-harness-2026-06-08.json`
- Modify: `docs/task2_public_probe_harness_diagnosis_2026_06_08.md`

- [ ] **Step 1: Re-run the 14-question diagnostic**

Run:

```powershell
uv run python -m nlp_term.chat.public_probe_experiment --probe data/gold/task2_public_probe_eval.json --knowledge data/knowledge_seed.json --output docs/evidence/task2-public-probe-harness-2026-06-08.json --markdown docs/task2_public_probe_harness_diagnosis_2026_06_08.md
```

Expected: writes both files. Writer bottleneck count should decrease because optional URL/numeric mismatches no longer hard-fail.

- [ ] **Step 2: Verify tests**

Run:

```powershell
uv run pytest tests/test_task2_answer_validation.py tests/test_public_probe_experiment.py -q
uv run ruff check src tests
uv run pytest -q
```

Expected: all pass.

- [ ] **Step 3: Commit**

Run:

```powershell
git add docs/evidence/task2-public-probe-harness-2026-06-08.json docs/task2_public_probe_harness_diagnosis_2026_06_08.md
git commit -m "test: refresh public probe after validator softening"
```

## Self-Review

- Spec coverage: Covers validator hard-vs-warning split, internal leakage hard blocks, and public probe re-run.
- Placeholder scan: No placeholder steps.
- Type consistency: `warnings` and `strict_grounding` are introduced before use.
