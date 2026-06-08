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
| index-eligible active sources | 45 | 32 | 통과 |
| raw fetched sources | 45 | 120 | 미달 |
| accepted knowledge docs | 1,814 | 600 | 통과 |
| structured rows | 1,533 | 700 | 통과 |
| index chunk candidates | 1,814 | 1,500 | 통과 |
| graduation docs | 271 | 180 | 통과 |
| graduation rows | 228 | 150 | 통과 |
| notice docs | 94 | 80 | 통과 |
| calendar rows | 279 | 120 | 통과 |
| dining rows | 925 | 120 | 통과 |
| shuttle rows/segments | 41 | 40 | 통과 |

## 분포

- domain: dining 1,084, academic_calendar 315, graduation 271, notices 94, shuttle 50
- row types: dining_menu 925, academic_calendar_event 279, graduation_requirement 228, notice_board_item 60, shuttle_segment 39, shuttle_route 2
- generation: structured_row 1,533, source_parse 281
- source count in accepted docs: 45
- notice ratio: 0.052
- max source concentration: 0.070

## 실패 및 병목

- Tier 1 hard floor validator는 `raw sources 45 below 120`에서 실패한다.
- 현재치 기준 sanity gate(`min_raw_sources=45`)는 통과했다. 즉 raw source 120을 제외한 hard floor는 모두 충족한다.
- raw source 120은 의미 있는 공식 source를 더 찾아야 한다. 중앙 공지 페이지만 대량 추가하면 notice cap과 사용자 요구의 의미성 조건을 깨기 쉽다.
- collection failure 7건은 모두 cached raw snapshot 재사용으로 처리됐다.
- source parse failure는 0건이다.

## 이번 실행에서 개선된 점

- 졸업요건이 일반 chunk가 아니라 `graduation_requirement` row로 228개 생성된다.
- 셔틀은 route 2개 외에 출발시각/정류장 `shuttle_segment` 39개를 생성한다.
- 식단은 2026년 6월 주간 식당별 source를 통해 `dining_menu` 925개를 생성한다.
- notice는 high-value score, dedupe, board cap을 적용한다.
- `plus.cnu.ac.kr`는 Python `requests`에서 연결 리셋이 반복되어 collector에 curl fallback을 추가했다.
- 2023/2024 교육과정 PDF, 2023~2025 학사일정, 2026년 6월 식당별 주간 식단, 학사공지 2~6페이지를 stage1 active source로 추가했다.
- 연도별 학사일정 source의 `curriculum_year`를 calendar row 날짜/row_id에 반영한다.

## 다음 작업

1. raw source 120 목표는 공식성과 의미성을 유지한 상태에서 재검토한다.
2. 대표 학과 top5 졸업요건 source를 추가해 graduation source 다양성을 더 높인다.
3. 학과 학사공지/졸업공지 source를 high-value gate로 추가하되 notice docs 150 cap을 유지한다.
4. RAG index/probe 단계에서 1,814 docs가 실제 검색 품질로 이어지는지 평가한다.
