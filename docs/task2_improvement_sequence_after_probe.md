# Task 2 Improvement Sequence After Public Probe

작성일: 2026-06-08

이 문서는 14개 public probe trace 진단 이후의 개선 순서를 고정한다. 현재 진단 결과는 [`docs/task2_public_probe_harness_diagnosis_2026_06_08.md`](task2_public_probe_harness_diagnosis_2026_06_08.md)에 기록되어 있다.

## 즉시 실행할 Goal

1. Validator 정책 완화
   - 계획: [`docs/superpowers/plans/2026-06-08-validator-policy-softening.md`](superpowers/plans/2026-06-08-validator-policy-softening.md)
   - 목적: 내부 trace 누출은 hard block으로 유지하되, URL/숫자/기관명 mismatch는 기본 warning으로 낮춘다.

2. Evidence pack context 확장
   - 계획: [`docs/superpowers/plans/2026-06-08-evidence-pack-context-expansion.md`](superpowers/plans/2026-06-08-evidence-pack-context-expansion.md)
   - 목적: chunk의 첫 문장만 Qwen에게 넘기는 정보 손실을 줄이고, temporal/current 질문은 더 많은 bounded context를 전달한다.

3. Atomic-aware chunking smoke 선행
   - 계획: [`docs/superpowers/plans/2026-06-08-structure-aware-chunking.md`](superpowers/plans/2026-06-08-structure-aware-chunking.md)
   - 목적: 확실한 날짜/시간/식단/공지/졸업요건 패턴만 atomic guard로 보호하고, 일반 설명문은 recursive splitting을 유지한다. fixed-window는 낮은 신뢰 fallback으로만 남긴다.

4. Retrieval candidate 확장
   - 계획: [`docs/superpowers/plans/2026-06-08-retrieval-candidate-expansion.md`](superpowers/plans/2026-06-08-retrieval-candidate-expansion.md)
   - 목적: retrieval 후보 수와 final evidence pack 크기를 분리하고, domain filter 전후 후보를 trace에 남긴다.

이 goal들은 데이터 확장 전에 실행한다. 이유는 추가 데이터를 넣더라도 validator, evidence pack, chunking, retrieval 후보 정책이 과도하게 정보를 버리거나 구조를 깨면 Qwen baseline 평가가 왜곡되기 때문이다.

## 나중에 처리할 항목

### Temporal Extractor 확장

현재 temporal parser는 모델을 붙이지 않고 deterministic extractor로 유지한다. 다음 확장 시에는 `temporal_type` 직접 분류보다 아래 feature를 우선 추출한다.

- time expression: `오늘`, `다음주 화요일`, `5월 이후`, `가장 최근`, `이번 학기`
- normalized date/range: ISO week 기준 날짜 또는 기간
- action cue: 메뉴 조회, 게시일 조회, 변경사항 조회, 정상 운행 여부, 일정 날짜 조회
- freshness cue: 오늘, 최근, 최신, 새로, 변동, 정상 운행
- domain: dining, notices, academic_calendar, shuttle, graduation

모델 기반 temporal classifier는 이 단계에서 붙이지 않는다. 실패 원인을 classifier/RAG/Qwen writer와 분리하기 어렵기 때문이다. 로컬 Qwen 보조 분류는 deterministic extractor가 충분히 평가된 뒤 애매한 질문에만 제한적으로 검토한다.

### Task 1 Boundary 보강

`충남대학교 인공지능학과 24학번의 경우 프로젝트 수업을 몇 개 들어야 하나요?`가 notices로 route된 것은 Task 1 classifier 문제다. 데이터 확장 전후로 curriculum/graduation과 notices 경계 질문을 별도 평가셋에 추가해야 한다.

우선 보강할 cue:

- `학번`
- `교육과정`
- `프로젝트 수업`
- `전공`
- `이수`
- `졸업`
- 학과명 + 학번 + 수업/교과목 조합

### Qwen Baseline

위 즉시 goal들이 끝난 뒤 14개 public probe를 Qwen writer로 재실행한다. 현재 deterministic trace 진단은 Qwen 성능 claim이 아니며, Qwen baseline은 validator/evidence/chunking/retrieval 손실을 줄인 뒤 수행해야 한다.

### Data Expansion

데이터 확장은 Qwen baseline 이후 실행한다. 단, source-specific parser 설계는 chunking goal 전에 문서로 고정한다. 구현은 source별 최소 serial loop가 통과한 뒤 넓힌다.

Source-specific parser 방향은 [`docs/data_expansion_goal_plan.md`](data_expansion_goal_plan.md)의 Phase 2를 기준으로 한다. 핵심 원칙은 structured rows와 natural-language knowledge chunks를 함께 만든다는 것이다. 학사일정, 식단, 셔틀처럼 날짜/장소/행 단위가 중요한 source는 text chunk만으로 처리하지 않는다.

우선순위는 다음과 같다.

1. 졸업/교육과정: 2023, 2024, 2025, 2026 교육과정과 2026년 기준 대표 학과 top5
2. 학사일정: 날짜/행사명/date_span 구조화
3. 공지/장학: posted_date, title, source_url 구조화
4. 식단: menu_date, location, meal_type, menu_items 구조화

### Hybrid RAG

장기적으로는 lexical overlap만으로 부족하다. 데이터가 늘어난 뒤 BM25/keyword + embedding + metadata filter 조합을 검토한다. 현재 53개 chunk만으로 embedding 품질을 판단하면 불안정하므로, 데이터 확장 이후 실험한다.

### Controlled Fetch

Controlled fetch는 Qwen이 자유롭게 tool-call하는 방식이 아니다. source registry에 등록된 공식 source만 harness가 정해진 parser로 가져오는 방식이다. 현재는 문서화만 하고, 식단/셔틀/최신공지 데이터 확장 이후 구현한다.

필요한 최소 계약:

- source id
- 공식 URL 또는 endpoint
- parser type
- target date/range parameter
- structured fields
- fetched_at
- official_chain_ok

## 현재 기준 결론

개선 순서는 다음으로 고정한다.

```text
validator
-> evidence pack
-> atomic-aware chunking smoke
-> retrieval candidate policy
-> temporal extractor 확장
-> Task1 boundary 보강
-> Qwen baseline
-> data expansion
-> hybrid RAG
-> controlled fetch
```
