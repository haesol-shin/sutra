# Source Adapter And Structured Row Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement only the shared structured-row contract and the dining vertical slice so Task 2 RAG and future deterministic Task 3 tool-use can share the same evidence format.

**Architecture:** Structured rows are created from existing `SourceSpec + RawSource + SourceVerification` objects. Rows are the source of truth for both static `KnowledgeDoc` generation and future dynamic tool results. The first implementation slice is deliberately limited to base rows, dining rows, and the adapter protocol.

**Tech Stack:** Python 3.10.12, uv, Pydantic, BeautifulSoup/lxml, existing `RawSource`/`SourceVerification`/`KnowledgeDoc` schemas, pytest.

---

## Scope

Implement A+B only:

- Work Unit A: `BaseStructuredRow`, `DiningRow`, and `SourceAdapter`.
- Work Unit B: dining adapter over `data/raw/dining/cnu_mobile_food.html`.

Do not implement calendar, shuttle, graduation, or notice adapters in this pass.

Do not modify:

- Qwen prompts.
- retrieval/reranking logic.
- source inventory promotion flags.
- dynamic Task 3 runtime.

## Critical Constraints From Review

Architect status: `WATCH`.

Critic status: `REQUEST CHANGES`, now incorporated into this revised plan.

Required constraints:

- `BaseStructuredRow` provenance must be derived from `SourceSpec + RawSource + SourceVerification`, not arbitrary caller-provided values.
- Work Unit A finalizes only base and dining contracts.
- `row_id` must be deterministic and must not depend on `fetched_at`.
- `to_knowledge_docs()` must write structured metadata under `metadata["structured"]` and compatibility aliases used by existing harness/sufficiency code.
- `cnu_mobile_food` is `official_linked`, not `official_chain_ok`. Current/latest dining answers must remain fail-closed unless a later source-promotion review changes that status.

## Provisional Future Schemas

These are not implemented in this pass:

- Calendar rows.
- Shuttle rows.
- Graduation rows.
- Notice rows.

They remain design notes until their own adapter slices. This prevents premature schema churn before dining proves the shared contract.

## Work Unit A: Structured Contract

**Files:**

- Create: `src/nlp_term/structured/__init__.py`
- Create: `src/nlp_term/structured/rows.py`
- Create: `src/nlp_term/structured/adapters.py`
- Create: `tests/test_structured_row_contract.py`

- [ ] **Step 1: Write contract tests**

Create tests that require:

- rows are constructed from `SourceSpec + RawSource + SourceVerification`;
- provenance fields mirror those objects;
- missing or disconnected provenance cannot silently pass;
- `row_id` is stable when only `fetched_at` changes;
- `to_knowledge_docs()` exposes `metadata["structured"]` and compatibility aliases.

Run:

```powershell
uv run pytest tests/test_structured_row_contract.py -q
```

Expected: fail because the structured package does not exist yet.

- [ ] **Step 2: Implement base row models**

Create `src/nlp_term/structured/rows.py` with:

- `BaseStructuredRow`
- `DiningRow`
- helper constructor that takes `SourceSpec`, `RawSource`, and `SourceVerification`

Required derived fields:

```text
source_id
source_url
label
domain
raw_path
raw_checksum
raw_fetched_at
parser_name
parser_version
verification_official_chain_ok
freshness_policy
row_id
row_type
evidence_text
```

Dining fields:

```text
meal_date
cafeteria
meal_type
user_type
menu_name
price
menu_items
is_closed
closed_reason
```

Deterministic dining row id rule:

```text
source_id | row_type | meal_date | cafeteria | meal_type | user_type | ordinal_or_menu_key
```

Do not include `fetched_at`.

- [ ] **Step 3: Implement adapter protocol**

Create `src/nlp_term/structured/adapters.py`.

The adapter protocol must make the provenance context explicit:

```python
class SourceAdapter(Protocol):
    source_id: str

    def parse(
        self,
        *,
        spec: SourceSpec,
        raw: RawSource,
        verification: SourceVerification,
    ) -> list[BaseStructuredRow]: ...

    def to_knowledge_docs(self, rows: list[BaseStructuredRow]) -> list[KnowledgeDoc]: ...
```

- [ ] **Step 4: Define metadata contract**

`to_knowledge_docs()` must write:

```python
metadata["structured"] = row_domain_fields
```

Compatibility aliases:

