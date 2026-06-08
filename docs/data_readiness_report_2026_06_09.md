# Qwen Data Readiness Report

- 기준일: `2026-06-09`
- 입력: `data/knowledge_seed.json`
- current knowledge checksum: `eaad337cd1e24436a30044ad76bd096f693cf4fa751ba6d86e997517f00df0e7`
- current source probe checksum: `f0f0928b5b34f365a5abcee45c655cfe70df2a6d0f45f52c0c92edef6f9aaf87`
- 문서 수: `2162`
- 성격: diagnostic report, final performance claim 아님
- 주의: public probe mapping은 오래된 baseline 경로를 설명하는 참고 표이며, 현재 우선순위 판단 근거로 쓰지 않는다.

## 판단 기준

좋은 데이터는 Qwen에게 그대로 또는 아주 작은 정리만 거쳐 넣었을 때 학생 질문에 자연스럽고 유용하게 답하는 데 도움이 되는 데이터다. 이 보고서는 `source_url` 존재와 official-chain 검증을 분리해서 본다.

## 전체 집계

| 항목 | 값 |
|---|---:|
| domain `graduation` | 325 |
| domain `notices` | 203 |
| domain `academic_calendar` | 465 |
| domain `dining` | 1110 |
| domain `shuttle` | 59 |
| generation `structured_row` | 1618 |
| generation `source_parse` | 449 |
| generation `structured_aggregate` | 95 |

## 도메인별 준비도

| Domain | Total | Answer-unit | Fragment/raw | official true/false/missing | Coverage | Verdict | Blocker/Caveat | Next |
|---|---:|---:|---:|---|---|---|---|---|
| `graduation` | 325 | 244 candidates | 81 | 325/0/0 | - | `not_ready_until_audited` | extraction accuracy is not reliable enough; some rows misread local credit mentions as requirements; department/year scope must be preserved | Add high-confidence extraction filters and audit representative rows before treating graduation_requirement rows as Qwen-ready. |
| `notices` | 203 | 60 | 143 | 203/0/0 | 2026-01-14~2026-06-08 (39 dates) | `not_ready` | structured notice coverage is low | Prefer notice_board_item; rebuild/extract more board items from raw notice list chunks. |
| `academic_calendar` | 465 | 418 | 47 | 465/0/0 | 2022-12-21~2026-12-25 (256 dates) | `ready` | - | Prefer semester/month aggregate docs for broad questions and event rows for direct date lookup; suppress raw source_parse chunks. |
| `dining` | 1110 | 25 | 1085 | 1110/0/0 | menu weeks in June 2026 | `usable_with_caveat` | weekly bundles already exist, but row-level dining_menu fragments can still dominate broad retrieval if not prioritized correctly | Prefer dining_weekly_menu for broad/current-week questions; use dining_menu rows only inside a date/cafeteria/meal bundle. |
| `shuttle` | 59 | 2 | 57 | 59/0/0 | doc date 2026-03-03; route validity 2026-03-03~2026-06-21 | `usable_with_caveat` | route-level summaries are sparse; many rows are segments | Prefer shuttle_route summaries; use segment rows only to enrich route-level summaries. |

## 샘플

### graduation
- clean candidate: `graduation_biochemistry_requirements__graduation_requirement__생화학과__unknown__교양_이수학점__1__fceefcb2a7` / `graduation_requirement` / 생화학과 unknown 교양 이수학점
  - excerpt: 생화학과 unknown 교육과정의 general_education 요건: 교양 이수학점은 3학점 기준입니다. 적용 대상은 생화학과 적용자입니다. 원문 문장: '이수구분이 바르게 표시 되었는지 먼저 확인하세요! 13학년도 교육과정 이전학생은 교양에서 국어 관련3학점, 영어 관련 6학점이상 이수하여 교양이 합계 24학점이 되어야 합니다'.
- noisy/fragment candidate: `graduation_biochemistry_requirements_chunk_1` / `<missing>` / graduation source 1
  - excerpt: 교육과정에 따라 이수해야 할 과목이 많이 다릅니다. (보통은 학번 앞자리이지만 변경한 경우 학번과 다를 수 있습니다.) F학점은 제외하고 확인합니다. 이수구분이 바르게 표시 되었는지 먼저 확인하세요! 13학년도 교육과정 이전학생은 교양에서 국어 관련3학점, 영어 관련 6학점이상 이수하여 교양이 합계 24학점이 되어야 합니다. (1~5영역 골로루 이수 안 해도 됩니다.) 그리고 기초과목은 정해

