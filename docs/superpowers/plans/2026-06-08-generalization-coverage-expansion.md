# Generalization Coverage Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move from public-probe-specific fixes to a generalizable Task 2/3 coverage workflow with robustness probes, expanded structured sources, and measurable harness behavior.

**Architecture:** Keep the current deterministic harness structure. Add a separate robustness eval layer before expanding more rules, then expand source adapters and routing only when failures are backed by grouped evidence. LLM generation remains a writer step; temporal interpretation, source selection, freshness, and evidence sufficiency stay deterministic.

**Tech Stack:** Python 3.10.12, `uv`, pytest, ruff, existing `src/nlp_term/` package layout, existing structured row and harness contracts.

---

## Execution Order

Run these goals in order. Do not start a later goal until the current goal has a passing focused test suite and a committed result.

1. Goal A: Generalization probe set.
2. Goal B: Source coverage expansion.
3. Goal C: Harness generalization checks.
4. Goal D: Public probe rerun and diagnosis.

## Goal A: Generalization Probe Set

**Purpose:** Stop optimizing only against the 14 public probes. Create a separate robustness set that checks expression diversity for the same intent categories.

**Files:**
- Create: `data/gold/task2_generalization_probe.json`
- Create: `tests/test_task2_generalization_probe_contract.py`
- Modify: `docs/task2_public_probe_harness_diagnosis_2026_06_08.md`

- [ ] **Step A1: Write the probe schema test**

Create `tests/test_task2_generalization_probe_contract.py` with a test that loads `data/gold/task2_generalization_probe.json` and validates every row has:

```python
from __future__ import annotations

import json
from pathlib import Path


PROBE_PATH = Path("data/gold/task2_generalization_probe.json")
REQUIRED_IDS = {
    "latest_notice",
    "changed_since_notice",
    "future_dining",
    "current_dining",
    "shuttle_status",
    "graduation_versioned",
}


def test_generalization_probe_has_required_intent_groups() -> None:
    rows = json.loads(PROBE_PATH.read_text(encoding="utf-8"))
    groups = {row["group"] for row in rows}
    assert REQUIRED_IDS <= groups
    assert len(rows) >= 60
    assert all("question" in row for row in rows)
    assert all("expected_label" in row for row in rows)
    assert all("expected_temporal_type" in row for row in rows)
```

- [ ] **Step A2: Run the schema test and verify RED**

Run:

```powershell
uv run pytest tests\test_task2_generalization_probe_contract.py -q
```

Expected: FAIL because `data/gold/task2_generalization_probe.json` does not exist.

- [ ] **Step A3: Add the generalization probe JSON**

Create `data/gold/task2_generalization_probe.json` with at least 60 rows:

- 10 `latest_notice`
- 10 `changed_since_notice`
- 10 `future_dining`
- 10 `current_dining`
- 10 `shuttle_status`
- 10 `graduation_versioned`

Each row shape:

```json
{
  "id": "latest_notice_001",
  "group": "latest_notice",
  "question": "새로 올라온 학사 공지 있나요?",
  "expected_label": 1,
  "expected_domain": "notices",
  "expected_temporal_type": "latest_item"
}
```

- [ ] **Step A4: Run the schema test and verify GREEN**

Run:

```powershell
uv run pytest tests\test_task2_generalization_probe_contract.py -q
```

Expected: PASS.

- [ ] **Step A5: Document why this set exists**

Append a short section to `docs/task2_public_probe_harness_diagnosis_2026_06_08.md`:

```markdown
## Generalization Probe Policy

The 14 public probes are fixed regression probes, not the only optimization target. `data/gold/task2_generalization_probe.json` tracks expression coverage for latest notices, changed-since questions, dining date queries, shuttle status, and versioned graduation questions. Future router or source changes should improve both public probes and this robustness set.
```

- [ ] **Step A6: Commit**

Run:

```powershell
git add data\gold\task2_generalization_probe.json tests\test_task2_generalization_probe_contract.py docs\task2_public_probe_harness_diagnosis_2026_06_08.md
git commit -m "test: add task2 generalization probes"
```

## Goal B: Source Coverage Expansion

**Purpose:** Fix failures caused by missing data before adding more routing rules.

**Files:**
- Modify: `src/nlp_term/collect/source_inventory.py`
- Modify: `src/nlp_term/collect/dining.py`
- Modify: `src/nlp_term/structured/dining.py`
- Modify: `src/nlp_term/prepare/from_sources.py`
- Test: `tests/test_dining_adapter.py`
- Test: `tests/test_prepare_from_sources.py`

- [ ] **Step B1: Add a failing dining coverage test**

Extend `tests/test_dining_adapter.py` with a test requiring multiple dates when the raw source contains multiple day tabs or date-param snapshots:

```python
def test_dining_adapter_can_emit_multiple_menu_dates() -> None:
    # Use a fixture or existing raw snapshot set once collected.
    # Expected behavior: at least two distinct meal_date values.
    rows = DiningAdapter().parse(spec=spec, raw=raw, verification=verification)
    assert len({row.meal_date for row in rows}) >= 2
```

- [ ] **Step B2: Verify RED**

Run:

```powershell
uv run pytest tests\test_dining_adapter.py::test_dining_adapter_can_emit_multiple_menu_dates -q
```

Expected: FAIL until multi-date dining raw snapshots or parsing support exists.

- [ ] **Step B3: Expand dining collection**

