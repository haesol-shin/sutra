# Task 2 Public Probe Harness Diagnosis

- 기준 시각: `2026-06-08T00:00:00+09:00`
- 질문 수: 14
- Task1 label match: 13 / 14 (92.86%)
- Temporal type match: 10 / 14 (71.43%)
- Answered: 6 / 14 (42.86%)
- Fail-closed: 8 / 14 (57.14%)
- Bottlenecks: `{"classifier": 1, "data": 1, "evidence": 2, "none": 4, "retrieval": 2, "temporal": 4}`

이 결과는 현재 harness의 trace 진단이며 최종 Task 2 성능 claim이 아니다.

| ID | Label | Temporal | Target | Status | Bottleneck | Failure |
| --- | --- | --- | --- | --- | --- | --- |
| public_probe_01 | 0 / 0 | none / none |  | answered | none |  |
| public_probe_02 | 2 / 2 | date_lookup / date_lookup |  | answered | none |  |
| public_probe_03 | 3 / 3 | current_snapshot / current_snapshot | 2026-06-08 | fail_closed | data | current_fact_source_not_official_chain_verified |
| public_probe_04 | 4 / 4 | period_summary / ongoing_status | 2026-06-15~2026-06-21 | fail_closed | temporal | date_filtered_evidence_missing_or_mismatched |
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

## Structured Row 적용 후 진단

이번 실행은 structured calendar/dining/shuttle row가 `knowledge_seed.json`에 연결된 뒤의 harness trace다. 전체 답변 성공은 6/14이고, 실패 8개는 모델 생성 품질보다 routing, source coverage, freshness/evidence gate 문제가 크다.

### 개선된 항목

- `public_probe_02`: 수강신청 시작일 질문은 academic calendar structured row를 검색해 답변 가능해졌다.
- `public_probe_11`: `종강일` 질문은 `하기방학` alias가 걸려 답변 가능해졌다.
- `public_probe_12`: 여름 계절학기 종료 질문은 calendar structured row를 검색해 답변 가능해졌다.
- `public_probe_04`: 셔틀 structured row는 검색된다. 다만 temporal/evidence gate가 기간 row를 아직 제대로 해석하지 못해 fail-close한다.

### 남은 실패 원인

| ID | 주요 원인 | 해석 |
| --- | --- | --- |
| public_probe_03 | dining source official-chain 미승인 | `cnu_mobile_food` row는 구조화됐지만 `official_chain_ok=False`라 current fact 답변이 차단된다. |
| public_probe_04 | temporal router + date_span interval 처리 부족 | 질문 의도는 `ongoing_status`인데 `period_summary`로 분류된다. 또한 `2026-03-03/2026-06-21` 같은 기간 근거를 target week와 겹치는지 검사하지 못한다. |
| public_probe_05 | latest notice temporal 분류 부족 | “이번에 올라온 공지사항”을 `latest_item`으로 보지 못하고 `none`으로 둔다. |
| public_probe_06 | changed-since temporal 분류 부족 | “새로 업데이트된 셔틀버스 정류장”을 변경 조회로 분류하지 못한다. |
| public_probe_07 | 변경 근거 source 부족 | calendar row는 일정 자체만 있고 “5월 이후 변경 여부”를 증명하는 notice/change evidence가 없다. |
| public_probe_08 | 다음주 식단 데이터 부족 | 현재 structured dining은 2026-06-08 snapshot만 있어 2026-06-15~2026-06-21 식단을 답변할 근거가 없다. |
| public_probe_09 | latest notice temporal + posted_date 구조 부족 | 공지 board chunk는 있지만 최신 게시일을 안정적으로 뽑는 `posted_date` row가 없다. |
| public_probe_10 | Task 1 classifier + source 부족 | 인공지능학과 24학번 프로젝트 수업 질문이 notice로 오분류된다. CIC/컴퓨터인공지능학과 교육과정 source가 아직 없다. |
| public_probe_13 | 다음주 식단 데이터 부족 | 2026-06-16 2학생회관 row가 없어서 date-filtered evidence gate에서 차단된다. |
| public_probe_14 | 장학 공지 source 부족 | 토익 장학금 기준을 담은 scholarship evidence가 없어 notice retrieval score가 낮다. |

### 다음 해결 순서

1. Temporal router 보강: `다음주 + 정상 운행`은 `ongoing_status`, `이번에/최근/가장 최근 공지`는 `latest_item`, `새로 업데이트된`은 `changed_since`로 분류한다.
2. Evidence date overlap 보강: `date_span`, `valid_start/valid_end` 기간 row가 target day/week와 겹치면 date-filtered evidence로 인정한다.
3. Notice structured parser 추가: board list에서 `title`, `posted_date`, `url`, `department` row를 만들고 latest query를 처리한다.
4. Dining source expansion: 최소 6월 전체 또는 다음주 date-param fetch가 가능한 식단 source path를 확보한다.
5. Graduation/CIC source expansion: 컴퓨터인공지능학과/인공지능학과 2024학번 교육과정과 프로젝트 수업 기준 source를 추가한다.
