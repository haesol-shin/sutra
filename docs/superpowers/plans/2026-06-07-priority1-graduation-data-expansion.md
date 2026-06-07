# Priority 1 Graduation Data Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the source-backed graduation/curriculum dataset before further RAG, reranking, or prompt-quality tuning.

**Architecture:** Keep the pipeline source-backed and serial-first. Fetch raw official snapshots, parse them into clean `KnowledgeDoc` rows with department/year/parser metadata, regenerate deterministic Task 1/Task 2 seed rows, then rerun diagnostics without claiming final performance.

**Tech Stack:** Python 3.10.12, uv, pydantic, requests, PyMuPDF via existing document parser, olefile/HWP path where available, pytest, ruff, existing `nlp_term.collect`, `nlp_term.prepare`, `nlp_term.validators`, `nlp_term.retrieve`, and `nlp_term.chat` modules.

---

## Existing Planning Context

This plan does not start from zero. It narrows these existing documents into one executable unit:

- `docs/next_data_expansion_priorities.md`: says Priority 1 is graduation requirements, curriculum, PDF/HWP, representative departments, and year differences.
- `docs/task2_claim_guard_notes.md`: records the completed 0.5 guardrail; do not keep tuning prompts before source expansion.
- `docs/synthetic_data_protocol.md`: separates seed, synthetic, human gold, and Task 2 gold; do not use generated seed metrics as final performance claims.
- `docs/data_expansion_goal_plan.md`: broader long-term data/RAG plan; this file covers only the next Priority 1 slice.

Current repo baseline measured before this plan:

- `data/knowledge_seed.json`: 53 docs total.
- label 0 graduation docs: 27 docs.
- label 0 departments in metadata: `생화학과`, `영어영문학과`.
- label 0 curriculum years in metadata: `2025`.
- `data/cls_train_seed.json`: 1,346 rows.
- `data/qa_seed.json`: 50 rows.
- `data/gold/task2_fact_gold.json`: 25 rows, 5 per label.

External source candidates found during planning and still requiring fetch verification before activation:

- Central curriculum guide page: `https://plus.cnu.ac.kr/html/kr/sub05/sub05_051201.html`
- 2025 curriculum PDF: `https://plus.cnu.ac.kr/html/kr/25file/2025_book.pdf`
- 2024 curriculum PDF: `https://plus.cnu.ac.kr/html/kr/24file/2024_book.pdf`
- 2023 curriculum PDF: `https://plus.cnu.ac.kr/html/kr/23file/2023_book.pdf`
- Biochemistry graduation requirements: `https://biochemistry.cnu.ac.kr/biochemistry/info/requirements.do`
- English graduation requirements: `https://english.cnu.ac.kr/english/edu/undergraduate02.do`
- Energy Engineering graduation requirements: `https://energy.cnu.ac.kr/energy/department/graduate.do`
- Horticulture academic counseling page with graduation table: `https://horti.cnu.ac.kr/horti/college/college04.do`
- Smart City Architectural Engineering graduation requirements: `https://smartarchi-eng.cnu.ac.kr/smartarchi-eng/department/condition.do`

Do not assume every candidate will parse cleanly. The plan intentionally starts with verification and failure logging.

## Acceptance Criteria

- Source inventory contains an active Priority 1 graduation slice with at least 5 representative departments.
- Source inventory contains at least 3 curriculum years for central curriculum PDFs or equivalent official curriculum documents.
- Raw snapshots are fetched with checksums and 2xx status for every active Priority 1 source.
- PDF/HWP/HWPX/HTML parser output has no mojibake/private-use glyph scan hits in accepted `KnowledgeDoc` rows.
- Every graduation/curriculum `KnowledgeDoc` has applicable `source_department`, `source_curriculum_year`, and `source_parser_type` metadata.
- `data/knowledge_seed.json` has at least 75 docs total and at least 45 label 0 docs after regeneration.
- label 0 metadata contains at least 5 departments and at least 3 curriculum years.
- Add at least 25 new source-backed Task 1 gold-like questions to a review queue, not directly to human gold.
- Add at least 25 new Task 2 fact candidates to a review queue, not directly to Task 2 gold.
- Rerun Task 1 classifier, retrieval diagnostics, and Task 2 vertical slice as diagnostics only.
- No final Task 1 or Task 2 performance claim is made from seed/synthetic data.

