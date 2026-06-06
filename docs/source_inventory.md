# Source Inventory

작성일: 2026-06-06

이 문서는 수집 대상 source와 현재 구현 상태를 분리해서 기록한다. `seed` 데이터는 파이프라인 검증용이며, 최종 성능 주장이나 제출 데이터셋 근거로 단독 사용하지 않는다.

## Stage-Aware Collection Policy

- `stage0`: 작은 직렬 루프 검증용 source만 fetch한다.
- `stage1`: Stage 0 통과 후 넓힐 source 후보이다.
- `stage2`: 안정화 후 병렬 확장 후보이다.
- 현재 `run_collect` 기본값은 `stage0`이다.
- Stage 0은 8-12개 active source, 다섯 라벨 전체, 졸업요건 중앙 PDF와 학과 1-2개를 포함해야 한다.

## Stage 0 Active Sources

| Label | Domain | Source ID | Parser | URL | Notes |
| ---: | --- | --- | --- | --- | --- |
| 0 | graduation | `graduation_curriculum_pdf` | `pdf` | `https://plus.cnu.ac.kr/html/kr/25file/2025_book.pdf` | 중앙 2025 교육과정 PDF |
| 0 | graduation | `graduation_english_requirements` | `html` | `https://english.cnu.ac.kr/english/edu/undergraduate02.do` | 영어영문학과 졸업요건 |
| 0 | graduation | `graduation_biochemistry_requirements` | `html` | `https://biochemistry.cnu.ac.kr/biochemistry/info/requirements.do` | 생화학과 졸업요건 |
| 1 | notices | `academic_notice_board` | `html` | `https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr` | 중앙 학사공지 목록 |
| 1 | notices | `academic_notice_detail_2512782` | `board_detail` | `https://plus.cnu.ac.kr/_prog/_board/?mode=V&no=2512782&code=sub07_0702&site_dvs_cd=kr&menu_dvs_cd=0702` | 최근 학사공지 상세 |
| 1 | notices | `academic_notice_detail_2512124` | `board_detail` | `https://plus.cnu.ac.kr/_prog/_board/?mode=V&no=2512124&code=sub07_0702&site_dvs_cd=kr&menu_dvs_cd=0702` | 최근 학사공지 상세 |
| 1 | notices | `academic_notice_detail_2511200` | `board_detail` | `https://plus.cnu.ac.kr/_prog/_board/?mode=V&no=2511200&code=sub07_0702&site_dvs_cd=kr&menu_dvs_cd=0702` | 최근 학사공지 상세 |
| 2 | academic_calendar | `academic_calendar` | `calendar` | `https://plus.cnu.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&site_dvs_cd=kr` | 공식 학사일정 |
| 3 | dining | `cnu_mobile_food` | `dining` | `https://mobileadmin.cnu.ac.kr/food/index.jsp` | 최신 식단 snapshot |
| 4 | shuttle | `shuttle_bus` | `shuttle` | `https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html` | 공식 셔틀 시간표 |

## Legacy Smoke Sources

| Label | Domain | Source ID | URL | Current status |
| ---: | --- | --- | --- | --- |
| 0 | graduation | `graduation_curriculum_pdf` | `https://plus.cnu.ac.kr/html/kr/25file/2025_book.pdf` | raw fetch 가능, PDF parser 필요 |
| 1 | notices | `academic_notice_board` | `https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&menu_dvs_cd=0702&site_dvs_cd=kr` | raw fetch 가능, board detail parser 미구현 |
| 2 | academic_calendar | `academic_calendar` | `https://plus.cnu.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&site_dvs_cd=kr` | raw fetch 가능, calendar parser 미구현 |
| 3 | dining | `cnu_mobile_food`, `cnucoop_discovery` | `https://mobileadmin.cnu.ac.kr/food/index.jsp`, `https://www.cnucoop.co.kr/` | raw fetch 가능, 공식 chain/date parameter 검증 필요 |
| 4 | shuttle | `shuttle_bus` | `https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html` | raw fetch 가능, timetable parser 미구현 |

## Validation Contract

- `uv run python -m nlp_term.collect.run_collect --fetch --output data/sources/source_probe.json`
- `uv run python -m nlp_term.validators --source-probe data/sources/source_probe.json --require-raw-files`
- `uv run python -m nlp_term.validators --knowledge-provenance data/sources/source_probe.json --data-dir data`

위 명령들이 통과해야 실제 raw snapshot, source metadata, seed knowledge provenance가 연결된 것으로 본다. `official_chain_ok=False`인 source는 최종 답변에서 단정적인 최신 정보 근거로 사용하지 않는다.

## Document Parser Boundary

- PDF: `pymupdf` 기반 텍스트 추출을 기본 경로로 둔다.
- HWP: legacy `.hwp`는 OLE container를 읽기 위해 `olefile` 기반 파서를 둔다.
- HWPX: `.hwpx`는 zip/XML 구조이므로 Python stdlib 기반 파서를 둔다.
- 파싱 실패 문서는 `data/source_parse_failures.json`에 기록하고, 해당 source를 hardcoded seed row로 조용히 대체하지 않는다.
