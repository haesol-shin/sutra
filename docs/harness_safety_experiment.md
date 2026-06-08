# Task 2/3 Phase A Harness Safety Experiment

작성일: 2026-06-07

이 문서는 Task 2/Optional Task 3 evidence harness의 1차 안전성 실험 결과를 기록한다. 목적은 최종 성능을 주장하는 것이 아니라, 현재 하네스가 근거 부족, 최신성 질문, 교차 도메인 질문에서 writer 호출을 안정적으로 제어하는지 확인하는 것이다.

## Scope

- 대상 코드: `src/nlp_term/chat/orchestrator.py`
- 실험 러너: `src/nlp_term/chat/harness_experiment.py`
- 질문셋: `data/harness_safety_questions.json`
- 결과 artifact: `docs/evidence/harness-safety-experiment-2026-06-07.json`

이번 실험은 production `batch.py`, `ui/app.py`, `realtime.py`를 전환하지 않는다. Qwen 실제 생성 품질도 평가하지 않는다. 주입 writer는 일부 질문에서 메뉴/시간표를 지어낼 수 있도록 구성했고, 하네스가 writer 호출 전 차단하는지를 본다.

## Question Set

- 총 30개 질문
- 5개 도메인 포함: graduation, notices, academic_calendar, dining, shuttle
- 포함 시나리오:
  - source_navigation
  - static_fact
  - procedural
  - current_fact
  - unsupported
  - wrong_domain_guard

## Result Summary

2026-06-07 실행 결과:

| Metric | Value |
| --- | ---: |
| question_count | 30 |
| answered_count | 16 |
| fail_close_count | 14 |
| answered_rate | 0.533 |
| fail_close_rate | 0.467 |
| route_match_rate | 0.933 |
| answer_kind_match_rate | 0.933 |
| wrong_domain_pass_count | 0 |
| current_fact_hallucination_count | 0 |
| validator_failure_count | 0 |
| pass_criteria_met | true |

안전성 종료 기준인 wrong-domain pass 0건, current-fact hallucination 0건은 통과했다.

## Bottlenecks

| Bottleneck | Count | Interpretation |
| --- | ---: | --- |
| none | 16 | 현재 RAG 근거와 하네스 정책으로 답변 가능 |
| data | 12 | current_fact 구조화 필드, official-chain, source registry/parser 준비 부족 |
| classifier | 2 | 질문에 도메인 단서가 섞이거나 기존 keyword fallback이 기본 label로 흘러간 케이스 |

data 병목이 가장 크다. 특히 dining은 `official_chain_ok=False`라 current fact를 fail-close하고, notices/calendar/shuttle의 최신성 질문은 구조화 필드가 없어 fail-close한다. 이는 Qwen writer 문제가 아니라 source/parser/metadata 준비 부족 신호로 본다.

## Issue Found And Fixed

초기 실험에서 `셔틀 시간표는 졸업요건 페이지에서 확인해도 돼?` 같은 교차 도메인 source-navigation 질문이 classifier에 의해 graduation으로 라우팅되고, graduation source navigation으로 통과할 수 있는 문제가 발견됐다.

수정:

- source-navigation 질문에서 2개 이상 도메인 단서가 섞이면 `AnswerKind.UNSUPPORTED`로 fail-close한다.
- wrong-domain metric은 단순히 retrieved evidence domain만 보지 않고, `wrong_domain_guard` 시나리오에서 answered가 발생해도 pass로 계산하지 않도록 강화했다.
- 회귀 테스트: `test_harness_fails_closed_for_cross_domain_source_navigation`

## Next Bottleneck

다음 단계는 모델 품질 실험보다 data/retrieval 쪽이 우선이다.

1. current_fact에 필요한 구조화 metadata 정의와 parser 보강
2. dining source official-chain 재검증 또는 대체 source 확보
3. notices/calendar 최신성 질문용 posted_date/date_span 구조화
4. classifier fallback의 교차 도메인/범위 밖 질문 처리 보강
5. 이후 Qwen writer 품질 실험으로 자연스러움과 hallucination을 별도 측정

이 artifact는 sanity-level harness safety probe이며, 최종 Task 2/3 성능 claim으로 사용하면 안 된다.
