# Task 2 Public Probe Harness Diagnosis

- 기준 시각: `2026-06-08T00:00:00+09:00`
- 질문 수: 14
- Task1 label match: 13 / 14 (92.86%)
- Temporal type match: 11 / 14 (78.57%)
- Answered: 7 / 14 (50.00%)
- Fail-closed: 7 / 14 (50.00%)
- Bottlenecks: `{"classifier": 1, "data": 1, "evidence": 2, "none": 5, "retrieval": 2, "temporal": 3}`

이 결과는 현재 harness의 trace 진단이며 최종 Task 2 성능 claim이 아니다.

| ID | Label | Temporal | Target | Status | Bottleneck | Failure |
| --- | --- | --- | --- | --- | --- | --- |
| public_probe_01 | 0 / 0 | none / none |  | answered | none |  |
| public_probe_02 | 2 / 2 | date_lookup / date_lookup |  | answered | none |  |
| public_probe_03 | 3 / 3 | current_snapshot / current_snapshot | 2026-06-08 | fail_closed | data | current_fact_source_not_official_chain_verified |
| public_probe_04 | 4 / 4 | ongoing_status / ongoing_status | 2026-06-15~2026-06-21 | answered | none |  |
| public_probe_05 | 1 / 1 | none / latest_item |  | answered | temporal |  |
| public_probe_06 | 4 / 4 | none / changed_since |  | answered | temporal |  |
| public_probe_07 | 2 / 2 | changed_since / changed_since | 2026-05-09~2026-06-08 | fail_closed | evidence | date_filtered_evidence_missing_or_mismatched |
| public_probe_08 | 3 / 3 | period_summary / period_summary | 2026-06-15~2026-06-21 | fail_closed | retrieval | top_score_below_threshold;no_fetchable_registry_candidate |
| public_probe_09 | 1 / 1 | none / latest_item |  | fail_closed | temporal | top_score_below_threshold;controlled_fetch_candidate_exists |
| public_probe_10 | 1 / 0 | none / none |  | fail_closed | classifier | top_score_below_threshold;controlled_fetch_candidate_exists |
| public_probe_11 | 2 / 2 | date_lookup / date_lookup |  | answered | none |  |
| public_probe_12 | 2 / 2 | date_lookup / date_lookup |  | answered | none |  |
| public_probe_13 | 3 / 3 | future_schedule / future_schedule | 2026-06-16 | fail_closed | evidence | date_filtered_evidence_missing_or_mismatched |
| public_probe_14 | 1 / 1 | none / none |  | fail_closed | retrieval | top_score_below_threshold;controlled_fetch_candidate_exists |

## Bottleneck Legend

- `classifier`: Task 1 label이 기대값과 다르다.
- `temporal`: temporal type이 기대값과 다르다.
- `retrieval`: 검색 결과가 없거나 score가 낮아 근거 pack을 만들 수 없다.
- `data`: controlled fetch/source registry/공식성/구조화 데이터가 부족하다.
- `evidence`: 검색은 됐지만 날짜/근거 충분성 검사를 통과하지 못했다.
- `writer`: 답변 생성 후 validator에서 막혔다.
- `none`: 현재 trace 기준으로 harness 병목이 없다.

## Router/Overlap 개선 후 진단

이번 변경은 두 가지 좁은 병목만 겨냥했다.

- `다음주 셔틀 정상 운행` 유형은 기간 요약(`period_summary`)이 아니라 운행 상태(`ongoing_status`)로 routing한다.
- shuttle처럼 일정 기간 동안 유효한 source row는 `valid_start`/`valid_end` 또는 `date_span`이 질문 target range와 겹치면 날짜 근거로 인정한다.

그 결과 `public_probe_04`는 fail-closed에서 answered로 바뀌었다. 전체 public probe 기준 Answered는 6/14에서 7/14로, Temporal type match는 10/14에서 11/14로 개선됐다.

남은 주요 실패 원인은 다음과 같다.

- `public_probe_03`: 식단 현재 스냅샷은 검색됐지만 공식 chain 검증 조건을 통과하지 못했다.
- `public_probe_05`, `public_probe_09`: 최근 공지 질문은 `latest_item` router와 `posted_date` 기반 notice row가 아직 부족하다.
- `public_probe_06`, `public_probe_07`: 변경/업데이트 질문은 최근 기간 window와 변경 근거 row가 부족하다.
- `public_probe_08`, `public_probe_13`: 다음주/특정일 식단 데이터가 knowledge에 없다.
- `public_probe_10`: Task 1 classifier가 졸업 질문을 공지로 오분류했고, 컴퓨터인공지능학과 졸업요건 source도 부족하다.
- `public_probe_14`: 토익 장학금 기준 source가 없다.

다음 개선 우선순위는 데이터 확장 전에 resolver가 막고 있는 최소 병목과 데이터 부재를 분리하는 것이다.

1. notice/latest/changed-since router와 `posted_date` 구조화 row를 추가한다.
2. 식단 source adapter가 월간/일자별 데이터를 안정적으로 확보하도록 확장한다.
3. 컴퓨터인공지능학과 졸업요건 및 장학금 source를 공식 문서 기반으로 추가한다.
4. Task 1 classifier의 졸업/공지 혼동 케이스를 별도 fixture로 고정한다.
