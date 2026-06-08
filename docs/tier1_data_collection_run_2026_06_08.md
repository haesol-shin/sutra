# Tier 1 Data Collection Run - 2026-06-08

범위 타입: `feat`, `test`, `docs`, `chore`

## 실행 요약

- `source_probe.json`은 `--stage all --fetch --reuse-existing-raw`로 재생성했다.
- `knowledge_seed.json`은 새 source probe로 재생성했다.
- RAG index/probe 평가는 이번 goal 범위에서 제외했다.
- raw snapshot과 source probe는 `.gitignore` 대상이므로 커밋하지 않는다.

## 검증 수치

| 항목 | 현재 | Tier 1 hard floor | 상태 |
|---|---:|---:|---|
| index-eligible active sources | 60 | 32 | 통과 |
| raw fetched sources | 123 | 120 | 통과 |
| accepted knowledge docs | 1,954 | 600 | 통과 |
| structured rows | 1,616 | 700 | 통과 |
| index chunk candidates | 1,954 | 1,500 | 통과 |
| graduation docs | 314 | 180 | 통과 |
| graduation rows | 242 | 150 | 통과 |
| notice docs | 103 | 80 | 통과 |
| calendar rows | 348 | 120 | 통과 |
| dining rows | 925 | 120 | 통과 |
| shuttle rows/segments | 41 | 40 | 통과 |

## 분포

- domain: dining 1,085, academic_calendar 393, graduation 314, notices 103, shuttle 59
- row types: dining_menu 925, academic_calendar_event 348, graduation_requirement 242, notice_board_item 60, shuttle_segment 39, shuttle_route 2
- generation: structured_row 1,616, source_parse 338
- source count in accepted docs: 60
- raw source count: 123
- all generated docs including non-index candidate docs: 2,104
- notice ratio: 0.053
- max source concentration: 0.065

## 실패 및 병목

- Tier 1 hard floor validator는 통과했다.
- collection failure 3건은 모두 cached raw snapshot 재사용으로 처리됐다.
- source parse failure는 36건이다. 대부분 `index_eligible=false` raw candidate pool 또는 도메인 전용 structured parser가 아직 없는 상세/목록 page다.
- raw candidate pool은 수집 evidence로 보존하지만 RAG accepted docs에서는 제외한다.

## 이번 실행에서 개선된 점

- 졸업요건이 일반 chunk가 아니라 `graduation_requirement` row로 242개 생성된다.
- 셔틀은 route 2개 외에 출발시각/정류장 `shuttle_segment` 39개를 생성한다.
- 식단은 2026년 6월 주간 식당별 source를 통해 `dining_menu` 925개를 생성한다.
- notice는 high-value score, dedupe, board cap을 적용한다.
- `plus.cnu.ac.kr`는 Python `requests`에서 연결 리셋이 반복되어 collector에 curl fallback을 추가했다.
- 2023/2024 교육과정 PDF, 2023~2025 학사일정, 2026년 6월 식당별 주간 식단, 학사공지 2~6페이지를 stage1 active source로 추가했다.
- 연도별 학사일정 source의 `curriculum_year`를 calendar row 날짜/row_id에 반영한다.
- `active`와 `index_eligible`을 분리해 raw source 120 목표와 RAG 품질 목표가 충돌하지 않도록 했다.
- 수강신청, 영어능력 인정/TOEIC, 장학, 학과 졸업요건, 셔틀 보완 source를 추가했다.
- 학과 공지/중앙 학사공지 후보 page는 `index_eligible=false` raw candidate pool로 저장했다.
- 대량 source 수집 안정화를 위해 `--reuse-existing-raw` 옵션을 추가했다.

## 다음 작업

1. RAG index/probe 단계에서 1,954 accepted docs가 실제 검색 품질로 이어지는지 평가한다.
2. `index_eligible=false` raw candidate pool 중 학과 공지 parser/gate를 구현해 일부를 승격할지 판단한다.
3. 대표 학과 top5 졸업요건 source는 현재 추가분으로 보완됐지만, 학과 인원 기준 공식 문서가 확보되면 source 우선순위를 재정렬한다.
