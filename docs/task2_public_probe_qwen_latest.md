# Task 2 Public Probe Qwen Baseline

- 기준 시각: `2026-06-08T00:00:00+09:00`
- writer backend: `llama_server`
- 질문 수: 14
- Task1 label match: 14 / 14 (100.00%)
- Temporal type match: 13 / 14 (92.86%)
- Answered: 14 / 14 (100.00%)
- Fail-closed: 0 / 14 (0.00%)
- Qwen writer called: 14 / 14
- Writer-called but blocked: 0
- Bottlenecks: `{"none": 13, "temporal": 1}`

이 결과는 현재 harness를 통과한 Qwen writer baseline이며 최종 Task 2 성능 claim이 아니다.

| ID | Label | Temporal | Status | Writer | Bottleneck | Failure |
| --- | --- | --- | --- | --- | --- | --- |
| public_probe_01 | 0 / 0 | none / none | answered | yes | none |  |
| public_probe_02 | 2 / 2 | date_lookup / date_lookup | answered | yes | none |  |
| public_probe_03 | 3 / 3 | current_snapshot / current_snapshot | answered | yes | none |  |
| public_probe_04 | 4 / 4 | ongoing_status / ongoing_status | answered | yes | none |  |
| public_probe_05 | 1 / 1 | latest_item / latest_item | answered | yes | none |  |
| public_probe_06 | 4 / 4 | none / changed_since | answered | yes | temporal |  |
| public_probe_07 | 2 / 2 | changed_since / changed_since | answered | yes | none |  |
| public_probe_08 | 3 / 3 | period_summary / period_summary | answered | yes | none |  |
| public_probe_09 | 1 / 1 | latest_item / latest_item | answered | yes | none |  |
| public_probe_10 | 0 / 0 | none / none | answered | yes | none |  |
| public_probe_11 | 2 / 2 | date_lookup / date_lookup | answered | yes | none |  |
| public_probe_12 | 2 / 2 | date_lookup / date_lookup | answered | yes | none |  |
| public_probe_13 | 3 / 3 | future_schedule / future_schedule | answered | yes | none |  |
| public_probe_14 | 1 / 1 | none / none | answered | yes | none |  |

## Answers

### 1. 졸업까지 몇 학점 들어야 하나요?

- id: `public_probe_01`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['academic_notice_board_page_2__notice_board_item__1799__2026-05-18__졸업생_취업_특화_취업_실패_원인_진단_취업_나침반_안내__452575b4ea', 'graduation_english_requirements_chunk_6', 'graduation_english_requirements_chunk_7', 'academic_calendar__academic_calendar_event__2026__2026-03-30__2026-04-03__2025학년도_후기_조기졸업_신청__24__59399878cb', 'academic_calendar__academic_calendar_event__2026__2026-09-30__2026-10-07__2026학년도_전기_조기졸업_신청__57__b8b95283a9', 'academic_calendar_2023__academic_calendar_event__2023__2023-04-03__2023-04-07__조기_졸업신청__24__e0db30b228', 'academic_calendar_2023__academic_calendar_event__2023__2023-10-04__2023-10-11__조기졸업_신청__59__5c6b48d374', 'academic_calendar_2024__academic_calendar_event__2024__2024-04-01__2024-04-05__조기졸업_신청__23__0783c3d44d']`

충남대학교 졸업에 필요한 학점은 **입학 연도 및 학과에 따라 기준이 다릅니다.**

제공된 정보에 따르면, **영어영문학과**의 경우 2015, 2016 년 입학생 기준 **총 130 학점**이 필요하며, 이 중 교양학점은 최소 36 학점 이상 이수해야 합니다.

다른 학과나 다른 입학 연도의 기준은 각 학과 교육과정 또는 입학년도별 졸업요건 규정에 따라 상이할 수 있으므로, 정확한 학점 수치는 소속 학과의 공식 홈페이지나 학생지원센터에서 확인하시는 것이 좋습니다.

### 2. 이번 학기 수강신청은 언제 시작하나요?

- id: `public_probe_02`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['academic_notice_board__notice_board_item__1814__2026-06-05__2026학년도_하기_계절학기_수강신청_취소13차기간_안내__d93ad5b0e1', 'academic_notice_board_page_4__notice_board_item__1785__2026-05-04__2026학년도_하기_계절학기_수강신청_안내__9ee75f360e', 'academic_calendar__academic_calendar_event__2026__2026-02-02__2026-02-06__2026학년도_제1학기_수강신청__9__8a0295927b', 'academic_calendar__academic_calendar_event__2026__2026-05-07__2026-05-11__하기_계절학기_수강신청__29__b9e6bbac63', 'academic_calendar__academic_calendar_event__2026__2026-08-03__2026-08-07__제2학기_수강신청__42__fe2aecb134', 'academic_calendar__academic_calendar_event__2026__2026-11-05__2026-11-10__동기_계절학기_수강신청__63__6b6e442bf4', 'academic_calendar_2023__academic_calendar_event__2023__2023-05-10__2023-05-12__하기_계절학기_수강신청__30__52b0861610', 'academic_calendar_2023__academic_calendar_event__2023__2023-11-08__2023-11-10__동기_계절학기_수강신청__64__ff38e1ada5']`

