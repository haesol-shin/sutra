# Task 2 Probe 39 Harness Diagnosis

- 기준 시각: `2026-06-08T00:00:00+09:00`
- 질문 수: 39
- 도메인 분포: `{"academic_calendar": 9, "dining": 8, "graduation": 7, "notices": 8, "shuttle": 7}`
- Task 1 label match: 38 / 39 (97.44%)
- Temporal type match: 31 / 39 (79.49%)
- Retrieval top1 domain match: 32 / 39 (82.05%)
- Retrieval top3 domain hit: 36 / 39 (92.31%)
- Answered: 31 / 39 (79.49%)
- Fail-closed: 8 / 39 (20.51%)
- Bottlenecks: `{"classifier": 1, "data": 1, "evidence": 5, "none": 25, "temporal": 7}`
- Evidence duplicate doc rate: 0 / 163 (0.00%)
- Evidence fact duplicates: 0
- Evidence scope duplicates: 0
- Answered duplicate rate: 0.00%
- Fail-closed duplicate rate: 0.00%

이 결과는 deterministic harness trace 진단이며 최종 Task 2 성능 claim이 아니다.

| ID | Set | Domain | Label | Temporal | Retrieval | Status | Bottleneck | Failure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| public_probe_01 | public_probe | graduation | 0 / 0 | none / none | top1=True, top3=True | answered | none |  |
| public_probe_02 | public_probe | academic_calendar | 2 / 2 | date_lookup / date_lookup | top1=False, top3=True | answered | none |  |
| public_probe_03 | public_probe | dining | 3 / 3 | current_snapshot / current_snapshot | top1=False, top3=False | answered | none |  |
| public_probe_04 | public_probe | shuttle | 4 / 4 | ongoing_status / ongoing_status | top1=True, top3=True | answered | none |  |
| public_probe_05 | public_probe | notices | 1 / 1 | latest_item / latest_item | top1=True, top3=True | answered | none |  |
| public_probe_06 | public_probe | shuttle | 4 / 4 | none / changed_since | top1=True, top3=True | answered | temporal |  |
| public_probe_07 | public_probe | academic_calendar | 2 / 2 | changed_since / changed_since | top1=True, top3=True | answered | none |  |
| public_probe_08 | public_probe | dining | 3 / 3 | period_summary / period_summary | top1=True, top3=True | fail_closed | evidence | date_filtered_evidence_missing_or_mismatched |
| public_probe_09 | public_probe | notices | 1 / 1 | latest_item / latest_item | top1=True, top3=True | answered | none |  |
| public_probe_10 | public_probe | graduation | 0 / 0 | none / none | top1=False, top3=True | answered | none |  |
| public_probe_11 | public_probe | academic_calendar | 2 / 2 | date_lookup / date_lookup | top1=True, top3=True | answered | none |  |
| public_probe_12 | public_probe | academic_calendar | 2 / 2 | date_lookup / date_lookup | top1=True, top3=True | answered | none |  |
| public_probe_13 | public_probe | dining | 3 / 3 | future_schedule / future_schedule | top1=True, top3=True | fail_closed | evidence | date_filtered_evidence_missing_or_mismatched |
| public_probe_14 | public_probe | notices | 1 / 1 | none / none | top1=True, top3=True | answered | none |  |
| gp001 | generalization_sample | graduation | 0 / 0 | none / none | top1=True, top3=True | answered | none |  |
| gp002 | generalization_sample | graduation | 0 / 0 | none / none | top1=True, top3=True | answered | none |  |
| gp003 | generalization_sample | graduation | 0 / 0 | none / none | top1=True, top3=True | answered | none |  |
| gp004 | generalization_sample | graduation | 0 / 0 | none / none | top1=True, top3=True | answered | none |  |
| gp005 | generalization_sample | graduation | 0 / 0 | none / none | top1=True, top3=True | answered | none |  |
| gp013 | generalization_sample | notices | 1 / 1 | none / current_snapshot | top1=True, top3=True | answered | temporal |  |
| gp014 | generalization_sample | notices | 1 / 1 | latest_item / latest_item | top1=True, top3=True | answered | none |  |
| gp015 | generalization_sample | notices | 1 / 1 | none / latest_item | top1=True, top3=True | fail_closed | temporal | raw_json_or_template_text |
| gp016 | generalization_sample | notices | 1 / 1 | changed_since / changed_since | top1=True, top3=True | fail_closed | evidence | date_filtered_evidence_missing_or_mismatched |
| gp017 | generalization_sample | notices | 1 / 1 | none / date_lookup | top1=True, top3=True | fail_closed | temporal | raw_json_or_template_text |
| gp031 | generalization_sample | academic_calendar | 2 / 2 | date_lookup / date_lookup | top1=False, top3=True | answered | none |  |
| gp032 | generalization_sample | academic_calendar | 2 / 2 | date_lookup / date_lookup | top1=True, top3=True | answered | none |  |
| gp033 | generalization_sample | academic_calendar | 2 / 2 | date_lookup / date_lookup | top1=True, top3=True | answered | none |  |
| gp034 | generalization_sample | academic_calendar | 1 / 2 | none / date_lookup | top1=False, top3=True | answered | classifier |  |
| gp035 | generalization_sample | academic_calendar | 2 / 2 | none / date_lookup | top1=True, top3=True | answered | temporal |  |
| gp043 | generalization_sample | dining | 3 / 3 | current_snapshot / current_snapshot | top1=False, top3=False | answered | none |  |
| gp044 | generalization_sample | dining | 3 / 3 | current_snapshot / current_snapshot | top1=True, top3=True | answered | none |  |
| gp045 | generalization_sample | dining | 3 / 3 | period_summary / period_summary | top1=True, top3=True | fail_closed | evidence | date_filtered_evidence_missing_or_mismatched |
| gp046 | generalization_sample | dining | 3 / 3 | future_schedule / future_schedule | top1=True, top3=True | fail_closed | evidence | date_filtered_evidence_missing_or_mismatched |
| gp047 | generalization_sample | dining | 3 / 3 | current_snapshot / current_snapshot | top1=True, top3=True | fail_closed | data | current_fact_requires_structured_fields |
| gp049 | generalization_sample | shuttle | 4 / 4 | ongoing_status / ongoing_status | top1=True, top3=True | answered | none |  |
| gp050 | generalization_sample | shuttle | 4 / 4 | current_snapshot / current_snapshot | top1=True, top3=True | answered | none |  |
| gp051 | generalization_sample | shuttle | 4 / 4 | current_snapshot / current_snapshot | top1=True, top3=True | answered | none |  |
| gp052 | generalization_sample | shuttle | 4 / 4 | ongoing_status / future_schedule | top1=False, top3=False | answered | temporal |  |
| gp053 | generalization_sample | shuttle | 4 / 4 | none / changed_since | top1=True, top3=True | answered | temporal |  |
