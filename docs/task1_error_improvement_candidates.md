# Task 1 Gold Error Improvement Candidates

작성일: 2026-06-07

## Scope

이 문서는 Goal 2.3 Step 3 산출물이다. `docs/evidence/task1-gold-error-analysis-2026-06-07.json`의 오답 8개를 원인별로 분리한다.

중요 경계:

- no model improvement has been made in this step.
- gold 질문은 학습 데이터, few-shot prompt, synthetic generation seed로 복사하지 않는다.
- 아래 후보는 다음 실험의 우선순위를 정하기 위한 것이며, 성능 개선 완료를 주장하지 않는다.

## Current Diagnostic Summary

- gold row count: 50
- current macro F1: 0.8385026737967914
- current weighted F1: 0.8385026737967913
- error count: 8
- label 2 issue: 학사일정 label은 false negative 2개와 false positive 4개를 동시에 가진다.
- false negative counts: label 1 = 3, label 2 = 2, label 4 = 3
- false positive counts: label 0 = 2, label 2 = 4, label 3 = 2

## Primary Categories

각 오답은 정확히 하나의 primary category에 배정한다.

| Category | Meaning | Next Action Type |
| --- | --- | --- |
| data coverage shortage | 해당 표현이 train/source-derived 데이터에 충분히 다양하게 없음 | source-backed data expansion |
| label boundary ambiguity | 두 라벨 사이의 의도 경계가 실제 사용자 질문에서 겹침 | label guide and gold review |
| classifier feature or model limitation | 키워드/현재 classifier가 문맥을 구분하지 못함 | feature/model experiment |
| likely annotation ambiguity | gold label 자체도 검토 여지가 있음 | human review before training |
| retrieval/source wording leakage risk | 출처명/문서문구 기반 shortcut이 생길 위험 | leakage guard |

## Error Classification

| # | Question | Expected | Predicted | Primary Category | Why |
| ---: | --- | ---: | ---: | --- | --- |
| 1 | 휴학 신청 공지 어디서 봐? | 1 | 2 | label boundary ambiguity | `휴학 신청`은 학사일정 이벤트처럼 보이지만 질문 의도는 공지 위치 확인이다. |
| 2 | 이번 학기 출석인정 신청 바뀐 거 있어? | 1 | 2 | data coverage shortage | 변경/신청 관련 공지 표현이 일정 표현으로 흡수됐다. 공지 데이터의 절차/변경 질문이 부족하다. |
| 3 | 복학 신청 관련 글 찾는 중이야 | 1 | 2 | label boundary ambiguity | `복학 신청`은 일정과 공지 경계에 있다. “관련 글”은 공지 의도를 강하게 만든다. |
| 4 | 학위수여식 날짜 알려줘 | 2 | 3 | classifier feature or model limitation | 날짜 질문인데 `학위`/행사 문맥이 식단/기타 키워드와 섞여 잘못 분류됐다. |
| 5 | 성적발표일 확인하고 싶어 | 2 | 0 | classifier feature or model limitation | `성적`이 졸업/학점 계열로 오해될 수 있다. 날짜성 토큰을 더 잘 봐야 한다. |
| 6 | 주말 셔틀 있는지 알려줘 | 4 | 3 | data coverage shortage | 셔틀 질문에서 `버스/통학` 없이 `셔틀`만 있는 간단 표현을 더 보강해야 한다. |
| 7 | 공휴일에도 통학 차가 다니나? | 4 | 0 | classifier feature or model limitation | `통학 차` 같은 우회 표현을 셔틀로 묶지 못했다. |
| 8 | 수업 끝나고 야간 셔틀 탈 수 있어? | 4 | 2 | label boundary ambiguity | `수업 끝나고`가 학사일정/시간 문맥을 만들지만 최종 의도는 셔틀 운행이다. |

Category counts:

- data coverage shortage: 2
- label boundary ambiguity: 3
- classifier feature or model limitation: 3
- likely annotation ambiguity: 0
- retrieval/source wording leakage risk: 0

## Label-Wise Interpretation

### Label 1: Notices

Label 1 false negatives는 모두 label 2로 갔다. 공지 질문 중 `휴학`, `복학`, `신청`, `변경` 표현이 학사일정으로 빨려 들어가는 문제가 있다.

Next candidate:

- 공지 데이터에 “신청 관련 글/변경 공지/출석인정 안내” 같은 source-backed 질문 후보를 추가한다.
- 단, gold 문장을 그대로 복제하지 않는다.

### Label 2: Academic Calendar

label 2 / 학사일정은 현재 가장 조심해야 할 라벨이다. 학사일정 질문 자체를 놓치는 false negative도 있고, 공지/셔틀 질문을 학사일정으로 잘못 끌어오는 false positive도 가장 많다.

Next candidate:

- 날짜성 질문과 공지성 질문을 구분하는 boundary guide를 작성한다.
- `날짜`, `일정`, `기간`, `발표일`, `개강`, `종강`처럼 일정 의미가 강한 표현과 `공지`, `글`, `안내`, `신청 관련`처럼 게시물 탐색 의미가 강한 표현을 분리한다.

Smallest next experiment:

- classifier를 바로 바꾸기 전에 label 1/2/4 경계 질문을 source-backed 후보로 10-15개씩 추가하고, gold가 아닌 development sanity set에서 변화만 본다.

### Label 4: Shuttle

Label 4 false negatives는 짧은 구어체와 우회 표현에서 나온다. `통학 차`, `야간 셔틀`, `주말 셔틀`처럼 실제 학생 표현을 더 넣어야 한다.

Next candidate:

- 셔틀 structured timetable이 준비되기 전에도 질문 표현 후보는 늘릴 수 있다.
- 실제 운행 여부 답변은 Task 2/3 source freshness와 분리한다.

## Rejected Candidates

| Candidate | Rejection Reason |
| --- | --- |
| Add the eight gold error questions directly to train data | Gold leakage and overfitting risk. |
| Add keyword exceptions only for these exact phrases | Too brittle; improves this gold set without improving generalization. |
| Report current 50-row gold result as final Task 1 performance | The gold set is intentionally small and not final generalization evidence. |
| Expand Optional Task 3 realtime first | Task 1/2 remain the assignment priority. |

## Recommended Next Task 1 Experiment

Run a small source-backed development expansion, not a gold-tuning patch:

1. Add non-gold candidate questions for label 1/2/4 boundaries.
2. Keep candidates in a training/development artifact, not `data/gold`.
3. Re-run source-disjoint sanity and gold evaluation.
4. Accept the change only if gold macro F1 improves without reducing any class F1 below the current class-specific floor.

This recommendation remains an experiment proposal. It is not an implemented model improvement.