2026학년도 하기 계절학기 수강신청은 2026년 5월 7일부터 5월 11일까지 진행됩니다.

### 3. 오늘 학식 뭐 나와요?

- id: `public_probe_03`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['academic_calendar__academic_calendar_event__2026__2026-02-27__2026-02-27__입학식2026학년도__13__2d6f71eb70', 'academic_calendar_2023__academic_calendar_event__2023__2023-02-28__2023-02-28__2023학년도_입학식__15__fb3d8e6e41', 'academic_calendar_2024__academic_calendar_event__2024__2024-02-28__2024-02-28__입학식2024년도__14__f03d27e054', 'academic_calendar_2025__academic_calendar_event__2025__2025-02-28__2025-02-28__입학식2025학년도__14__57dcb9ae22', 'cnu_mobile_food__dining_menu__2026-06-08__제1학생회관__조식__직원__1__de7b35a625', 'cnu_mobile_food__dining_menu__2026-06-08__제2학생회관__조식__직원__2__256ddf0c67', 'cnu_mobile_food__dining_menu__2026-06-08__제3학생회관__조식__직원__3__b838af6db9', 'cnu_mobile_food__dining_menu__2026-06-08__제4학생회관__조식__직원__4__c62f6984a8']`

오늘 (2026-06-08) 학식 메뉴는 학생회관에 따라 다릅니다.

*   **제 1 학생회관**: 조식 메뉴가 운영되고 있습니다.
*   **제 2, 3, 4 학생회관**: 조식 메뉴는 운영되지 않습니다.

상세한 메뉴 내용은 [제 1 학생회관 조식 메뉴 운영 내역](https://mobileadmin.cnu.ac.kr/food/index.jsp) 에서 확인하실 수 있습니다.

### 4. 다음주에 셔틀버스는 정상 운행하나요?

- id: `public_probe_04`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['shuttle_bus__shuttle_route__campus_loop__2026-03-03__2026-06-21__2a184c34ae', 'shuttle_bus__shuttle_route__intercampus_loop__2026-03-03__2026-06-21__4b1ebb50cb', 'shuttle_bus__shuttle_segment__campus_loop__departure_time__0820_월평역_등교__1__2026-03-03__2026-06-21__44bb3f901c', 'shuttle_bus__shuttle_segment__campus_loop__departure_time__0830__2__2026-03-03__2026-06-21__f73ccdf144', 'shuttle_bus__shuttle_segment__campus_loop__departure_time__0930__3__2026-03-03__2026-06-21__3763c72372', 'shuttle_bus__shuttle_segment__campus_loop__departure_time__0940__4__2026-03-03__2026-06-21__ee150ffdeb', 'shuttle_bus__shuttle_segment__campus_loop__departure_time__1030__5__2026-03-03__2026-06-21__b8c9ea767e', 'shuttle_bus__shuttle_segment__campus_loop__departure_time__1130__6__2026-03-03__2026-06-21__f81a656625']`

다음주 (2026.06.15~06.21) 는 학기 중 평일 주간이므로 셔틀버스가 정상 운행됩니다.

*   **교내 순환**: 평일 등교 시간 (08:20~17:30) 에 운행하며, 정심화 국제문화회관, 사회과학대학 입구, 학생생활관 3거리, 농업생명과학대학 앞 등 주요 정류장을 지나갑니다.
*   **캠퍼스 순환**: 평일 등교 시간 (08:10~08:50) 에 운행하며, 중앙도서관, 제2학생회관, 월평역 등을 연결합니다.