## File Structure

- Modify `src/nlp_term/collect/source_inventory.py`
  - Add active Priority 1 sources only after verification tests define the coverage contract.
  - Keep inactive candidates inactive unless they pass fetch and parser checks.

- Modify `src/nlp_term/collect/run_collect.py` only if stage filtering or Priority 1 tagging is missing.
  - It already writes source probe rows; prefer extending metadata rather than adding a new collector.

- Modify `src/nlp_term/prepare/from_sources.py`
  - Preserve department/year/parser metadata.
  - Add parser-specific failure reasons when PDF/HWP/HWPX extraction fails.
  - Keep chunk ranking deterministic and source-backed.

- Modify `src/nlp_term/validators.py`
  - Add explicit graduation coverage gates: minimum graduation departments, minimum curriculum years, minimum label 0 docs, parser metadata required.
  - Keep existing source probe, knowledge quality, dataset quality, and metric claim gates.

- Create `src/nlp_term/prepare/graduation_review_queue.py`
  - Build source-backed Task 1 question candidates and Task 2 fact candidates for human review.
  - Do not write directly to `data/gold`.

- Create `tests/test_graduation_data_expansion_plan.py`
  - Contract tests for graduation coverage gates and review queue artifact shape.

- Create or update `docs/evidence/priority1-graduation-data-expansion-2026-06-07.json`
  - Record commands, checksums, row counts, failures, and diagnostic metrics.

- Update `docs/data_expansion_progress.md`
  - Append progress notes after each committed stage.

---

### Task 1: Add Priority 1 Coverage Gates

**Files:**
- Modify: `src/nlp_term/validators.py`
- Test: `tests/test_graduation_data_expansion_plan.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nlp_term.validators import validate_graduation_coverage


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _doc(doc_id: str, *, department: str | None, year: str | None, parser_type: str = "html") -> dict[str, object]:
    metadata: dict[str, object] = {
        "generation_method": "source_parse",
        "source_parser_type": parser_type,
    }
    if department:
        metadata["source_department"] = department
    if year:
        metadata["source_curriculum_year"] = year
    return {
        "doc_id": doc_id,
        "label": 0,
        "domain": "graduation",
        "title": f"{department or year} 졸업요건",
        "body": "졸업요건은 전공, 교양, 교육과정, 학점 이수 기준을 확인해야 한다.",
        "source_url": "https://plus.cnu.ac.kr",
        "source_id": doc_id.rsplit("_", 1)[0],
        "metadata": metadata,
    }


def test_graduation_coverage_passes_with_departments_years_and_parser_metadata(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge_seed.json"
    rows = [
        _doc("bio_1", department="생화학과", year=None),
        _doc("eng_1", department="영어영문학과", year=None),
        _doc("energy_1", department="에너지공학과", year=None),
        _doc("horti_1", department="원예학과", year=None),
        _doc("archi_1", department="스마트시티건축공학과", year=None),
        _doc("curriculum_2023_1", department=None, year="2023", parser_type="pdf"),
        _doc("curriculum_2024_1", department=None, year="2024", parser_type="pdf"),
        _doc("curriculum_2025_1", department=None, year="2025", parser_type="pdf"),
    ]
    _write_json(knowledge_path, rows)

    report = validate_graduation_coverage(
        knowledge_path,
        min_label0_docs=8,
        min_departments=5,
        min_curriculum_years=3,
        require_parser_metadata=True,
    )

    assert report["label0_doc_count"] == 8
    assert report["department_count"] == 5
    assert report["curriculum_year_count"] == 3


def test_graduation_coverage_rejects_missing_curriculum_years(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge_seed.json"
    rows = [
        _doc("bio_1", department="생화학과", year=None),
        _doc("eng_1", department="영어영문학과", year=None),
        _doc("energy_1", department="에너지공학과", year=None),
        _doc("horti_1", department="원예학과", year=None),
        _doc("archi_1", department="스마트시티건축공학과", year=None),
        _doc("curriculum_2025_1", department=None, year="2025", parser_type="pdf"),
    ]
    _write_json(knowledge_path, rows)

    with pytest.raises(ValueError, match="curriculum years"):
        validate_graduation_coverage(
            knowledge_path,
            min_label0_docs=6,
            min_departments=5,
            min_curriculum_years=3,
            require_parser_metadata=True,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/test_graduation_data_expansion_plan.py -v
```