### notices
- clean candidate: `academic_notice_board__notice_board_item__공지__2026-04-16__2026학년도_하기_계절학기_국내_다른_대학_수학_안내__8b9f10574f` / `notice_board_item` / 2026학년도 하기 계절학기 국내 다른 대학 수학 안내
  - excerpt: 2026학년도 하기 계절학기 국내 다른 대학 수학 안내 공지사항의 게시일은 2026-04-16입니다. 작성자는 학사지원과이고, 번호는 공지입니다. 상단 고정 공지이며 첨부파일이 있습니다. 상세 링크: https://plus.cnu.ac.kr/_prog/_board/?mode=V&no=2512782&code=sub07_0702&site_dvs_cd=kr&menu_dvs_cd=0702&skey=
- noisy/fragment candidate: `academic_notice_board_chunk_1` / `<missing>` / notices source 1
  - excerpt: 학사정보게시판 목록 번호 제목 작성자 작성일 조회수 공지 2026학년도 하기 계절학기 국내 다른 대학 수학 안내 학사지원과 2026-04-16 4616 공지 2026학년도 제1학기 학생 출석인정 신청 변경 사항 안내 학사지원과 2026-03-05 5720 공지 2026학년도 제1학기 휴학 및 복학 신청 안내 학사지원과 2026-01-14 4837 1815 2026학년도 하기 계절학기 2차 폐

### academic_calendar
- clean candidate: `academic_calendar__academic_calendar_event__2026__2025-12-22__2026-01-13__동기_계절학기__1__58dc59a409` / `academic_calendar_event` / 2025-12-22 동기 계절학기
  - excerpt: 2026학년도 학사일정: 동기 계절학기은 2025-12-22부터 2026-01-13까지입니다. 학생 표현으로는 겨울 계절학기, 동계 계절학기, 계절학기 종강, 겨울 계절학기 종강일에 해당합니다.
- noisy/fragment candidate: `academic_calendar_chunk_1` / `<missing>` / academic_calendar source 1
  - excerpt: 01.13(화) 제2학기 성적발표

### dining
- clean candidate: `cnu_mobile_food_week_2026_06_08_1st__dining_weekly_menu__2026-06-08__2026-06-13__제1학생회관` / `dining_weekly_menu` / 2026-06-08~2026-06-13 제1학생회관 주간 식단
  - excerpt: 2026-06-08~2026-06-13 제1학생회관 주간 식단 요약:
- 2026-06-08 제1학생회관 조식 직원 식단은 운영안함입니다.
- 2026-06-08 제1학생회관 조식 학생 식단은 운영안함입니다.
- 2026-06-08 제1학생회관 중식 직원 식단은 운영안함입니다.
- 2026-06-08 제1학생회관 중식 학생 식단은 운영안함입니다.
- 2026-06-08 제1학생회관 석식 직원
- noisy/fragment candidate: `cnu_mobile_food__dining_menu__2026-06-08__제1학생회관__조식__직원__1__de7b35a625` / `dining_menu` / 2026-06-08 제1학생회관 조식 식단
  - excerpt: 2026-06-08 제1학생회관 조식 직원 메뉴: 메뉴운영내역.

### shuttle
- clean candidate: `shuttle_bus__shuttle_route__campus_loop__2026-03-03__2026-06-21__2a184c34ae` / `shuttle_route` / 2026학년도 셔틀버스 교내 순환
  - excerpt: 2026학년도 셔틀버스 교내 순환은 2026-03-03부터 2026-06-21까지 학기 중 평일 주간에 정상 운행합니다. 평일 야간, 주말, 공휴일, 방학 등은 미운영입니다. 출발 시간표: 08:20 (월평역) 등교, 08:30, 09:30, 09:40, 10:30, 11:30, 13:30, 14:30, 15:30, 16:30, 17:30. 첫차 08:30, 막차 17:30. 정류장 및 운행
- noisy/fragment candidate: `shuttle_bus__shuttle_segment__campus_loop__departure_time__0820_월평역_등교__1__2026-03-03__2026-06-21__44bb3f901c` / `shuttle_segment` / 2026학년도 셔틀버스 교내 순환 출발시각 08:20 (월평역) 등교
  - excerpt: 2026학년도 셔틀버스 교내 순환의 출발시각: 08:20 (월평역) 등교. 적용 기간은 2026-03-03부터 2026-06-21까지이고, 운영일은 학기 중 평일 주간입니다.

## Old Public Probe Mapping

이 표는 오래된 Qwen baseline/harness 경로를 설명하는 참고 자료다. 현재 `data/knowledge_seed.json` checksum과 다르므로 현재 우선순위 판단 근거로 사용하지 않는다. `Answer-unit docs found`는 전체 knowledge 안의 존재 여부가 아니라, 당시 baseline이 실제로 가져온 retrieved docs 안에서 answer-unit 문서가 발견되었는지를 뜻한다.