```text
menu_date
location
cafeteria
meal_type
user_type
structured_fields
raw_path
raw_checksum
raw_fetched_at
verification_official_chain_ok
verification_parser_name
verification_parser_version
source_freshness_policy
```

- [ ] **Step 5: Verify and commit**

Run:

```powershell
uv run pytest tests/test_structured_row_contract.py -q
```

Commit:

```powershell
git add src/nlp_term/structured tests/test_structured_row_contract.py
git commit -m "feat: define structured dining row contract"
```

## Work Unit B: Dining Adapter Vertical Slice

**Files:**

- Create: `src/nlp_term/structured/dining.py`
- Create: `tests/test_dining_adapter.py`
- Generate only if useful: `data/structured/dining_rows.json`

- [ ] **Step 1: Write dining adapter tests**

Tests must verify:

- parsing saved raw `data/raw/dining/cnu_mobile_food.html`;
- at least one row for the available menu date;
- cafeteria columns include 제1학생회관 and 제2학생회관 when present;
- 조식/중식/석식 are preserved;
- 직원/학생 user types are preserved;
- `운영안함` is represented as `is_closed=True`;
- price is parsed from strings like `정식(6000)`;
- re-parsing the same raw with a different `fetched_at` keeps the same `row_id`s`;
- generated `KnowledgeDoc` rows contain the metadata aliases from Work Unit A.

Run:

```powershell
uv run pytest tests/test_dining_adapter.py -q
```

Expected: fail because dining adapter does not exist yet.

- [ ] **Step 2: Implement dining parser**

Create `src/nlp_term/structured/dining.py`.

Parser rules:

- Use DOM/table position, not flattened text.
- Extract the active date from the raw page text.
- Use table header cells as cafeteria names.
- Use rowspans/row order to keep meal type with user type.
- Treat `운영안함` as a closed row.
- Preserve source provenance from `SourceSpec + RawSource + SourceVerification`.

- [ ] **Step 3: Implement dining knowledge docs**

Generate natural-language `KnowledgeDoc.body` from each row.

Closed row example:

```text
2026-06-08 제2학생회관 조식 학생 식단은 운영안함입니다.
```

Open row example:

```text
2026-06-08 제1학생회관 중식 학생 정식(4500): 김치볶음밥, 누드소세지, 맑은우동국물, 마카로니샐러드, 베이비슈, 단무지.
```

Do not mark the source as official-chain verified. Preserve `verification_official_chain_ok=False` unless the source inventory is reviewed later.

- [ ] **Step 4: Add freshness and official-chain gate**

Because `cnu_mobile_food` is `official_linked` but not `official_chain_ok`, this slice must not enable current/latest dining answers by itself.

Acceptance:

- structured rows can be generated;
- static review can inspect the rows;
- current/latest dining claims remain fail-closed in existing harness tests.

- [ ] **Step 5: Verify regression safety**

Run:

```powershell
uv run pytest tests/test_structured_row_contract.py tests/test_dining_adapter.py tests/test_phase_a_harness_contract.py tests/test_public_probe_experiment.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

Commit:

```powershell
git add src/nlp_term/structured tests/test_structured_row_contract.py tests/test_dining_adapter.py data/structured/dining_rows.json
git commit -m "feat: add structured dining adapter"
```

If `data/structured/dining_rows.json` is not generated, omit it from `git add`.

## Acceptance Gates

- Work Unit A tests pass.
- Work Unit B tests pass.
- Existing harness/public-probe safety tests pass.
- No calendar/shuttle/graduation/notice adapters are implemented.
- No source promotion is performed.
- No current/latest dining answer path is enabled from `cnu_mobile_food`.

Required verification command:

```powershell
uv run pytest tests/test_structured_row_contract.py tests/test_dining_adapter.py tests/test_phase_a_harness_contract.py tests/test_public_probe_experiment.py -q
```

## Stop Condition

Stop after A+B pass and commit.

Do not proceed to:

- calendar adapter,
- shuttle adapter,
- graduation adapter,
- notice adapter,
- source promotion,
- Qwen prompt tuning,
- retrieval changes,
- Task 3 dynamic runtime integration.

## Self-Review

- Spec coverage: The plan covers the shared RAG/tool-use evidence contract and the first dining slice.
- Scope control: It removes premature calendar/shuttle/graduation/notice implementation.
- Provenance safety: Rows derive from existing source registry/probe/verification objects.
- Freshness safety: Dining current/latest answers remain blocked until explicit source promotion review.
- Generalization: The contract is reusable, but only dining is implemented now to reduce schema churn.