Expected:

```text
ImportError: cannot import name 'validate_graduation_coverage'
```

- [ ] **Step 3: Write minimal implementation**

Add `validate_graduation_coverage(path, min_label0_docs, min_departments, min_curriculum_years, require_parser_metadata)` to `src/nlp_term/validators.py`.

Implementation rules:

- load `KnowledgeDoc` rows with `validate_rows`.
- filter `doc.label == 0`.
- count `metadata["source_department"]`.
- count `metadata["source_curriculum_year"]`.
- reject missing `source_parser_type` when `require_parser_metadata=True`.
- return a dict with `label0_doc_count`, `departments`, `department_count`, `curriculum_years`, `curriculum_year_count`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
uv run pytest tests/test_graduation_data_expansion_plan.py -v
uv run ruff check src tests
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit**

```powershell
git add src/nlp_term/validators.py tests/test_graduation_data_expansion_plan.py
git commit -m "test: add graduation coverage gates"
```

---

### Task 2: Activate A Verified Priority 1 Source Slice

**Files:**
- Modify: `src/nlp_term/collect/source_inventory.py`
- Modify if needed: `docs/source_inventory.md`
- Test: `tests/test_graduation_data_expansion_plan.py`

- [ ] **Step 1: Add a failing source inventory test**

Append this test to `tests/test_graduation_data_expansion_plan.py`:

```python
from nlp_term.collect.source_inventory import iter_specs


def test_priority1_active_inventory_has_five_departments_and_three_curriculum_years() -> None:
    specs = [
        spec for spec in iter_specs(stage="all", active_only=True)
        if spec.label == 0 and spec.domain == "graduation"
    ]
    departments = {spec.department for spec in specs if spec.department}
    years = {spec.curriculum_year for spec in specs if spec.curriculum_year}
    parser_types = {spec.parser_type for spec in specs}

    assert len(departments) >= 5
    assert len(years) >= 3
    assert {"html", "pdf"} <= parser_types
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/test_graduation_data_expansion_plan.py::test_priority1_active_inventory_has_five_departments_and_three_curriculum_years -v
```

Expected: fails because current active inventory has only 2 departments and 1 curriculum year.

- [ ] **Step 3: Update `source_inventory.py` minimally**

Activate or add only Priority 1 graduation sources that pass URL review:

```python
SourceSpec(
    source_id="graduation_energy_requirements",
    label=0,
    domain="graduation",
    url="https://energy.cnu.ac.kr/energy/department/graduate.do",
    parser_type="html",
    stage="stage1",
    active=True,
    priority=10,
    official_chain_ok=True,
    notes="Energy Engineering graduation requirements",
    department="에너지공학과",
)
```

Add equivalent active specs for:

- `graduation_horticulture_counsel`, department `원예학과`, URL `https://horti.cnu.ac.kr/horti/college/college04.do`
- `graduation_smartarchi_requirements`, department `스마트시티건축공학과`, URL `https://smartarchi-eng.cnu.ac.kr/smartarchi-eng/department/condition.do`
- `graduation_curriculum_2024_pdf`, year `2024`, URL `https://plus.cnu.ac.kr/html/kr/24file/2024_book.pdf`
- `graduation_curriculum_2023_pdf`, year `2023`, URL `https://plus.cnu.ac.kr/html/kr/23file/2023_book.pdf`

Keep `graduation_curriculum_pdf` as the existing 2025 source.

- [ ] **Step 4: Run inventory tests**

Run:

```powershell
uv run pytest tests/test_graduation_data_expansion_plan.py -v
uv run python -m nlp_term.validators --source-inventory --min-stage1-candidates 5
uv run ruff check src tests
```

Expected: tests pass. If `--source-inventory` rejects inactive `official_chain_ok=True`, update inactive candidate flags rather than weakening the validator.

