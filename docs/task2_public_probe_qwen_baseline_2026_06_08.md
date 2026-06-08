# Task 2 Public Probe Qwen Baseline

- 기준 시각: `2026-06-08T00:00:00+09:00`
- writer backend: `llama_server`
- 질문 수: 14
- Task1 label match: 13 / 14 (92.86%)
- Temporal type match: 10 / 14 (71.43%)
- Answered: 6 / 14 (42.86%)
- Fail-closed: 8 / 14 (57.14%)
- Qwen writer called: 6 / 14
- Writer-called but blocked: 0
- Bottlenecks: `{"classifier": 1, "data": 1, "evidence": 1, "none": 4, "retrieval": 3, "temporal": 4}`

이 결과는 현재 harness를 통과한 Qwen writer baseline이며 최종 Task 2 성능 claim이 아니다.

| ID | Label | Temporal | Status | Writer | Bottleneck | Failure |
| --- | --- | --- | --- | --- | --- | --- |
| public_probe_01 | 0 / 0 | none / none | answered | yes | none |  |
| public_probe_02 | 2 / 2 | date_lookup / date_lookup | answered | yes | none |  |
| public_probe_03 | 3 / 3 | current_snapshot / current_snapshot | fail_closed | no | data | current_fact_source_not_official_chain_verified |
| public_probe_04 | 4 / 4 | period_summary / ongoing_status | fail_closed | no | temporal | date_filtered_evidence_missing_or_mismatched |
| public_probe_05 | 1 / 1 | none / latest_item | answered | yes | temporal |  |
| public_probe_06 | 4 / 4 | none / changed_since | answered | yes | temporal |  |
| public_probe_07 | 2 / 2 | changed_since / changed_since | fail_closed | no | retrieval | top_score_below_threshold;controlled_fetch_candidate_exists |
| public_probe_08 | 3 / 3 | period_summary / period_summary | fail_closed | no | retrieval | top_score_below_threshold;no_fetchable_registry_candidate |
| public_probe_09 | 1 / 1 | none / latest_item | fail_closed | no | temporal | top_score_below_threshold;controlled_fetch_candidate_exists |
| public_probe_10 | 1 / 0 | none / none | fail_closed | no | classifier | top_score_below_threshold;controlled_fetch_candidate_exists |
| public_probe_11 | 2 / 2 | date_lookup / date_lookup | answered | yes | none |  |
| public_probe_12 | 2 / 2 | date_lookup / date_lookup | answered | yes | none |  |
| public_probe_13 | 3 / 3 | future_schedule / future_schedule | fail_closed | no | evidence | date_filtered_evidence_missing_or_mismatched |
| public_probe_14 | 1 / 1 | none / none | fail_closed | no | retrieval | top_score_below_threshold;controlled_fetch_candidate_exists |

## Answers

### 1. 졸업까지 몇 학점 들어야 하나요?

- id: `public_probe_01`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['graduation_biochemistry_requirements_chunk_5', 'graduation_biochemistry_requirements_chunk_7', 'graduation_biochemistry_requirements_chunk_6']`

충남대학교 생화학과 졸업 이수 학점은 입학 연도에 따라 기준이 다릅니다.

**2014 학번 이후 학생**의 경우, 교양 (42 학점 이상) 과 전공 (78 학점 이상) 을 이수한 후에도 총 130 학점에 미치지 못하면 **일반선택**이나 **전공 초과** 과목을 통해 부족한 학점을 채워야 합니다. 특히 2015 학번 이후 학생들은 교양 과목의 일선 (1 선) 구분과 전공 심화/핵심 과목의 초과 이수를 주의해야 합니다.

**2014 학번 이전 학생**의 경우, 교양 (42 학점) + 기초 (9~12 학점) + 전공 (81 학점) 으로 총 130 학점 이상을 이수하면 되며, 초과된 학점은 자동으로 인정됩니다.

※ 편입생은 본교 과목 중복 이수를 주의해야 하며, 직전계절학기 인턴쉽 학점은 인정되지 않습니다. 정확한 기준은 본인의 입학 연도와 학과 사무실 공식 안내를 확인하시기 바랍니다.

### 2. 이번 학기 수강신청은 언제 시작하나요?

- id: `public_probe_02`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['academic_calendar_chunk_5', 'academic_calendar_chunk_8', 'academic_calendar_chunk_4']`