| ID | Domain | Baseline | Bottleneck | Answer-unit docs found | Recommendation |
|---|---|---|---|---:|---|
| `public_probe_01` | `graduation` | `answered` | `none` | 0 | data_transform_or_retrieval_issue |
| `public_probe_02` | `academic_calendar` | `answered` | `none` | 0 | data_transform_or_retrieval_issue |
| `public_probe_03` | `dining` | `fail_closed` | `data` | 0 | avoid_hard_fail_closed; provide useful bounded answer if evidence is partial |
| `public_probe_04` | `shuttle` | `fail_closed` | `temporal` | 0 | avoid_hard_fail_closed; provide useful bounded answer if evidence is partial |
| `public_probe_05` | `notices` | `answered` | `temporal` | 0 | data_transform_or_retrieval_issue |
| `public_probe_06` | `shuttle` | `answered` | `temporal` | 0 | data_transform_or_retrieval_issue |
| `public_probe_07` | `academic_calendar` | `fail_closed` | `retrieval` | 0 | avoid_hard_fail_closed; provide useful bounded answer if evidence is partial |
| `public_probe_08` | `dining` | `fail_closed` | `retrieval` | 0 | avoid_hard_fail_closed; provide useful bounded answer if evidence is partial |
| `public_probe_09` | `notices` | `fail_closed` | `temporal` | 0 | avoid_hard_fail_closed; provide useful bounded answer if evidence is partial |
| `public_probe_10` | `graduation` | `fail_closed` | `classifier` | 0 | avoid_hard_fail_closed; provide useful bounded answer if evidence is partial |
| `public_probe_11` | `academic_calendar` | `answered` | `none` | 0 | data_transform_or_retrieval_issue |
| `public_probe_12` | `academic_calendar` | `answered` | `none` | 0 | data_transform_or_retrieval_issue |
| `public_probe_13` | `dining` | `fail_closed` | `evidence` | 0 | avoid_hard_fail_closed; provide useful bounded answer if evidence is partial |
| `public_probe_14` | `notices` | `fail_closed` | `retrieval` | 0 | avoid_hard_fail_closed; provide useful bounded answer if evidence is partial |

## 우선순위

1. **Current evidence-pack audit**
   - 근거: 이전 public probe mapping은 stale baseline이므로 현재 Qwen 입력을 직접 확인해야 한다.
   - 종료 조건: 39-set diagnostics에서 각 질문별 selected evidence row_type, title, source_id, body excerpt를 표로 남긴다.
2. **Graduation extraction accuracy gate**
   - 근거: 졸업 row는 개수보다 정확도가 병목이며, 일부 학점 표현을 잘못 일반화했다.
   - 종료 조건: 졸업 요건 row를 high-confidence/needs-review로 나누고, ambiguous row는 Qwen-ready 후보에서 제외한다.
3. **Dining bundle priority**
   - 근거: Dining has 925 dining_menu rows and 25 weekly aggregates; bundles exist but retrieval/evidence selection must prefer them for broad questions.
   - 종료 조건: Dining questions receive weekly/daily bundle evidence first; individual dining_menu rows only appear as bundle details.
4. **Shuttle route summary priority**
   - 근거: route-level summaries are useful, but segment rows are too small for broad questions.
   - 종료 조건: Shuttle questions receive shuttle_route first and segment rows only as supporting details.
5. **Notice structured extraction expansion**
   - 근거: Only 60/203 notice docs are structured notice_board_item; raw list chunks dominate notices.
   - 종료 조건: Latest/notice-location questions retrieve notice_board_item or explicit board summary before raw chunks.

## Hybrid RAG 위치

Hybrid RAG는 배제하지 않는다. 다만 이 보고서는 hybrid 이전의 데이터 준비도 진단이다. 현재 39셋 진단에서 retrieval top-3 domain hit는 높았지만, Qwen baseline은 fail-closed와 fragment 전달 문제가 컸다. 따라서 첫 구현은 embedding/reranker가 아니라 answer-unit 우선 전달을 검증한다.

Hybrid 후보는 도메인별로 다르게 본다.

- 우선순위 높음: notices, graduation. 표현 차이와 학과/제도명 변형이 많아 semantic search와 reranker 효과가 클 수 있다.
- 우선순위 중간: academic_calendar. event alias가 충분하면 lexical/metadata로도 가능하지만 "종강", "방학 시작" 같은 표현 변형은 보강 가치가 있다.
- 우선순위 낮음: dining, shuttle. 날짜/장소/노선 구조 필드가 핵심이라, 먼저 answer-unit bundle/route summary가 필요하다.

결론적으로 hybrid는 "검색 알고리즘 개선" 단계에서 실험한다. 지금 단계의 목적은 Qwen에게 넘길 후보 문서 단위를 깨끗하게 만드는 것이다.

## Non-goals

- no new crawling
- no prompt optimization
- no validator changes
- no tool-call revival

## 결론

현재 병목은 데이터 총량 하나가 아니라 Qwen에게 전달되는 evidence 단위와 extraction 정확도다. Dining은 공식 flag를 probe부터 고쳤고 weekly bundle도 존재한다. 다음 최소 구현은 current evidence-pack audit, graduation extraction gate, dining/shuttle/notices의 answer-unit 우선 전달이다.