- [ ] **Step 5: Commit**

```powershell
git add src/nlp_term/collect/source_inventory.py docs/source_inventory.md tests/test_graduation_data_expansion_plan.py
git commit -m "feat: expand graduation source inventory"
```

---

### Task 3: Fetch And Validate Raw Priority 1 Sources

**Files:**
- Modify only if needed: `src/nlp_term/collect/run_collect.py`
- Generated: `data/sources/source_probe.json`
- Generated: `data/raw/graduation/*`
- Docs: `docs/data_expansion_failure_log.md`

- [ ] **Step 1: Run source collection with fetch**

Run:

```powershell
uv run python -m nlp_term.collect.run_collect --stage all --fetch --output data/sources/source_probe.json
```

Expected:

```text
wrote ... source probe rows
```

If `run_collect` does not support `--stage all`, first add a failing CLI test that asserts `--stage all` is accepted, then implement the parser option by reusing `iter_specs(stage=args.stage, active_only=...)`.

- [ ] **Step 2: Validate raw files**

Run:

```powershell
uv run python -m nlp_term.validators --source-probe data/sources/source_probe.json --require-raw-files --require-official-chain-evidence
```

Expected:

```text
validation-ok
```

- [ ] **Step 3: Handle failed fetches without hiding them**

If any active source fails:

1. append a record to `docs/data_expansion_failure_log.md` with source id, URL, status/error, and next action.
2. either fix the URL from an official CNU page or mark the source inactive.
3. rerun Step 1 and Step 2.

Do not keep a failing active source.

- [ ] **Step 4: Commit**

```powershell
git add data/sources/source_probe.json data/raw/graduation docs/data_expansion_failure_log.md
git commit -m "docs: record priority1 raw source snapshots"
```

---

### Task 4: Parse Priority 1 Sources Into Knowledge

**Files:**
- Modify: `src/nlp_term/prepare/from_sources.py`
- Generated: `data/knowledge_seed.json`
- Generated: `data/source_parse_failures.json`
- Test: `tests/test_graduation_data_expansion_plan.py`

- [ ] **Step 1: Add parser metadata regression test**

Append this test:

```python
from nlp_term.schemas import KnowledgeDoc, RawSource, SourceVerification
from nlp_term.prepare.from_sources import build_knowledge_from_probe


def test_source_parse_preserves_graduation_department_year_and_parser_metadata(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "graduation" / "sample.html"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text("졸업요건 전공 교양 교육과정 학점 이수 기준을 확인한다." * 5, encoding="utf-8")
    probe_path = tmp_path / "probe.json"
    raw = RawSource(
        source_id="graduation_sample",
        label=0,
        domain="graduation",
        url="https://example.cnu.ac.kr/grad",
        fetched_at="2026-06-07T00:00:00+09:00",
        content_type="text/html",
        raw_path=str(raw_path),
        status_code=200,
        checksum="dummy",
    )
    verification = SourceVerification(
        source_id="graduation_sample",
        official_chain_ok=True,
        parser_name="html_stage_inventory",
        parser_version="test",
        evidence=["https://example.cnu.ac.kr/grad"],
        warnings=[],
        verified_at="2026-06-07T00:00:00+09:00",
    )
    _write_json(
        probe_path,
        [
            {
                "raw": raw.model_dump(),
                "verification": verification.model_dump(),
                "inventory": {
                    "stage": "stage1",
                    "active": True,
                    "parser_type": "html",
                    "department": "예시학과",
                    "curriculum_year": "2025",
                },
            }
        ],
    )

    docs, failures = build_knowledge_from_probe(probe_path, chunks_per_source=1)

    assert failures == []
    doc = KnowledgeDoc.model_validate(docs[0])
    assert doc.metadata["source_department"] == "예시학과"
    assert doc.metadata["source_curriculum_year"] == "2025"
    assert doc.metadata["source_parser_type"] == "html"
```

- [ ] **Step 2: Run parser regression test**

Run:

```powershell
uv run pytest tests/test_graduation_data_expansion_plan.py -v
```

Expected: pass if metadata is already preserved; fail if path handling or metadata propagation regressed.