2026학년도 제1학기 수강신청은 **2026년 2월 2일 (월)부터 2월 6일 (금)**까지 진행됩니다.

참고로, 1월 26일 (월)부터 1월 28일 (수)까지 예비수강신청이 먼저 이루어지며, 계절학기 수강신청은 5월 7일 (목)부터 5월 11일 (월)까지 있습니다. 정확한 일정은 학교 공식 학사일정 페이지를 통해 확인하시는 것이 좋습니다.

### 3. 오늘 학식 뭐 나와요?

- id: `public_probe_03`
- status: `fail_closed`
- qwen_writer_called: `False`
- retrieved_doc_ids: `['cnu_mobile_food_chunk_1', 'cnu_mobile_food_chunk_2', 'cnu_mobile_food_chunk_3']`

공식 근거가 충분하지 않아 확답하기 어렵습니다. 충남대학교 공식 출처를 기준으로 다시 확인해 주세요.

### 4. 다음주에 셔틀버스는 정상 운행하나요?

- id: `public_probe_04`
- status: `fail_closed`
- qwen_writer_called: `False`
- retrieved_doc_ids: `['shuttle_bus_chunk_1', 'shuttle_bus_chunk_2', 'shuttle_bus_chunk_3', 'shuttle_bus_chunk_4', 'shuttle_bus_chunk_5', 'shuttle_bus_chunk_6', 'shuttle_bus_chunk_7', 'shuttle_bus_chunk_8']`

공식 근거가 충분하지 않아 확답하기 어렵습니다. 충남대학교 공식 출처를 기준으로 다시 확인해 주세요.

### 5. 이번에 올라온 공지사항 어디서 볼 수 있어요?

- id: `public_probe_05`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['academic_notice_board_chunk_1', 'academic_notice_board_chunk_2']`

충남대학교 공지사항은 **학사정보게시판**에서 확인하실 수 있습니다.

제공된 근거에 따르면, 2026학년도 계절학기 수강신청, 출석인정 신청 변경 사항, 휴학 및 복학 안내 등 최신 학사 관련 공지들이 게시되어 있습니다. 해당 게시판의 직접적인 접속 링크는 다음과 같습니다.

*   **공지사항 주소**: https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr

### 6. 새로 업데이트된 셔틀버스 정류장이 있을까요?

- id: `public_probe_06`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['shuttle_bus_chunk_5', 'shuttle_bus_chunk_2', 'shuttle_bus_chunk_3']`

충남대학교 셔틀버스는 현재 **교내 순환** (대덕캠퍼스 내) 과 **캠퍼스 순환** (대덕캠퍼스⇄보운캠퍼스) 두 노선을 운영 중입니다.

*   **교내 순환**: 월평역 등교 08:20 출발
*   **캠퍼스 순환**: 골프연습장 출발 08:10, 보운캠퍼스 회차 08:50

정류장 위치나 운행 시간은 학교 사정, 천재지변, 교통 상황 등에 따라 변경될 수 있으므로, 최신 정보는 **충남대학교 공식 셔틀버스 안내 페이지** (https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html) 를 확인하시는 것이 좋습니다.

### 7. 5월 이후로 변동된 학사일정이 있을까요?

- id: `public_probe_07`
- status: `fail_closed`
- qwen_writer_called: `False`
- retrieved_doc_ids: `['academic_calendar_chunk_1', 'academic_calendar_chunk_2', 'academic_calendar_chunk_3', 'academic_calendar_chunk_4', 'academic_calendar_chunk_5', 'academic_calendar_chunk_6', 'academic_calendar_chunk_7', 'academic_calendar_chunk_8']`

