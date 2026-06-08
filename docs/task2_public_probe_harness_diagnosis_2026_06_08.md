# Task 2 Public Probe Harness Diagnosis

- 기준 시각: `2026-06-08T00:00:00+09:00`
- 질문 수: 14
- Task1 label match: 13 / 14 (92.86%)
- Temporal type match: 13 / 14 (92.86%)
- Answered: 9 / 14 (64.29%)
- Fail-closed: 5 / 14 (35.71%)
- Bottlenecks: `{"classifier": 1, "data": 1, "evidence": 2, "none": 7, "retrieval": 1, "temporal": 1, "writer": 1}`

이 결과는 현재 harness의 trace 진단이며 최종 Task 2 성능 claim이 아니다.

| ID | Label | Temporal | Target | Status | Bottleneck | Failure |
| --- | --- | --- | --- | --- | --- | --- |
| public_probe_01 | 0 / 0 | none / none |  | answered | none |  |
| public_probe_02 | 2 / 2 | date_lookup / date_lookup |  | answered | none |  |
| public_probe_03 | 3 / 3 | current_snapshot / current_snapshot | 2026-06-08 | fail_closed | data | current_fact_source_not_official_chain_verified |
| public_probe_04 | 4 / 4 | ongoing_status / ongoing_status | 2026-06-15~2026-06-21 | answered | none |  |
| public_probe_05 | 1 / 1 | latest_item / latest_item |  | answered | none |  |
| public_probe_06 | 4 / 4 | none / changed_since |  | answered | temporal |  |
| public_probe_07 | 2 / 2 | changed_since / changed_since | 2026-05-09~2026-06-08 | fail_closed | evidence | date_filtered_evidence_missing_or_mismatched |
| public_probe_08 | 3 / 3 | period_summary / period_summary | 2026-06-15~2026-06-21 | fail_closed | retrieval | top_score_below_threshold;no_fetchable_registry_candidate |
| public_probe_09 | 1 / 1 | latest_item / latest_item |  | answered | none |  |
| public_probe_10 | 1 / 0 | none / none |  | answered | classifier |  |
| public_probe_11 | 2 / 2 | date_lookup / date_lookup |  | answered | none |  |
| public_probe_12 | 2 / 2 | date_lookup / date_lookup |  | answered | none |  |
| public_probe_13 | 3 / 3 | future_schedule / future_schedule | 2026-06-16 | fail_closed | evidence | date_filtered_evidence_missing_or_mismatched |
| public_probe_14 | 1 / 1 | none / none |  | fail_closed | writer | raw_json_or_template_text |

## Bottleneck Legend

- `classifier`: Task 1 label이 기대값과 다르다.
- `temporal`: temporal type이 기대값과 다르다.
- `retrieval`: 검색 결과가 없거나 score가 낮아 근거 pack을 만들 수 없다.
- `data`: controlled fetch/source registry/공식성/구조화 데이터가 부족하다.
- `evidence`: 검색은 됐지만 날짜/근거 충분성 검사를 통과하지 못했다.
- `writer`: 답변 생성 후 validator에서 막혔다.
- `none`: 현재 trace 기준으로 harness 병목이 없다.

## Notice Latest Parse 개선 후 진단

이번 변경은 공지 목록 HTML을 단순 chunk가 아니라 정렬 가능한 `notice_board_item` row로 바꾸는 데 집중했다.

- `academic_notice_board`에서 `title`, `posted_date`, `author`, `detail_url`, `notice_no`, `is_pinned`, `hits`, `has_attachment`를 구조화한다.
- `latest_item` 질문에서는 `posted_date`가 있는 notice row를 우선 검색하고, evidence pack에서도 최신 게시일 순서가 앞에 오도록 정렬한다.
- `이번에/최근/최신/가장 최근 + 공지/게시/올라온` 형태의 notice 질문은 `latest_item`으로 routing한다.

결과적으로 `public_probe_05`와 `public_probe_09`가 temporal mismatch/retrieval 병목에서 answered로 바뀌었다. 전체 public probe 기준 Answered는 7/14에서 9/14로, Temporal type match는 11/14에서 13/14로 개선됐다.

이번 변경으로 `data/knowledge_seed.json`은 166개 doc이 되었고, structured row는 106개다. row type별 개수는 `notice_board_item=10`, `academic_calendar_event=69`, `dining_menu=25`, `shuttle_route=2`다.

남은 주요 실패 원인은 다음과 같다.

- `public_probe_03`: 식단 source는 아직 official-chain 검증이 없어 current fact가 차단된다.
- `public_probe_06`: `새로 업데이트된 셔틀버스 정류장`은 아직 `changed_since`로 routing되지 않는다.
- `public_probe_07`: 변경된 학사일정 여부는 일정 row만으로는 부족하고 변경 공지/게시일 근거가 필요하다.
- `public_probe_08`, `public_probe_13`: 다음주/특정일 식단 row가 knowledge에 없다.
- `public_probe_10`: classifier가 인공지능학과 졸업/교육과정 질문을 notices로 오분류한다. source도 컴퓨터인공지능학과 기준이 부족하다.
- `public_probe_14`: 토익 장학금 질문은 관련 장학금 source가 없어서 다른 장학 공지 row가 검색되고, writer validator에서 차단된다.

다음 우선순위는 데이터 확장이다. 특히 식단 월간/일자별 source, 셔틀 변경 공지, 컴퓨터인공지능학과 졸업요건, 토익 장학금 source가 없으면 harness만으로는 더 이상 정답률을 크게 올리기 어렵다.