- [ ] **Step 3: Regenerate knowledge from fetched sources**

Run:

```powershell
uv run python -m nlp_term.prepare.from_sources --source-probe data/sources/source_probe.json --output data/knowledge_seed.json --failures-output data/source_parse_failures.json --chunks-per-source 9
```

Expected:

```text
wrote ... knowledge docs to data\knowledge_seed.json
```

- [ ] **Step 4: Validate knowledge and graduation coverage**

Run:

```powershell
uv run python -m nlp_term.validators --knowledge-quality data/knowledge_seed.json --source-probe data/sources/source_probe.json --min-total-docs 75 --min-docs-per-label 1 --min-body-chars 80 --min-source-parse-ratio 0.9
uv run python -c "from pathlib import Path; from nlp_term.validators import validate_graduation_coverage; print(validate_graduation_coverage(Path('data/knowledge_seed.json'), min_label0_docs=45, min_departments=5, min_curriculum_years=3, require_parser_metadata=True))"
```

Expected: both commands pass. If `data/source_parse_failures.json` is not empty, log every failure and either repair parser behavior or deactivate the failing source.

- [ ] **Step 5: Commit**

```powershell
git add src/nlp_term/prepare/from_sources.py tests/test_graduation_data_expansion_plan.py data/knowledge_seed.json data/source_parse_failures.json docs/data_expansion_failure_log.md
git commit -m "feat: parse expanded graduation sources"
```

---

### Task 5: Build Graduation Review Queues

**Files:**
- Create: `src/nlp_term/prepare/graduation_review_queue.py`
- Generated: `data/review/task1_graduation_questions.json`
- Generated: `data/review/task2_graduation_facts.json`
- Test: `tests/test_graduation_data_expansion_plan.py`

- [ ] **Step 1: Add failing review queue test**

Append this test:

```python
from nlp_term.prepare.graduation_review_queue import build_graduation_review_queues


def test_graduation_review_queue_builds_source_backed_task1_and_task2_candidates() -> None:
    docs = [
        KnowledgeDoc(
            doc_id="graduation_energy_1",
            label=0,
            domain="graduation",
            title="에너지공학과 졸업요건",
            body="에너지공학과 졸업요건은 130학점 이상, 입학연도별 교육과정 이수, 졸업논문 심사를 포함한다.",
            source_url="https://energy.cnu.ac.kr/energy/department/graduate.do",
            source_id="graduation_energy_requirements",
            metadata={
                "source_department": "에너지공학과",
                "source_parser_type": "html",
                "source_stage": "stage1",
            },
        )
    ]

    task1_rows, task2_rows = build_graduation_review_queues(docs, max_task1_per_doc=2, max_task2_per_doc=2)

    assert len(task1_rows) == 2
    assert len(task2_rows) == 2
    assert task1_rows[0]["label"] == 0
    assert task1_rows[0]["source_doc_id"] == "graduation_energy_1"
    assert task1_rows[0]["review_status"] == "needs_human_review"
    assert task2_rows[0]["source_doc_id"] == "graduation_energy_1"
    assert task2_rows[0]["source_url"] == "https://energy.cnu.ac.kr/energy/department/graduate.do"
    assert task2_rows[0]["answerable_scope"] == "static"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/test_graduation_data_expansion_plan.py::test_graduation_review_queue_builds_source_backed_task1_and_task2_candidates -v
```

Expected: import failure for `graduation_review_queue`.

- [ ] **Step 3: Implement deterministic review queue builder**

Implement:

- `build_graduation_review_queues(docs, max_task1_per_doc=2, max_task2_per_doc=2) -> tuple[list[dict], list[dict]]`
- Task 1 candidates include `question`, `label`, `source_doc_id`, `generation_method: "source_template"`, `review_status: "needs_human_review"`.
- Task 2 candidates include `fact_id`, `label`, `source_doc_id`, `source_url`, `claim`, `evidence_quote`, `answerable_scope: "static"`, `review_status: "needs_human_review"`.
- Extract evidence spans only from source body text; do not ask an LLM.
- Do not modify `data/gold` in this task.

- [ ] **Step 4: Add CLI and generate review queues**

Run:

