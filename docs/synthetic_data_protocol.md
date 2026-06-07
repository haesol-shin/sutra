# Synthetic Data Protocol

작성일: 2026-06-07

## 목적

LLM-assisted 데이터 생성은 학습/개발 후보를 빠르게 늘리기 위한 방법이다. 최종 성능 주장은 synthetic 또는 seed metric이 아니라 별도 gold artifact에서 나온 metric만 사용한다.

## 데이터 계층

- `seed`: 파이프라인 회귀와 smoke 검증용이다. 성능 주장에 사용하지 않는다.
- `llm_assisted_train`: LLM이 만든 후보 중 validator와 audit을 통과한 학습용 데이터다.
- `synthetic`: 학습 선택과 개발 비교용이다. 최종 성능으로 표시하지 않는다.
- `human_gold`: 사람이 직접 작성하거나 최종 검수한 Task 1 평가셋이다.
- `task2_gold`: fact-level 근거와 답변 평가 prompt를 분리한 Task 2 평가셋이다.

## Gold Artifacts

Gold 파일은 제출용 입력 파일과 분리한다.

```text
data/gold/task1_human_gold.json
data/gold/task2_fact_gold.json
data/gold/task2_answer_eval_gold.json
```

Gold 데이터는 학습, prompt few-shot 예시, retriever tuning set, LLM synthetic generation seed로 재사용하지 않는다.

## Task 1 Gold

`task1_human_gold.json` row:

```json
{
  "question": "졸업하려면 전공 몇 학점 들어야 해?",
  "label": 0,
  "source_doc_id": null,
  "difficulty": "natural",
  "ambiguous_reason": null,
  "annotator": "human",
  "validated": true
}
```

초기 목표:

- 총 50-75개.
- 라벨별 최소 10개.
- 짧은 구어체, 오타, 경계 질문, 애매한 질문을 포함한다.
- `chunk_3`, `source 1`, 내부 `doc_id` 같은 구현 단서가 질문에 들어가면 gold로 쓰지 않는다.

## Task 2 Gold

`task2_fact_gold.json`은 답변 문장이 아니라 검증 가능한 fact를 담는다.

```json
{
  "fact_id": "graduation_biochemistry_credit_001",
  "label": 0,
  "source_doc_id": "graduation_biochemistry_requirements_chunk_1",
  "source_url": "https://plus.cnu.ac.kr/...",
  "claim": "생화학과 졸업요건은 학과별 교육과정 기준을 확인해야 한다.",
  "evidence_quote": "생화학과 졸업요건 ...",
  "answerable_scope": "static"
}
```

`task2_answer_eval_gold.json`은 사용자 질문과 기대 fact를 연결한다.

```json
{
  "user": "생화학과 졸업 조건 어디서 보면 돼?",
  "expected_fact_ids": ["graduation_biochemistry_credit_001"],
  "must_not_claim": ["확인되지 않은 최신 정보"],
  "naturalness_score": null,
  "factuality_score": null
}
```

초기 목표:

- fact는 라벨별 5-8개.
- answer eval prompt는 25-40개.
- `fresh` 질문은 static RAG 평가와 분리한다.

## Metric Claim Rules

Metric artifact는 아래 필드를 반드시 가진다.

```json
{
  "evaluation_set_type": "human_gold",
  "dataset_origin": "human_gold",
  "claim_level": "heldout_eval",
  "input_path": "data/gold/task1_human_gold.json",
  "input_checksum": "..."
}
```

허용 claim level:

- `sanity`: seed smoke 또는 회귀 검증.
- `training_selection`: synthetic 개발/모델 선택용.
- `heldout_eval`: gold 평가용. `seed` origin은 사용할 수 없다.
- `qualitative_check`: Task 2 자연성/사람 검수용.

## 검증 명령

```powershell
uv run python -m nlp_term.validators --gold-data data/gold --min-task1-gold-rows 50 --min-task1-gold-per-label 10 --min-task2-facts-per-label 5 --min-task2-answer-rows 25
```

```powershell
uv run python -m nlp_term.validators --metric-claim model/metrics/gold_classifier_metrics.json --input data/gold/task1_human_gold.json --require-dataset-origin human_gold --require-claim-level heldout_eval
```

## 보고 원칙

- seed metric은 "pipeline sanity"로만 표현한다.
- synthetic metric은 "training/development metric"으로만 표현한다.
- 최종 Task 1 성능은 `human_gold` metric만 사용한다.
- Task 2는 retrieval, factuality, naturalness를 분리해서 보고한다.