주말, 공휴일, 평일 야간 및 방학 기간에는 운행하지 않습니다.

### 5. 이번에 올라온 공지사항 어디서 볼 수 있어요?

- id: `public_probe_05`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['academic_notice_board__notice_board_item__공지__2026-03-05__2026학년도_제1학기_학생_출석인정_신청_변경_사항_안내__4898d48afa', 'graduation_energy_requirements_chunk_1', 'graduation_energy_requirements_chunk_2', 'graduation_energy_requirements_chunk_3', 'graduation_law_requirements_chunk_2', 'graduation_law_requirements_chunk_3', 'graduation_law_requirements_chunk_5', 'graduation_law_requirements_chunk_6']`

이번에 올라온 공지사항은 **충남대학교 포털 (plus.cnu.ac.kr)**의 **'공지사항'** 메뉴에서 확인하실 수 있습니다.

현재 기준 (2026 년 6 월 8 일) 으로 가장 최근에 게시된 공지사항은 **2026 년 3 월 5 일**에 학사지원과에서 발표한 **'2026 학년도 제 1 학기 학생 출석인정 신청 변경 사항 안내'**입니다.

다른 학과별 공지사항 (예: 에너지공학과, 법학과 등) 은 해당 학과 홈페이지의 공지사항 또는 포털 내 해당 학과 메뉴에서 확인하실 수 있습니다.

### 6. 새로 업데이트된 셔틀버스 정류장이 있을까요?

- id: `public_probe_06`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['shuttle_bus__shuttle_segment__intercampus_loop__stop__충남대학교입구_버스정류장__4__2026-03-03__2026-06-21__a033ca4244', 'shuttle_bus__shuttle_segment__campus_loop__stop__정심화_국제문화회관__1__2026-03-03__2026-06-21__1c357c6234', 'shuttle_bus__shuttle_segment__campus_loop__stop__사회과_학대학_입구__2__2026-03-03__2026-06-21__f4f636ba5c', 'shuttle_bus__shuttle_segment__campus_loop__stop__서문__3__2026-03-03__2026-06-21__e53154b4f1', 'shuttle_bus__shuttle_segment__campus_loop__stop__음악_2호관_앞__4__2026-03-03__2026-06-21__0d58319899', 'shuttle_bus__shuttle_segment__campus_loop__stop__공동동물실험센터__5__2026-03-03__2026-06-21__798fbcd070', 'shuttle_bus__shuttle_segment__campus_loop__stop__체_육관_입구__6__2026-03-03__2026-06-21__b702aa0908', 'shuttle_bus__shuttle_segment__campus_loop__stop__예술대학_앞__7__2026-03-03__2026-06-21__a9cc6d6d82']`

2026학년도 셔틀버스 정류장 정보는 2026 년 3 월 3 일부터 6 월 21 일까지 적용됩니다.

**[교내 순환 정류장]**
*   서문
*   음악 2 호관 앞
*   공동동물실험센터
*   체 육관 입구
*   예술대학 앞
*   사회과 학대학 입구

**[캠퍼스 순환 정류장]**
*   충남대학교입구 버스정류장

*참고: 세부 정보는 시점에 따라 달라질 수 있으므로 공식 출처를 기준으로 확인하시기 바랍니다.*

### 7. 5월 이후로 변동된 학사일정이 있을까요?

