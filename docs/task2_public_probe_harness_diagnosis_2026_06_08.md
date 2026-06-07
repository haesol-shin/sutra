# Task 2 Public Probe Harness Diagnosis

- 기준 시각: `2026-06-08T00:00:00+09:00`
- 질문 수: 14
- Task1 label match: 13 / 14 (92.86%)
- Temporal type match: 10 / 14 (71.43%)
- Answered: 0 / 14 (0.00%)
- Fail-closed: 14 / 14 (100.00%)
- Bottlenecks: `{"classifier": 1, "data": 1, "evidence": 2, "retrieval": 2, "temporal": 4, "writer": 4}`

이 결과는 현재 harness의 trace 진단이며 최종 Task 2 성능 claim이 아니다.

| ID | Label | Temporal | Target | Status | Bottleneck | Failure |
| --- | --- | --- | --- | --- | --- | --- |
| public_probe_01 | 0 / 0 | none / none |  | fail_closed | writer | unsupported_url_claim;unsupported_numeric_claim |
| public_probe_02 | 2 / 2 | date_lookup / date_lookup |  | fail_closed | writer | unsupported_url_claim |
| public_probe_03 | 3 / 3 | current_snapshot / current_snapshot | 2026-06-08 | fail_closed | data | current_fact_source_not_official_chain_verified |
| public_probe_04 | 4 / 4 | period_summary / ongoing_status | 2026-06-15~2026-06-21 | fail_closed | temporal | date_filtered_evidence_missing_or_mismatched |
| public_probe_05 | 1 / 1 | none / latest_item |  | fail_closed | temporal | unsupported_url_claim |
| public_probe_06 | 4 / 4 | none / changed_since |  | fail_closed | temporal | unsupported_url_claim |
| public_probe_07 | 2 / 2 | changed_since / changed_since | 2026-05-09~2026-06-08 | fail_closed | evidence | date_filtered_evidence_missing_or_mismatched |
| public_probe_08 | 3 / 3 | period_summary / period_summary | 2026-06-15~2026-06-21 | fail_closed | retrieval | top_score_below_threshold;no_fetchable_registry_candidate |
| public_probe_09 | 1 / 1 | none / latest_item |  | fail_closed | temporal | top_score_below_threshold;controlled_fetch_candidate_exists |
| public_probe_10 | 1 / 0 | none / none |  | fail_closed | classifier | top_score_below_threshold;controlled_fetch_candidate_exists |
| public_probe_11 | 2 / 2 | date_lookup / date_lookup |  | fail_closed | writer | unsupported_url_claim |
| public_probe_12 | 2 / 2 | date_lookup / date_lookup |  | fail_closed | writer | unsupported_url_claim |
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