공식 근거가 충분하지 않아 확답하기 어렵습니다. 충남대학교 공식 출처를 기준으로 다시 확인해 주세요.

### 8. 다음주 학식 뭐 나와요?

- id: `public_probe_08`
- status: `fail_closed`
- qwen_writer_called: `False`
- retrieved_doc_ids: `['cnu_mobile_food_chunk_1', 'cnu_mobile_food_chunk_2', 'cnu_mobile_food_chunk_3']`

공식 근거가 충분하지 않아 확답하기 어렵습니다. 충남대학교 공식 출처를 기준으로 다시 확인해 주세요.

### 9. 가장 최근에 올라온 공지사항은 언제 게시되었나요?

- id: `public_probe_09`
- status: `fail_closed`
- qwen_writer_called: `False`
- retrieved_doc_ids: `['academic_notice_board_chunk_1', 'academic_notice_board_chunk_2']`

공식 근거가 충분하지 않아 확답하기 어렵습니다. 충남대학교 공식 출처를 기준으로 다시 확인해 주세요.

### 10. 충남대학교 인공지능학과 24학번의 경우 프로젝트 수업을 몇 개 들어야 하나요?

- id: `public_probe_10`
- status: `fail_closed`
- qwen_writer_called: `False`
- retrieved_doc_ids: `['academic_notice_detail_2512782_chunk_2']`

공식 근거가 충분하지 않아 확답하기 어렵습니다. 충남대학교 공식 출처를 기준으로 다시 확인해 주세요.

### 11. 이번 학기 종강일이 언제인가요?

- id: `public_probe_11`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['academic_calendar_chunk_7', 'academic_calendar_chunk_1', 'academic_calendar_chunk_2', 'academic_calendar_chunk_3', 'academic_calendar_chunk_4']`

제공된 근거에는 이번 학기 (제 1 학기) 의 종강일 정보가 포함되어 있지 않습니다.

충남대학교 공식 학사일정 페이지 (https://plus.cnu.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&site_dvs_cd=kr) 를 통해 정확한 날짜를 확인하시기 바랍니다.

### 12. 이번 여름 계절학기 종강일이 언제인 가요?

- id: `public_probe_12`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['academic_calendar_chunk_2', 'academic_calendar_chunk_8', 'academic_calendar_chunk_9', 'academic_calendar_chunk_7', 'academic_calendar_chunk_1']`

제공된 근거에는 계절학기 **종강일**에 대한 명시적인 정보가 포함되어 있지 않습니다.

근거 3 에 따르면 하기 계절학기는 **6 월 22 일 (월) ~ 7 월 10 일 (금)**로 운영되며, 7 월 10 일이 마지막 수업일일 가능성이 높지만 정확한 종강일은 공식 출처를 통해 다시 확인하시는 것을 권장합니다.

### 13. 다음주 화요일 2학생회관 메뉴가 어떻게 되나요?

- id: `public_probe_13`
- status: `fail_closed`
- qwen_writer_called: `False`
- retrieved_doc_ids: `['cnu_mobile_food_chunk_1', 'cnu_mobile_food_chunk_2', 'cnu_mobile_food_chunk_3']`

공식 근거가 충분하지 않아 확답하기 어렵습니다. 충남대학교 공식 출처를 기준으로 다시 확인해 주세요.

### 14. 토익 장학금을 받으려면 성적이 몇 점 이상이어야 하나요?

- id: `public_probe_14`
- status: `fail_closed`
- qwen_writer_called: `False`
- retrieved_doc_ids: `['academic_notice_detail_2512782_chunk_1']`

공식 근거가 충분하지 않아 확답하기 어렵습니다. 충남대학교 공식 출처를 기준으로 다시 확인해 주세요.
