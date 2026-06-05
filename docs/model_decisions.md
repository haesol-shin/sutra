# Model And Data Decisions

작성일: 2026-06-06

## Data Policy

- Task 1, 2, 3는 같은 raw source inventory를 공유한다.
- Downstream dataset은 목적별로 분리한다.
- `data/knowledge_seed.json`, `data/cls_train_seed.json`, `data/label_audit_seed.json`, `data/qa_seed.json`은 파이프라인 검증용 seed이다.
- 최종 학습 데이터에는 `generation_method="dry_run"` 또는 `validated=false` row를 넣지 않는다.
- 현재 seed audit은 template 기반 sanity check다. 최종 self-consistency label 생성은 독립 vote 결과를 audit artifact에 `vote_labels`, `final_label`, `confidence`, `decision`으로 남긴다.

## Task 1

- 1차 baseline은 `char_wb` TF-IDF + Logistic Regression이다.
- seed metric은 학습 경로 sanity check일 뿐이며, 성능 주장으로 사용하지 않는다.
- 현재 seed baseline metric은 `held_out_seed_sanity` 범위로 기록한다. seed 규모가 작기 때문에 점수는 모델 선택 근거가 아니라 평가 코드 분리 여부 확인용이다.
- 다음 실제 평가 전제는 source-backed generated dataset과 held-out split이다.

## Task 2/3 Generator Candidates

- 최종 inference runtime에서 외부 LLM API, MCP, full tool-call agent를 쓰지 않는다.
- 15GB VRAM 제약 때문에 primary/candidate는 9B 이하만 허용한다.
- `Qwen/Qwen3.5-9B`를 primary candidate로 둔다. Hugging Face model card는 9B parameter와 Transformers/vLLM/SGLang 호환성을 명시한다.
- `Gemma4 E4B`는 9B 이하 대안 후보지만 Korean campus QA 실험이 필요하다.
- `EXAONE-4.0-1.2B`는 Korean-relevant reference로 남긴다. 너무 작으면 generation 품질이 낮을 수 있다.
- `EXAONE-4.5-33B`는 한국어/문서 이해 측면에서 관심 후보지만 9B/15GB VRAM 제약을 넘어 cut 처리한다.

Model metadata는 `data/model_shortlist.json`에 기록하고 `validators --model-shortlist`로 검사한다.