- id: `public_probe_07`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['academic_calendar__academic_calendar_monthly__2026__05', 'academic_calendar_2023__academic_calendar_monthly__2023__05', 'academic_calendar_2024__academic_calendar_monthly__2024__05', 'academic_calendar_2025__academic_calendar_monthly__2025__05', 'academic_calendar__academic_calendar_monthly__2026__01', 'academic_calendar__academic_calendar_monthly__2026__02', 'academic_calendar__academic_calendar_monthly__2026__03', 'academic_calendar__academic_calendar_monthly__2026__04']`

2026학년도 5월 학사일정은 다음과 같습니다.

*   **2026-05-01**: 노동절
*   **2026-05-05**: 어린이날
*   **2026-05-07~2026-05-11**: 하기 계절학기 수강신청
*   **2026-05-13**: 수업일수 2/3선
*   **2026-05-22**: 수업일수 3/4선
*   **2026-05-24**: 부처님오신날
*   **2026-05-25**: 개교기념일, 대체공휴일

상기 일정은 공식 학사 캘린더에 기반한 정보입니다.

### 8. 다음주 학식 뭐 나와요?

- id: `public_probe_08`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['cnu_mobile_food_week_2026_06_08_1st__dining_weekly_menu__2026-06-08__2026-06-13__제1학생회관', 'cnu_mobile_food_week_2026_06_08_2nd__dining_weekly_menu__2026-06-08__2026-06-13__제2학생회관', 'cnu_mobile_food_week_2026_06_08_3rd__dining_weekly_menu__2026-06-08__2026-06-13__제3학생회관', 'cnu_mobile_food_week_2026_06_08_4th__dining_weekly_menu__2026-06-08__2026-06-13__제4학생회관', 'cnu_mobile_food_week_2026_06_08_life_science__dining_weekly_menu__2026-06-08__2026-06-13__생활과학대학']`

제공된 검색 근거는 **2026 년 6 월 8 일~13 일**의 식단 정보로, 질문하신 **다음주 (6 월 15 일~21 일)**의 메뉴는 포함되어 있지 않습니다.