```powershell
uv run python -m nlp_term.prepare.graduation_review_queue --knowledge data/knowledge_seed.json --task1-output data/review/task1_graduation_questions.json --task2-output data/review/task2_graduation_facts.json --min-task1-rows 25 --min-task2-rows 25
```

Expected:

```text
wrote ... task1 review candidates
wrote ... task2 review candidates
```

- [ ] **Step 5: Commit**

```powershell
git add src/nlp_term/prepare/graduation_review_queue.py tests/test_graduation_data_expansion_plan.py data/review/task1_graduation_questions.json data/review/task2_graduation_facts.json
git commit -m "feat: add graduation review queues"
```

---

### Task 6: Regenerate Seed Data And Diagnostics

**Files:**
- Generated: `data/cls_train_seed.json`
- Generated: `data/label_audit_seed.json`
- Generated: `data/qa_seed.json`
- Generated: `model/classifier_metrics.json`
- Generated: `model/retrieval_metrics.json`
- Generated: `docs/evidence/priority1-graduation-data-expansion-2026-06-07.json`

- [ ] **Step 1: Regenerate deterministic seed artifacts**

Run:

```powershell
uv run python -m nlp_term.prepare.build_all --output-dir data
```

Expected:

```text
wrote seed datasets to data
```

- [ ] **Step 2: Validate seed and dataset quality**

Run:

```powershell
uv run python -m nlp_term.validators --seed-data --data-dir data
uv run python -m nlp_term.validators --dataset-quality --data-dir data --min-cls-rows 1400 --min-cls-per-label 40 --min-ambiguous-per-label 5 --min-qa-rows 50 --min-qa-per-label 8 --no-dry-run --require-validated --require-qa-source
```

Expected: both commands print `validation-ok`.

- [ ] **Step 3: Re-train and validate Task 1 diagnostic classifier**

Run:

```powershell
uv run python -m nlp_term.classify.train --input data/cls_train_seed.json --model-output model/classifier.joblib --metrics-output model/classifier_metrics.json
uv run python -m nlp_term.validators --classifier-metrics model/classifier_metrics.json --input data/cls_train_seed.json --require-source-disjoint --min-macro-f1 0.70 --min-weighted-f1 0.70 --min-class-f1 0.55
```

Expected: training completes and validator passes. Report as source-disjoint seed diagnostic, not final heldout performance.

- [ ] **Step 4: Rerun retrieval diagnostics**

Run:

```powershell
uv run python -m nlp_term.retrieve.evaluate --knowledge data/knowledge_seed.json --qa data/qa_seed.json --output model/retrieval_metrics.json
uv run python -m nlp_term.validators --retrieval-metrics model/retrieval_metrics.json --knowledge data/knowledge_seed.json --qa data/qa_seed.json --require-metadata-aware --min-top1-label-accuracy 0.80 --min-top3-source-hit-rate 0.75
```

Expected: validator passes. If it fails, record the failure and inspect label 0 confusion before changing retrieval.

- [ ] **Step 5: Rerun Task 2 vertical slice diagnostic**

Only run this if `llama-server` is available locally. Do not fallback to deterministic answers.

```powershell
llama-server -m model\generator\Qwen3.5-9B-Q4_K_M.gguf -c 4096 -ngl auto --cache-type-k q8_0 --cache-type-v q8_0 --host 127.0.0.1 --port 18080 --reasoning off --reasoning-budget 0
uv run python -m nlp_term.chat.vertical_slice --gold data/gold/task2_answer_eval_gold.json --facts data/gold/task2_fact_gold.json --knowledge data/knowledge_seed.json --output model/metrics/task2_vertical_slice_priority1.json --llama-server-url http://127.0.0.1:18080 --limit 5
uv run python -c "from pathlib import Path; from nlp_term.validators import validate_metric_claim; validate_metric_claim(Path('model/metrics/task2_vertical_slice_priority1.json'), input_path=Path('data/gold/task2_answer_eval_gold.json'), require_dataset_origin='task2_gold', require_claim_level='qualitative_check'); print('metric claim ok')"
```

Expected: vertical slice writes an artifact and metric claim validation passes. If llama-server cannot run, write an evidence note that Task 2 generation was skipped due to unavailable local server; do not substitute another backend.

