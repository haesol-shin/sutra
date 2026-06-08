# Tier 1 Data Collection Run - 2026-06-08

범위 타입: `feat`, `test`, `docs`, `chore`

## 실행 요약

- `source_probe.json`은 `--stage all --fetch`로 재생성했다.
- `knowledge_seed.json`은 새 source probe로 재생성했다.
- RAG index/probe 평가는 이번 goal 범위에서 제외했다.
- raw snapshot과 source probe는 `.gitignore` 대상이므로 커밋하지 않는다.

## 검증 수치

| 항목 | 현재 | Tier 1 hard floor | 상태 |
|---|---:|---:|---|
| index-eligible active sources | 15 | 32 | 미달 |
| raw fetched sources | 15 | 120 | 미달 |
| accepted knowledge docs | 556 | 600 | 미달 |
| structured rows | 466 | 700 | 미달 |
| index chunk candidates | 556 | 1,500 | 미달 |
| graduation docs | 166 | 180 | 미달 |
| graduation rows | 141 | 150 | 미달 |
| notice docs | 18 | 80 | 미달 |
| calendar rows | 69 | 120 | 미달 |
| dining rows | 205 | 120 | 통과 |
| shuttle rows/segments | 41 | 40 | 통과 |

## 분포

- domain: dining 244, graduation 166, academic_calendar 78, shuttle 50, notices 18
- row types: dining_menu 205, graduation_requirement 141, academic_calendar_event 69, shuttle_segment 39, notice_board_item 10, shuttle_route 2
- generation: structured_row 466, source_parse 90
- source count in accepted docs: 15
- notice ratio: 0.032
- max source concentration: 0.228

## 실패 및 병목

- Tier 1 hard floor validator는 `index-eligible sources 15 below 32`에서 실패한다.
- source concentration hard floor도 0.15 이하가 필요한데 현재 0.228이다.
- 중앙 교육과정 PDF가 127 docs로 가장 크다. 졸업요건 추가 source가 필요하다.
- calendar는 2026년 단일 source라 69 rows에 머문다. 2023~2026 학사일정 source 확장이 필요하다.
- notice는 cap/gate 이후 18 docs로 안전하지만, 목표량 80에는 부족하다. 학과 학사공지와 졸업/수강/장학 high-value notice source가 필요하다.
- collection failure 9건은 모두 cached raw snapshot 재사용으로 처리됐다.
- source parse failure는 0건이다.

## 이번 실행에서 개선된 점

- 졸업요건이 일반 chunk가 아니라 `graduation_requirement` row로 141개 생성된다.
- 셔틀은 route 2개 외에 출발시각/정류장 `shuttle_segment` 39개를 생성한다.
- 식단은 2026-06-08 주간 식당별 source를 통해 `dining_menu` 205개를 생성한다.
- notice는 high-value score, dedupe, board cap을 적용한다.

## 다음 작업

1. 공식 source를 32개 이상으로 늘린다.
2. 2023~2026 교육과정 PDF와 대표 학과 top5 졸업요건 source를 추가한다.
3. 2023~2026 학사일정 source를 추가한다.
4. 학과 학사공지/졸업공지 source를 high-value gate로 추가한다.
5. source concentration 0.15 이하가 되도록 중앙 PDF 의존도를 낮춘다.
