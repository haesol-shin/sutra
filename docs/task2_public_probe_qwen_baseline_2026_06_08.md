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

충남대학교 생화학과 졸업 요건은 입학 연도에 따라 다릅니다.

**2015 학번 이후 (2013 학번 이후 교육과정 적용)**
*   총 이수 학점: **130 학점 이상**
*   세부 구성: 교양 42 학점 + 전공 78 학점 (총 120 학점)
*   주의사항: 교양 과목에서 42 학점을 초과하여 이수한 학점은 졸업 이수 학점에 포함되지 않으므로, 부족한 10 학점은 일반 선택 또는 전공 과목을 초과하여 이수해야 합니다.

**2014 학번 이전**
*   총 이수 학점: **130 학점 이상**
*   세부 구성: 교양 42 학점 + 기초 (9~12 학점) + 전공 81 학점
*   특징: 일선 과목 구분 없이 원하는 과목을 수강하여 130 학점 이상이면 졸업 가능합니다.

※ 학과 및 입학 연도에 따라 기준이 다를 수 있으므로, 정확한 정보는 반드시 **생화학과 사무실**에 문의하거나 공식 홈페이지 ([https://biochemistry.cnu.ac.kr

### 2. 이번 학기 수강신청은 언제 시작하나요?

- id: `public_probe_02`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['academic_calendar_chunk_5', 'academic_calendar_chunk_8', 'academic_calendar_chunk_4']`

2026학년도 제1학기 수강신청은 2026년 2월 2일(월)부터 2월 6일(금)까지 진행됩니다.

참고로, 1월 26일(월)부터 1월 28일(수)까지 예비수강신청이 먼저 열리며, 계절학기 수강신청은 5월 7일(목)부터 5월 11일(월)까지 이루어집니다. 정확한 일정은 충남대학교 공식 학사일정 페이지를 확인하시기 바랍니다.

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

주요 공지사항 목록은 아래 링크를 통해 바로 보실 수 있습니다.
https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr

### 6. 새로 업데이트된 셔틀버스 정류장이 있을까요?

- id: `public_probe_06`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['shuttle_bus_chunk_5', 'shuttle_bus_chunk_2', 'shuttle_bus_chunk_3']`

충남대학교 셔틀버스는 현재 **대덕캠퍼스 내 순환**과 **대덕캠퍼스 ↔ 보운캠퍼스 순환** 두 노선을 운영 중입니다.

*   **대덕캠퍼스 내 순환**: 월평역 등교 시간 08:20 출발
*   **캠퍼스 순환 (대덕 ↔ 보운)**: 골프연습장 출발 시간 08:10

정류장 변경에 대한 최신 정보는 학교 사정에 따라 변동될 수 있으므로, **충남대학교 공식 셔틀버스 안내 페이지**를 확인하시는 것을 권장합니다.

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

제공된 근거에는 '이번 여름 계절학기'의 '종강일'에 대한 구체적인 날짜가 명시되어 있지 않습니다.

참고로 근거 자료에는 하기 계절학기가 6 월 22 일 (월) 에 시작한다는 정보와 동기 계절학기 성적 발표가 1 월 20 일 (화) 에 있다는 정보가 있으나, 여름 계절학기의 종료 시점은 확인되지 않았습니다. 정확한 종강일을 확인하시려면 충남대학교 공식 학사일정 페이지를 다시 한번 확인해 주시기 바랍니다.

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