- [ ] **Step 6: Write evidence summary**

Create `docs/evidence/priority1-graduation-data-expansion-2026-06-07.json` with:

- input/output checksums for source probe, knowledge, cls seed, qa seed.
- source count, graduation department count, curriculum year count.
- parse failure count and source ids.
- review queue row counts.
- classifier metric summary.
- retrieval metric summary.
- Task 2 vertical slice status, if run.
- explicit statement: `final_performance_claim: false`.

- [ ] **Step 7: Commit**

```powershell
git add data/knowledge_seed.json data/cls_train_seed.json data/label_audit_seed.json data/qa_seed.json model/classifier_metrics.json model/retrieval_metrics.json model/metrics/task2_vertical_slice_priority1.json docs/evidence/priority1-graduation-data-expansion-2026-06-07.json
git commit -m "docs: record priority1 graduation diagnostics"
```

---

### Task 7: Update Progress And Handoff Notes

**Files:**
- Modify: `docs/data_expansion_progress.md`
- Modify: `docs/next_data_expansion_priorities.md`
- Optional: `docs/task2_claim_guard_notes.md`

- [ ] **Step 1: Update progress document**

Append:

```markdown
## Priority 1 Graduation Expansion

- status: completed / partial / blocked
- source inventory: N active graduation sources
- departments: [...]
- curriculum years: [...]
- knowledge docs: N total, N label 0
- review queues: N Task 1 candidates, N Task 2 candidates
- diagnostics:
  - classifier source-disjoint metric: ...
  - retrieval top1/top3: ...
  - Task 2 vertical slice: ...
- final performance claim: false
- next bottleneck: ...
```

- [ ] **Step 2: Mark next priority**

In `docs/next_data_expansion_priorities.md`, add a short note under Priority 1 stating whether it passed or what remains. Do not delete the original criteria.

- [ ] **Step 3: Verify documentation-only diff**

Run:

```powershell
git diff -- docs/data_expansion_progress.md docs/next_data_expansion_priorities.md
```

Expected: only progress/status text changed.

- [ ] **Step 4: Commit**

```powershell
git add docs/data_expansion_progress.md docs/next_data_expansion_priorities.md
git commit -m "docs: update priority1 data expansion progress"
```

---

## Stop Rules

Stop and open a 5-agent meeting if any of these happens:

- An active official source returns non-2xx after two URL repair attempts.
- PDF/HWP/HWPX parser emits mojibake/private-use glyphs in accepted chunks after two parser repairs.
- Graduation coverage passes by count but reviewer finds generic boilerplate chunks.
- Task 2 vertical slice starts failing mostly due to unsupported numeric/institution/menu claims.
- Retrieval top3 source hit drops below the previous stage after expansion.

Meeting roles:

- Data curator: source relevance and official-chain evidence.
- Parser engineer: PDF/HWP/HWPX extraction quality.
- Task 1 evaluator: classification boundary and generalization risk.
- Task 2 evaluator: retrieval-to-answer factuality and naturalness.
- Critic: rejects metric overclaims and hidden fallback.

## Self-Review

Spec coverage:

- Graduation/curriculum/PDF/HWP priority is covered by Tasks 2-4.
- Dataset expansion is covered by Tasks 5-6.
- Claim guard and no extra prompt tuning are respected by the scope and stop rules.
- Metrics are diagnostic only and bound to artifact checksums.

Placeholder scan:

- No task uses placeholder markers or unspecified behavior.
- Candidate sources are named explicitly, and every active source must pass fetch/parse validation.

Type consistency:

- `validate_graduation_coverage` is introduced in Task 1 before later command usage.
- `build_graduation_review_queues` is introduced in Task 5 before CLI generation.
- Artifact names remain consistent across tasks.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-07-priority1-graduation-data-expansion.md`.

Recommended execution mode:

1. Inline Execution for Tasks 1-2 to establish gates and inventory.
2. Serial execution for Task 3 source fetch because web/source failures need immediate inspection.
3. Inline or team execution for Tasks 4-7 once raw source snapshots are stable.

Do not execute this plan in parallel until Task 3 source fetch and parser failures are resolved.
