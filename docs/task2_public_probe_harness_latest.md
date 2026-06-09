# Task 2 Public Probe Harness Diagnosis

- 기준 시각: `2026-06-08T00:00:00+09:00`
- 질문 수: 14
- Task1 label match: 14 / 14 (100.00%)
- Temporal type match: 13 / 14 (92.86%)
- Answered: 13 / 14 (92.86%)
- Fail-closed: 1 / 14 (7.14%)
- Bottlenecks: `{"none": 12, "temporal": 1, "writer": 1}`

이 결과는 현재 harness의 trace 진단이며 최종 Task 2 성능 claim이 아니다.

| ID | Label | Temporal | Target | Status | Bottleneck | Failure |
| --- | --- | --- | --- | --- | --- | --- |
| public_probe_01 | 0 / 0 | none / none |  | fail_closed | writer | raw_json_or_template_text |
| public_probe_02 | 2 / 2 | date_lookup / date_lookup |  | answered | none |  |
| public_probe_03 | 3 / 3 | current_snapshot / current_snapshot | 2026-06-08 | answered | none |  |
| public_probe_04 | 4 / 4 | ongoing_status / ongoing_status | 2026-06-15~2026-06-21 | answered | none |  |
| public_probe_05 | 1 / 1 | latest_item / latest_item |  | answered | none |  |
| public_probe_06 | 4 / 4 | none / changed_since |  | answered | temporal |  |
| public_probe_07 | 2 / 2 | changed_since / changed_since | 2026-05-09~2026-06-08 | answered | none |  |
| public_probe_08 | 3 / 3 | period_summary / period_summary | 2026-06-15~2026-06-21 | answered | none |  |
| public_probe_09 | 1 / 1 | latest_item / latest_item |  | answered | none |  |
| public_probe_10 | 0 / 0 | none / none |  | answered | none |  |
| public_probe_11 | 2 / 2 | date_lookup / date_lookup |  | answered | none |  |
| public_probe_12 | 2 / 2 | date_lookup / date_lookup |  | answered | none |  |
| public_probe_13 | 3 / 3 | future_schedule / future_schedule | 2026-06-16 | answered | none |  |
| public_probe_14 | 1 / 1 | none / none |  | answered | none |  |

## Bottleneck Legend

- `classifier`: Task 1 label이 기대값과 다르다.
- `temporal`: temporal type이 기대값과 다르다.
- `retrieval`: 검색 결과가 없거나 score가 낮아 근거 pack을 만들 수 없다.
- `data`: controlled fetch/source registry/공식성/구조화 데이터가 부족하다.
- `evidence`: 검색은 됐지만 날짜/근거 충분성 검사를 통과하지 못했다.
- `writer`: 답변 생성 후 validator에서 막혔다.
- `none`: 현재 trace 기준으로 harness 병목이 없다.
