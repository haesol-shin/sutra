# Data Model Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the source-backed data, retrieval, baseline classifier, and model-decision scaffolding needed before final Task 1/2 experiments.

**Architecture:** Keep `src/classifier.ipynb` and `chatbot.sh` as the only grading entrypoints. Add middle-pipeline modules under `src/nlp_term/prepare`, `src/nlp_term/retrieve`, and `src/nlp_term/classify` while preserving deterministic fallback behavior.

**Tech Stack:** Python 3.10.12, uv, Pydantic, scikit-learn, Gradio.

---

### Task 1: Commit Current Skeleton

**Files:**
- Already committed in `129ed3a feat: add submission skeleton and validators`

- [x] Commit grading skeleton and validators.

### Task 2: Schema And Dataset Contracts

**Files:**
- Modify: `src/nlp_term/schemas.py`
- Modify: `src/nlp_term/validators.py`

- [x] Add label audit, QA example, retrieved doc, and model candidate schemas.
- [x] Validate seed data, source probe metadata, and model shortlist metadata.

### Task 3: Source Collection

**Files:**
- Modify: `src/nlp_term/collect/base.py`
- Modify: `src/nlp_term/collect/*.py`
- Modify: `src/nlp_term/collect/run_collect.py`
- Create: `docs/source_inventory.md`

- [x] Add `fetch_source()` that writes raw snapshots and checksum over fetched bytes.
- [x] Keep stub mode for deterministic local probe.
- [x] Add `--fetch` mode for real source snapshot checks.

### Task 4: Seed Knowledge And Dataset Generation

**Files:**
- Create: `src/nlp_term/prepare/knowledge.py`
- Create: `src/nlp_term/prepare/cls_data.py`
- Create: `src/nlp_term/prepare/qa_data.py`
- Create: `src/nlp_term/prepare/build_all.py`

- [x] Generate seed `KnowledgeDoc` rows for labels 0-4.
- [x] Generate self-consistency audit metadata for classification seed rows.
- [x] Generate source-linked QA seed rows.

### Task 5: Retrieval

**Files:**
- Create: `src/nlp_term/retrieve/rank.py`
- Modify: `src/nlp_term/chat/composer.py`

- [x] Add deterministic lexical ranking over seed `KnowledgeDoc`s.
- [x] Attach source candidate evidence to deterministic chat answers.

### Task 6: Task 1 Baseline

**Files:**
- Create: `src/nlp_term/classify/features.py`
- Create: `src/nlp_term/classify/evaluate.py`
- Create: `src/nlp_term/classify/train.py`
- Modify: `src/nlp_term/classify/predict.py`

- [x] Train TF-IDF + Logistic Regression baseline on seed data.
- [x] Load `model/classifier.joblib` when present and fall back to keyword routing when absent.

### Task 7: Task 2/3 Model Shortlist

**Files:**
- Create: `data/model_shortlist.json`
- Create: `docs/model_decisions.md`

- [x] Record primary, candidate, reference, and cut model options.
- [x] Enforce 9B parameter limit for primary/candidate models.

### Task 8: Verification

**Files:**
- No new files.

- [ ] Run import, seed, source, model shortlist, notebook, chatbot, ruff, and compile checks.
- [ ] Run critic loop after verification and fix only concrete blockers.
