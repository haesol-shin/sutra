# Task 2 Probe 39 Harness Diagnosis

- 기준 시각: `2026-06-08T00:00:00+09:00`
- 질문 수: 39
- 도메인 분포: `{"academic_calendar": 9, "dining": 8, "graduation": 7, "notices": 8, "shuttle": 7}`
- Task 1 label match: 32 / 39 (82.05%)
- Temporal type match: 30 / 39 (76.92%)
- Retrieval top1 domain match: 27 / 39 (69.23%)
- Retrieval top3 domain hit: 28 / 39 (71.79%)
- Answered: 25 / 39 (64.10%)
- Fail-closed: 14 / 39 (35.90%)
- Bottlenecks: `{"classifier": 7, "data": 4, "evidence": 3, "none": 17, "retrieval": 4, "temporal": 4}`

이 결과는 deterministic harness trace 진단이며 최종 Task 2 성능 claim이 아니다.

| ID | Set | Domain | Label | Temporal | Retrieval | Status | Bottleneck | Failure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| public_probe_01 | public_probe | graduation | 0 / 0 | none / none | top1=True, top3=True | answered | none |  |
| public_probe_02 | public_probe | academic_calendar | 2 / 2 | date_lookup / date_lookup | top1=False, top3=False | answered | none |  |
| public_probe_03 | public_probe | dining | 3 / 3 | current_snapshot / current_snapshot | top1=False, top3=False | fail_closed | data | current_fact_source_not_official_chain_verified |
| public_probe_04 | public_probe | shuttle | 4 / 4 | ongoing_status / ongoing_status | top1=True, top3=True | answered | none |  |
| public_probe_05 | public_probe | notices | 1 / 1 | latest_item / latest_item | top1=True, top3=True | answered | none |  |
| public_probe_06 | public_probe | shuttle | 4 / 4 | none / changed_since | top1=True, top3=True | answered | temporal |  |
| public_probe_07 | public_probe | academic_calendar | 2 / 2 | changed_since / changed_since | top1=True, top3=True | fail_closed | evidence | date_filtered_evidence_missing_or_mismatched |
| public_probe_08 | public_probe | dining | 3 / 3 | period_summary / period_summary | top1=False, top3=False | fail_closed | retrieval | no_retrieved_docs;controlled_fetch_candidate_exists |
| public_probe_09 | public_probe | notices | 1 / 1 | latest_item / latest_item | top1=True, top3=True | answered | none |  |
| public_probe_10 | public_probe | graduation | 1 / 0 | none / none | top1=False, top3=False | answered | classifier |  |
| public_probe_11 | public_probe | academic_calendar | 2 / 2 | date_lookup / date_lookup | top1=True, top3=True | answered | none |  |
| public_probe_12 | public_probe | academic_calendar | 2 / 2 | date_lookup / date_lookup | top1=False, top3=False | fail_closed | retrieval | no_retrieved_docs;controlled_fetch_candidate_exists |
| public_probe_13 | public_probe | dining | 3 / 3 | future_schedule / future_schedule | top1=True, top3=True | fail_closed | evidence | date_filtered_evidence_missing_or_mismatched |
| public_probe_14 | public_probe | notices | 1 / 1 | none / none | top1=True, top3=True | answered | none |  |
| gp001 | generalization_sample | graduation | 0 / 0 | none / none | top1=True, top3=True | answered | none |  |
| gp002 | generalization_sample | graduation | 0 / 0 | none / none | top1=True, top3=True | answered | none |  |
| gp003 | generalization_sample | graduation | 0 / 0 | none / none | top1=True, top3=True | answered | none |  |
| gp004 | generalization_sample | graduation | 0 / 0 | none / none | top1=True, top3=True | answered | none |  |
| gp005 | generalization_sample | graduation | 0 / 0 | none / none | top1=True, top3=True | answered | none |  |
| gp013 | generalization_sample | notices | 0 / 1 | none / current_snapshot | top1=True, top3=True | answered | classifier |  |
| gp014 | generalization_sample | notices | 0 / 1 | none / latest_item | top1=True, top3=True | fail_closed | classifier | no_retrieved_docs;controlled_fetch_candidate_exists |
| gp015 | generalization_sample | notices | 0 / 1 | none / latest_item | top1=True, top3=True | fail_closed | classifier | no_retrieved_docs;controlled_fetch_candidate_exists |
| gp016 | generalization_sample | notices | 0 / 1 | changed_since / changed_since | top1=False, top3=False | fail_closed | classifier | date_filtered_evidence_missing_or_mismatched |
| gp017 | generalization_sample | notices | 0 / 1 | none / date_lookup | top1=True, top3=True | answered | classifier |  |
| gp031 | generalization_sample | academic_calendar | 2 / 2 | date_lookup / date_lookup | top1=False, top3=False | answered | none |  |
| gp032 | generalization_sample | academic_calendar | 2 / 2 | date_lookup / date_lookup | top1=True, top3=True | answered | none |  |
| gp033 | generalization_sample | academic_calendar | 2 / 2 | date_lookup / date_lookup | top1=False, top3=False | fail_closed | retrieval | no_retrieved_docs;controlled_fetch_candidate_exists |
| gp034 | generalization_sample | academic_calendar | 1 / 2 | none / date_lookup | top1=False, top3=False | answered | classifier |  |
| gp035 | generalization_sample | academic_calendar | 2 / 2 | none / date_lookup | top1=False, top3=True | answered | temporal |  |
| gp043 | generalization_sample | dining | 3 / 3 | current_snapshot / current_snapshot | top1=False, top3=False | fail_closed | data | current_fact_source_not_official_chain_verified |
| gp044 | generalization_sample | dining | 3 / 3 | current_snapshot / current_snapshot | top1=True, top3=True | fail_closed | data | current_fact_source_not_official_chain_verified |
| gp045 | generalization_sample | dining | 3 / 3 | period_summary / period_summary | top1=False, top3=False | fail_closed | retrieval | no_retrieved_docs;controlled_fetch_candidate_exists |
| gp046 | generalization_sample | dining | 3 / 3 | future_schedule / future_schedule | top1=True, top3=True | fail_closed | evidence | date_filtered_evidence_missing_or_mismatched |
| gp047 | generalization_sample | dining | 3 / 3 | current_snapshot / current_snapshot | top1=True, top3=True | fail_closed | data | current_fact_source_not_official_chain_verified |
| gp049 | generalization_sample | shuttle | 4 / 4 | ongoing_status / ongoing_status | top1=True, top3=True | answered | none |  |
| gp050 | generalization_sample | shuttle | 4 / 4 | current_snapshot / current_snapshot | top1=True, top3=True | answered | none |  |
| gp051 | generalization_sample | shuttle | 4 / 4 | current_snapshot / current_snapshot | top1=True, top3=True | answered | none |  |
| gp052 | generalization_sample | shuttle | 4 / 4 | ongoing_status / future_schedule | top1=True, top3=True | answered | temporal |  |
| gp053 | generalization_sample | shuttle | 4 / 4 | none / changed_since | top1=True, top3=True | answered | temporal |  |