Add a deterministic collection path that can store multiple dated snapshots under `data/raw/dining/`. Keep the adapter contract unchanged: it still emits `DiningRow` with `meal_date`, `cafeteria`, `meal_type`, and menu fields.

- [ ] **Step B4: Regenerate knowledge**

Run:

```powershell
uv run python -m nlp_term.prepare.from_sources --source-probe data\sources\source_probe.json --output data\knowledge_seed.json --failures-output data\source_parse_failures.json --chunks-per-source 9
```

Expected: `data/knowledge_seed.json` contains more `dining_menu` rows than before.

- [ ] **Step B5: Commit**

Run:

```powershell
git add src\nlp_term\collect\source_inventory.py src\nlp_term\collect\dining.py src\nlp_term\structured\dining.py src\nlp_term\prepare\from_sources.py tests\test_dining_adapter.py tests\test_prepare_from_sources.py data\knowledge_seed.json data\source_parse_failures.json
git commit -m "feat: expand dining source coverage"
```

## Goal C: Harness Generalization Checks

**Purpose:** Ensure routing rules are not only public-probe patches.

**Files:**
- Create or modify: `src/nlp_term/chat/generalization_probe_experiment.py`
- Modify: `src/nlp_term/chat/temporal_intent.py`
- Modify: `src/nlp_term/chat/orchestrator.py`
- Test: `tests/test_temporal_intent.py`
- Test: `tests/test_phase_a_harness_contract.py`

- [ ] **Step C1: Add temporal coverage tests from Goal A**

Add parameterized tests for:

- latest notice variants
- changed-since variants
- shuttle status variants
- future dining variants

Example:

```python
@pytest.mark.parametrize(
    "question",
    [
        "새로 올라온 학사 공지 있나요?",
        "최근 게시된 공지는 뭐예요?",
        "방금 등록된 공지사항 어디서 봐요?",
    ],
)
def test_latest_notice_variants_route_to_latest_item(question: str) -> None:
    intent = resolve_temporal_intent(question, route_domain="notices", reference_time=REFERENCE_TIME)
    assert intent.temporal_type == TemporalType.LATEST_ITEM
```

- [ ] **Step C2: Verify RED on at least one variant**

Run:

```powershell
uv run pytest tests\test_temporal_intent.py -q
```

Expected: at least one newly added variant fails.

- [ ] **Step C3: Generalize resolver rules minimally**

Update `src/nlp_term/chat/temporal_intent.py` by grouping cue sets by intent instead of adding one-off public probe phrases. Keep the implementation deterministic and traceable.

- [ ] **Step C4: Add generalization experiment runner**

Create `src/nlp_term/chat/generalization_probe_experiment.py` that loads `data/gold/task2_generalization_probe.json`, runs `answer_with_harness`, and writes:

- `docs/evidence/task2-generalization-probe-2026-06-08.json`
- `docs/task2_generalization_probe_diagnosis_2026_06_08.md`

- [ ] **Step C5: Commit**

Run:

```powershell
git add src\nlp_term\chat\generalization_probe_experiment.py src\nlp_term\chat\temporal_intent.py src\nlp_term\chat\orchestrator.py tests\test_temporal_intent.py tests\test_phase_a_harness_contract.py docs\evidence\task2-generalization-probe-2026-06-08.json docs\task2_generalization_probe_diagnosis_2026_06_08.md
git commit -m "test: measure task2 generalization probes"
```

## Goal D: Public Probe Rerun And Diagnosis

**Purpose:** Keep public probe results visible, but interpret them together with generalization probes.

**Files:**
- Modify: `docs/evidence/task2-public-probe-harness-2026-06-08.json`
- Modify: `docs/task2_public_probe_harness_diagnosis_2026_06_08.md`
- Modify: `docs/task2_generalization_probe_diagnosis_2026_06_08.md`

- [ ] **Step D1: Rerun public probe**

Run:

```powershell
uv run python -m nlp_term.chat.public_probe_experiment --probe data\gold\task2_public_probe_eval.json --knowledge data\knowledge_seed.json --output docs\evidence\task2-public-probe-harness-2026-06-08.json --markdown docs\task2_public_probe_harness_diagnosis_2026_06_08.md
```

- [ ] **Step D2: Rerun generalization probe**

Run:

```powershell
uv run python -m nlp_term.chat.generalization_probe_experiment --probe data\gold\task2_generalization_probe.json --knowledge data\knowledge_seed.json --output docs\evidence\task2-generalization-probe-2026-06-08.json --markdown docs\task2_generalization_probe_diagnosis_2026_06_08.md
```

- [ ] **Step D3: Full verification**

Run:

```powershell
uv run pytest -q
uv run ruff check src tests
```

Expected:

- pytest has zero failures.
- ruff reports `All checks passed!`.

- [ ] **Step D4: Commit**

Run:

```powershell
git add docs\evidence\task2-public-probe-harness-2026-06-08.json docs\task2_public_probe_harness_diagnosis_2026_06_08.md docs\evidence\task2-generalization-probe-2026-06-08.json docs\task2_generalization_probe_diagnosis_2026_06_08.md
git commit -m "test: rerun task2 public and generalization probes"
```

## Stop Condition

Stop this planning sequence after Goal D if:

- public probe and generalization probe both have fresh artifacts,
- failures are grouped by bottleneck,
- no new routing rule is added without a corresponding generalization probe group,
- full pytest and ruff pass.

At that point, decide whether the next work should be:

1. more source coverage,
2. embedding/hybrid retrieval,
3. Qwen prompt/writer quality,
4. Task 1 classifier retraining.
