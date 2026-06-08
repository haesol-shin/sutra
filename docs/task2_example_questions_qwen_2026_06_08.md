# Task 2 Example Questions Qwen Run

작성일: 2026-06-08

## Run Config

- model: `model/generator/Qwen3.5-9B-Q4_K_M.gguf`
- backend: llama.cpp llama-server
- prompt variant: Task 2 evidence pack + current datetime + ambiguity policy
- run_at: `2026-06-08T00:00:00+09:00`
- claim boundary: sample run, not final performance claim

## Results

### 1. 졸업까지 몇 학점 들어야 하나요?

- group: `assignment_example`
- Task 1 label/domain: `0` / `graduation`
- retrieved_doc_ids: `['graduation_biochemistry_requirements_chunk_6', 'graduation_biochemistry_requirements_chunk_7', 'graduation_biochemistry_requirements_chunk_8']`
- validator_passed: `True`
- elapsed_seconds: `15.58`

Answer:

졸업에 필요한 학점 수는 학과 및 입학 연도에 따라 달라질 수 있습니다. 제공된 정보에는 구체적인 학점 수치가 명시되어 있지 않으므로, 정확한 기준을 확인하시려면 **생화학과 공식 홈페이지** (https://biochemistry.cnu.ac.kr/biochemistry/info/requirements.do) 의 졸업요건 페이지를 참고하시는 것을 권장합니다.

### 2. 이번 학기 수강신청은 언제 시작하나요?

- group: `assignment_example`
- Task 1 label/domain: `2` / `academic_calendar`
- retrieved_doc_ids: `['academic_notice_board_chunk_1', 'academic_notice_board_chunk_2', 'academic_calendar_chunk_1']`
- validator_passed: `False`
- elapsed_seconds: `19.60`

Answer:

2026학년도 제 1 학기 수강신청은 **2026 년 2 월 2 일 (월)부터 2 월 6 일 (금)**까지 진행됩니다.

세부 일정과 변경 사항이 있을 수 있으므로, 최종 확인은 충남대학교 학사정보게시판 또는 공식 학사일정 페이지를 참고하시는 것을 권장합니다.

### 3. 오늘 학식 뭐 나와요?

- group: `assignment_example`
- Task 1 label/domain: `3` / `dining`
- retrieved_doc_ids: `['academic_calendar_chunk_2', 'academic_calendar_chunk_3', 'cnu_mobile_food_chunk_1']`
- validator_passed: `False`
- elapsed_seconds: `25.77`

Answer:

제공된 근거에는 2026 년 6 월 8 일 (일요일) 의 학식 메뉴 정보가 포함되어 있지 않습니다.

근거 3 에 따르면 2026 년 6 월 7 일 (일요일) 의 식단 정보도 '운영안함'으로 표시되어 있어, 해당 기간의 구체적인 메뉴가 공개되지 않았거나 안내되지 않은 것으로 보입니다.

정확한 학식 메뉴를 확인하시려면 충남대학교 공식 식단 안내 페이지 (https://mobileadmin.cnu.ac.kr/food/index.jsp) 를 직접 방문하여 최신 정보를 확인하시기 바랍니다.

### 4. 다음주에 셔틀버스는 정상 운행하나요?

- group: `assignment_example`
- Task 1 label/domain: `4` / `shuttle`
- retrieved_doc_ids: `['shuttle_bus_chunk_1', 'shuttle_bus_chunk_2', 'shuttle_bus_chunk_3']`
- validator_passed: `False`
- elapsed_seconds: `47.56`

Answer:

2026 년 6 월 8 일 (일요일) 기준, **다음 주 (평일)**에는 셔틀버스가 **정상 운행**됩니다.

단, 다음 주의 운영 여부는 학사일정 및 학교 사정에 따라 변경될 수 있으므로, 아래 공식 안내를 참고하시기 바랍니다.

*   **운영 기준**: 학기 중 평일 주간 운영 (평일 야간, 주말, 공휴일, 방학, 수학능력시험일 등 미운영)
*   **주요 노선**: 교내 순환 (대덕캠퍼스 내), 캠퍼스 순환 (대덕캠퍼스 ⇄ 보운캠퍼스)
*   **주의사항**: 운행 시간표는 천재지변, 학교 행사, 교통 상황, 탑승 인원 등에 따라 변경될 수 있으며, 전 구간에서 5 분 내외의 오차가 발생할 수 있습니다.

상세한 운행 시간표와 노선은 [충남대학교 셔틀버스 운영 안내](https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html) 페이지에서 확인하실 수 있습니다.

### 5. 이번에 올라온 공지사항 어디서 볼 수 있어요?

- group: `assignment_example`
- Task 1 label/domain: `1` / `notices`
- retrieved_doc_ids: `['academic_notice_board_chunk_1', 'academic_notice_board_chunk_2', 'graduation_curriculum_pdf_chunk_3']`
- validator_passed: `True`
- elapsed_seconds: `30.29`

Answer:

이번에 올라온 공지사항은 **학사정보게시판**에서 확인하실 수 있습니다.

제공된 정보에 따르면, 2026 학년도 계절학기 수강신청, 출석인정 신청 변경 사항, 휴학 및 복학 안내 등 최신 공지가 게시되어 있습니다. 구체적인 내용은 아래 링크를 통해 확인하실 수 있습니다.

*   **확인 경로**: [충남대학교 학사정보게시판](https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr)

원하시는 특정 학과나 주제에 대한 공지가 있는지 확인해 보시는 것을 추천드립니다.

### 6. 새로 업데이트된 셔틀버스 정류장이 있을까요?

- group: `assignment_example`
- Task 1 label/domain: `4` / `shuttle`
- retrieved_doc_ids: `['shuttle_bus_chunk_2', 'shuttle_bus_chunk_3', 'shuttle_bus_chunk_4']`
- validator_passed: `True`
- elapsed_seconds: `32.36`

Answer:

제공된 근거에는 **새로 업데이트된 셔틀버스 정류장**에 대한 구체적인 정보나 변경 사항이 포함되어 있지 않습니다.

현재 안내된 운행 노선은 다음과 같습니다.
*   **교내 순환 (대덕캠퍼스 내)**
*   **캠퍼스 순환 (대덕캠퍼스 ⇄ 보운캠퍼스)**

정류장 위치나 운행 시간표의 최신 변경 사항이 궁금하시다면, 공식 안내 페이지 ([https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html](https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html)) 를 직접 확인하시는 것을 권장합니다.

### 7. 5월 이후로 변동된 학사일정이 있을까요?

- group: `assignment_example`
- Task 1 label/domain: `2` / `academic_calendar`
- retrieved_doc_ids: `['academic_calendar_chunk_1', 'academic_calendar_chunk_2', 'academic_calendar_chunk_3']`
- validator_passed: `False`
- elapsed_seconds: `35.67`

Answer:

제공된 근거에는 2026 년 5 월 이후의 학사일정 정보가 포함되어 있지 않습니다.

현재 제공된 자료는 2026 년 1 월부터 3 월까지의 제 1 학기 관련 일정 (예비수강신청, 수강신청, 개강 등) 과 2025 년 학기 일정까지의 내용으로 구성되어 있습니다. 5 월 이후의 변동 사항이나 구체적인 일정은 시점에 따라 달라질 수 있으므로, 최신 정보를 확인하시려면 **충남대학교 총장실 홈페이지의 학사일정 메뉴** 또는 아래 공식 링크를 통해 직접 확인하시는 것을 권장합니다.

*   공식 출처: [충남대학교 학사일정](https://plus.cnu.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&site_dvs_cd=kr)

### 8. 다음주 학식 뭐 나와요?

- group: `assignment_example`
- Task 1 label/domain: `3` / `dining`
- retrieved_doc_ids: `['graduation_curriculum_pdf_chunk_5', 'academic_calendar_chunk_2', 'academic_calendar_chunk_3']`
- validator_passed: `False`
- elapsed_seconds: `22.75`

Answer:

제공된 근거에는 다음 주 (2026 년 6 월 8 일 기준) 의 구체적인 학식 메뉴나 운영 일정 정보가 포함되어 있지 않습니다.

학식 메뉴는 계절, 행사, 또는 학기별 계획에 따라 변동될 수 있으므로, 가장 정확한 정보는 **충남대학교 총학생회**나 **각 단과대학 학생회**에서 운영하는 공식 공지 게시판, 혹은 **학식 운영 관련 공식 홈페이지**를 확인하시는 것을 권장합니다.

### 9. 가장 최근에 올라온 공지사항은 언제 게시되었나요?

- group: `assignment_example`
- Task 1 label/domain: `1` / `notices`
- retrieved_doc_ids: `['academic_notice_board_chunk_1', 'academic_notice_board_chunk_2', 'graduation_english_requirements_chunk_7']`
- validator_passed: `False`
- elapsed_seconds: `35.37`

Answer:

제공된 근거에 따르면, 충남대학교 공지사항 게시판에서 가장 최근의 게시물은 **2026 년 6 월 5 일**에 올라온 것입니다.

해당 날짜에 게시된 주요 내용은 다음과 같습니다.
*   **2026 학년도 제 1 학기 수강신청 취소 (1~3 차) 기간 안내** (학사지원과)
*   **[화성시인재육성재단] 2026 년 화성 into 테크노폴 11 기·12 기 해외탐방 장학생 모집 안내** (학생과)

보다 정확한 최신 공지사항이나 추가 정보를 확인하시려면 [충남대학교 공지사항 게시판](https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr)을 직접 방문하여 확인하시기 바랍니다.

### 10. 충남대학교 인공지능학과 24학번의 경우 프로젝트 수업을 몇 개 들어야 하나요?

- group: `user_probe`
- Task 1 label/domain: `1` / `notices`
- retrieved_doc_ids: `['graduation_biochemistry_requirements_chunk_1', 'graduation_english_requirements_chunk_1', 'graduation_english_requirements_chunk_2']`
- validator_passed: `True`
- elapsed_seconds: `20.21`

Answer:

제공된 근거에는 충남대학교 **인공지능학과**의 교육과정 또는 프로젝트 수업 관련 정보가 포함되어 있지 않습니다.

기존 근거는 생화학과 및 영어영문학과 졸업요건에 대한 내용으로, 인공지능학과 24 학번의 구체적인 이수 과목 수를 확인할 수 없습니다. 따라서 정확한 정보는 인공지능학과 공식 홈페이지나 학사정보 공지사항에서 해당 학과의 최신 교육과정을 확인하시기 바랍니다.

### 11. 이번 학기 종강일이 언제인가요?

- group: `user_probe`
- Task 1 label/domain: `2` / `academic_calendar`
- retrieved_doc_ids: `['academic_calendar_chunk_2', 'academic_calendar_chunk_3', 'academic_calendar_chunk_7']`
- validator_passed: `False`
- elapsed_seconds: `28.09`

Answer:

제공된 근거에는 '종강일'에 대한 구체적인 날짜가 명시되어 있지 않습니다.

일반적으로 제 1 학기는 3 월 3 일 (화) 에 개강하며, 제 2 학기는 9 월 1 일 (화) 에 개강합니다. 학기별 정확한 종강일은 매년 학사규정에 따라 달라질 수 있으므로, 충남대학교 공식 학사 일정 페이지 (https://plus.cnu.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&site_dvs_cd=kr) 를 확인하시거나, 소속 학과 사무실 및 학생지원센터에 문의하시는 것을 권장합니다.

### 12. 이번 여름 계절학기 종강일이 언제인 가요?

- group: `user_probe`
- Task 1 label/domain: `2` / `academic_calendar`
- retrieved_doc_ids: `['academic_calendar_chunk_1', 'academic_calendar_chunk_4', 'academic_calendar_chunk_5']`
- validator_passed: `False`
- elapsed_seconds: `23.56`

Answer:

2026 년 하계 계절학기 종강일은 **7 월 20 일 (월)**입니다.

이는 하기 계절학기 성적발표 일자로, 해당 일자에 성적표가 발표됨을 의미합니다. 다만, 세부 일정은 시점에 따라 달라질 수 있으므로 충남대학교 공식 학사일정 (https://plus.cnu.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&site_dvs_cd=kr) 을 최종 확인하시기 바랍니다.

### 13. 다음주 화요일 2학생회관 메뉴가 어떻게 되나요?

- group: `user_probe`
- Task 1 label/domain: `3` / `dining`
- retrieved_doc_ids: `['cnu_mobile_food_chunk_1', 'cnu_mobile_food_chunk_2', 'cnu_mobile_food_chunk_3']`
- validator_passed: `False`
- elapsed_seconds: `23.14`

Answer:

제공된 근거에는 2026 년 6 월 8 일 기준 '다음 주 화요일'의 메뉴 정보가 포함되어 있지 않습니다. 현재 확인 가능한 정보는 6 월 7 일 (일요일) 의 식단이며, 해당 날짜에도 2 학생회관의 조식, 중식, 석식 모두 '운영안함'으로 안내되어 있습니다.

다음 주 화요일의 정확한 메뉴는 시점에 따라 변동될 수 있으므로, 충남대학교 공식 식단 홈페이지 (https://mobileadmin.cnu.ac.kr/food/index.jsp) 를 통해 최신 정보를 확인하시기 바랍니다.

### 14. 토익 장학금을 받으려면 성적이 몇 점 이상이어야 하나요?

- group: `user_probe`
- Task 1 label/domain: `1` / `notices`
- retrieved_doc_ids: `['graduation_biochemistry_requirements_chunk_1', 'graduation_english_requirements_chunk_4', 'graduation_english_requirements_chunk_5']`
- validator_passed: `False`
- elapsed_seconds: `18.44`

Answer:

제공된 근거에는 토익 장학금의 구체적인 성적 기준 (예: 800 점 이상 등) 이 명시되어 있지 않습니다.

일반적으로 토익 장학금은 학교 또는 학과별 장학제도 내규에 따라 정해지며, 학과와 입학 연도에 따라 기준이 다를 수 있습니다. 정확한 점수 요건과 신청 방법을 확인하시려면 **충남대학교 공식 홈페이지의 학사정보 또는 해당 학과 장학제도 페이지**를 참고하시기 바랍니다.