다음 주 학식 메뉴는 학교 공식 홈페이지에서 확인하실 수 있습니다.
*   **제 1 학생회관**: [식단 확인하기](https://mobileadmin.cnu.ac.kr/food/index.jsp?searchYmd=2026.06.09&searchLang=OCL04.10&searchView=date&searchCafeteria=OCL03.01)
*   **제 2 학생회관**: [식단 확인하기](https://mobileadmin.cnu.ac.kr/food/index.jsp?searchYmd=2026.06.09&searchLang=OCL04.10&searchView=date&searchCafeteria=OCL03.02)
*   **제 3 학생회관**: [식단 확인하기](https://mobileadmin.cnu.ac.kr/food/index.jsp?searchYmd=2026.06.09&searchLang=OCL04.10&searchView=date&searchCafeteria=OCL03.03)
*   **제 4 학생회관**: [식단 확인하기](https://mobileadmin.cnu.ac.kr/food/index.jsp?searchYmd=2026.06.09&searchLang=OCL04.10&searchView=date&searchCafeteria=OCL03.04)
*   **생활과학대학**: [식단 확인하기](https://mobileadmin.cnu.ac.kr/food/index.jsp?searchYmd=2026.06.09&searchLang=OCL04.10&searchView=date&searchCafeteria=OCL03.05)

### 9. 가장 최근에 올라온 공지사항은 언제 게시되었나요?

- id: `public_probe_09`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['academic_notice_board__notice_board_item__1815__2026-06-08__2026학년도_하기_계절학기_2차_폐강_안내__e57d3f694e', 'academic_notice_board__notice_board_item__1814__2026-06-05__2026학년도_하기_계절학기_수강신청_취소13차기간_안내__d93ad5b0e1', 'academic_notice_board__notice_board_item__1813__2026-06-05__화성시인재육성재단_2026년_화성_into_테크노폴_11기12기_해외탐방_장학생_모집_안내__80241b456a', 'academic_notice_board__notice_board_item__1812__2026-06-04__2026년도_학부생_미니_연구_프로젝트_지원사업_실행_계획_안내__ea4c1aaa77', 'academic_notice_board__notice_board_item__1811__2026-06-04__2026학년도_국제하기계절학기ssis_초청학생_도우미_선발_안내__b976777f48', 'academic_notice_board__notice_board_item__1810__2026-06-02__2026년도_리빙랩_기초과정_참가자_모집_공고__2e970576db', 'academic_notice_board__notice_board_item__1809__2026-06-02__2026년_6월_인재개발원_진로취업_프로그램_안내__3f38642d4c', 'academic_notice_board_page_2__notice_board_item__1808__2026-06-01__2026학년도_dsc공유대학_융합전공복수전공_학생모집_안내__81c15b8295']`

가장 최근에 게시된 공지사항은 **2026년 6월 8일**에 올라온 '2026학년도 하기 계절학기 2차 폐강 안내'입니다.

### 10. 충남대학교 인공지능학과 24학번의 경우 프로젝트 수업을 몇 개 들어야 하나요?

- id: `public_probe_10`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['academic_notice_board_page_2__notice_board_item__1805__2026-05-28__koica-충남대학교_전문인재_양성_프로그램_모집_안내__1e974a1a4a', 'academic_notice_board__notice_board_item__1812__2026-06-04__2026년도_학부생_미니_연구_프로젝트_지원사업_실행_계획_안내__ea4c1aaa77', 'notice_candidate_ai_20_chunk_9', 'notice_candidate_ai_20_chunk_8', 'notice_candidate_ai_30_chunk_8', 'academic_notice_board_page_5__notice_board_item__1775__2026-04-03__본교_박물관_국립대학육성사업_장학생_모집_안내__0aa4d979fd', 'notice_candidate_ai_90_chunk_9', 'notice_candidate_ai_0_chunk_5']`

현재 제공된 검색 근거에는 인공지능학과 24학번의 '프로젝트 수업'을 몇 개 들어야 하는지에 대한 구체적인 이수 요건이나 학과 내규가 포함되어 있지 않습니다.

다만, 관련 공지사항을 통해 다음과 같은 정보를 확인하실 수 있습니다.
1. **졸업 요건 및 교과목**: 2025 년 9 월부터 시행된 교양교육과정 개편 및 학과 졸업요건표가 공지되어 있으며, 인공지능개론 대체교과목 및 컴퓨터과학적사고 이수면제 안내 등 졸업 관련 규정이 업데이트되고 있습니다.
2. **수강 정원 및 안내**: 2026 년 1 학기 인공지능학과 및 컴퓨터융합학부의 수강 정원 증원 계획과 여석 조정 안내가 게시되어 있어, 프로젝트 수업 등 특정 과목의 수강 가능 여부와 정원을 확인하실 수 있습니다.
3. **졸업 프로젝트**: 종합설계 분반 공지 및 졸업프로젝트 신청 결과에 따른 수강 분반 배정 안내가 있어, 프로젝트 수업이 졸업 과정의 일부임을 알 수 있습니다.

정확한 프로젝트 수업 이수 개수는 학과 내규 (컴퓨터융합학부.인공지능학과 졸업에 관한 내규) 에 명시되어 있으므로, 학과 조교실이나 학과 홈페이지의 '졸업 요건' 또는 '내규' 메뉴에서 최신 정보를 확인하시는 것을 권장합니다.

### 11. 이번 학기 종강일이 언제인가요?

- id: `public_probe_11`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['academic_calendar__academic_calendar_event__2026__2026-06-22__2026-06-22__하기방학__37__964c89f954', 'academic_calendar_2023__academic_calendar_event__2023__2023-06-22__2023-06-22__하기방학__38__9c7a70e40a', 'academic_calendar_2024__academic_calendar_event__2024__2024-06-24__2024-06-24__하기방학__38__20a32c8785', 'academic_calendar_2025__academic_calendar_event__2025__2025-06-24__2025-06-24__하기방학__38__1c7756fe0f', 'academic_calendar__academic_calendar_event__2026__2025-12-22__2026-01-13__동기_계절학기__1__58dc59a409', 'academic_calendar__academic_calendar_event__2026__2026-06-22__2026-07-10__하기_계절학기__38__169fbd8705', 'academic_calendar__academic_calendar_event__2026__2026-12-21__2027-01-12__동기_계절학기__68__a344992106', 'academic_calendar_2023__academic_calendar_event__2023__2022-12-21__2023-01-10__동기_계절학기__1__82ef62db67']`

2026학년도 1학기 종강일은 2026년 6월 22일입니다. 이 날부터 하계 방학이 시작됩니다.

### 12. 이번 여름 계절학기 종강일이 언제인 가요?

- id: `public_probe_12`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['academic_calendar__academic_calendar_event__2026__2026-06-22__2026-07-10__하기_계절학기__38__169fbd8705', 'academic_calendar_2023__academic_calendar_event__2023__2023-06-22__2023-07-12__하기_계절학기__39__a1b316d8ff', 'academic_calendar_2024__academic_calendar_event__2024__2024-06-24__2024-07-12__하기_계절학기__39__4feae89257', 'academic_calendar_2025__academic_calendar_event__2025__2025-06-24__2025-07-14__하기_계절학기__39__8afa1a76a9', 'academic_calendar__academic_calendar_event__2026__2025-12-22__2026-01-13__동기_계절학기__1__58dc59a409', 'academic_calendar__academic_calendar_event__2026__2026-12-21__2027-01-12__동기_계절학기__68__a344992106', 'academic_calendar_2023__academic_calendar_event__2023__2022-12-21__2023-01-10__동기_계절학기__1__82ef62db67', 'academic_calendar_2023__academic_calendar_event__2023__2023-12-22__2024-01-15__동기_계절학기__69__9af344d708']`

2026학년도 하기 계절학기는 2026년 6월 22일부터 7월 10일까지 진행됩니다. 따라서 이번 여름 계절학기의 종강일은 **7월 10일**입니다.

참고로, 과거 학기별 여름 계절학기 기간은 다음과 같습니다.
- 2025학년도: 6월 24일 ~ 7월 14일
- 2024학년도: 6월 24일 ~ 7월 12일
- 2023학년도: 6월 22일 ~ 7월 12일

정확한 일정은 학교 공식 학사 캘린더를 통해 확인하실 수 있습니다.

### 13. 다음주 화요일 2학생회관 메뉴가 어떻게 되나요?

- id: `public_probe_13`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['cnu_mobile_food_week_2026_06_08_2nd__dining_weekly_menu__2026-06-08__2026-06-13__제2학생회관', 'cnu_mobile_food__dining_menu__2026-06-08__제2학생회관__조식__직원__2__256ddf0c67', 'cnu_mobile_food__dining_menu__2026-06-08__제2학생회관__조식__학생__7__465a75c6e2', 'cnu_mobile_food__dining_menu__2026-06-08__제2학생회관__중식__직원__11__719fd0a2ec', 'cnu_mobile_food__dining_menu__2026-06-08__제2학생회관__중식__학생__15__f93b5483f8', 'cnu_mobile_food__dining_menu__2026-06-08__제2학생회관__석식__직원__19__7a089ca5e1', 'cnu_mobile_food__dining_menu__2026-06-08__제2학생회관__석식__학생__23__2b91fe376d', 'cnu_mobile_food_week_2026_06_08_2nd__dining_menu__2026-06-09__제2학생회관__조식__직원__2__0a1b341c11']`

제 2 학생회관 2026 년 6 월 16 일 (다음 주 화요일) 메뉴는 검색된 근거에 포함되어 있지 않습니다. 제공된 정보는 2026 년 6 월 8 일~13 일 기간의 식단이며, 해당 날짜의 메뉴는 공식 홈페이지에서 확인하시기 바랍니다.

*   **확인 링크:** [제 2 학생회관 식단](https://mobileadmin.cnu.ac.kr/food/index.jsp)

### 14. 토익 장학금을 받으려면 성적이 몇 점 이상이어야 하나요?

- id: `public_probe_14`
- status: `answered`
- qwen_writer_called: `True`
- retrieved_doc_ids: `['academic_notice_board_page_4__notice_board_item__1784__2026-04-29__2026년_하기_국가근로장학금_취업연계_중점대학_안내__d8a691db78', 'scholarship_overview_chunk_2', 'scholarship_overview_chunk_3', 'scholarship_external_overview_chunk_2', 'scholarship_external_overview_chunk_3', 'graduation_english_requirements_chunk_7', 'scholarship_overview_chunk_1', 'scholarship_external_overview_chunk_4']`

충남대학교에서 국가근로장학금을 받으려면 **국가장학금 (Ⅰ·Ⅱ유형)**의 선발기준을 충족해야 합니다.

*   **일반 재학생 기준:** 직전 학기 **12 학점 이상** 이수 및 **백분위 성적 80 점 이상** 취득해야 합니다.
*   **기초·차상위 계층 및 학자금 지원 1~3 구간:** **70 점 (C 학점)** 이상이어야 합니다.
*   **신입생·편입생·재입학생·장애인학생:** 이수 학점 및 성적 기준이 **미적용**됩니다.

또한, **Ⅱ유형**의 경우 대학에서 별도의 선발기준을 수립하므로 한국장학재단 홈페이지나 해당 학과의 공지사항을 반드시 확인하시기 바랍니다.
