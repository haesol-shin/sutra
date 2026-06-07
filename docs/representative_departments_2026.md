# 2026 Representative Department Headcount Basis

작성일: 2026-06-07

이 문서는 Priority 1 졸업요건/교육과정 데이터 확장에서 사용할 대표 학과 선정 기준을 고정한다.

## Decision

대표 학과는 2026학년도 기준 인원순 top 5를 사용한다.

공개적으로 바로 확인 가능한 학과별 `재학생 수` 자료가 아직 확보되지 않았으므로, 이번 1차 데이터 확장에서는 2026학년도 수시모집요강의 `모집단위별 수시모집 합계`를 인원수 기준으로 사용한다.

이 기준은 재학생 수가 아니라 `2026학년도 수시 모집인원`이다. 공식 재학생 수 또는 더 나은 2026 학과별 headcount 자료가 확보되면 이 문서를 갱신한다.

## Source

- Source title: 충남대학교 2026학년도 수시 모집요강
- Source URL used for extraction: `https://file.megastudy.net/FileServer/UNI_HWP/non_file/26susi/X26C05023.pdf`
- Cross-check note: news reports state that Chungnam National University selected 3,357 students for 2026 수시모집 and point readers to the CNU admissions site for details.
- Local extraction path, ignored by git: `data/raw/admission/cnu_2026_susi_megastudy.pdf`
- Extracted pages used: 모집단위별 모집인원 table on pages 14-16 of the PDF.

## Overall Top 5 모집단위

This ranking includes broad 전공자율선택제 모집단위. It is useful as a raw enrollment-size reference, but some units are not ideal direct targets for 졸업요건 crawling because students later select a major.

| Rank | 모집단위 | 2026 수시모집 합계 | Note |
|---:|---|---:|---|
| 1 | 농생명융합학부 | 308 | 전공자율선택제/융합 모집단위 성격 |
| 2 | 경영학부 | 148 | 일반 학부 |
| 3 | 컴퓨터인공지능학부 | 147 | 일반 학부 |
| 4 | 인문사회융합학부 | 125 | 전공자율선택제/융합 모집단위 성격 |
| 5 | 자율전공융합학부 | 96 | 전공자율선택제/융합 모집단위 성격 |

## Priority 1 Graduation Source Target Top 5

For 졸업요건/교육과정 crawling, use the top 5 regular major-bearing 모집단위 after excluding broad 전공자율선택제/융합 entry units whose graduation requirements are likely governed by later major selection.

| Rank | 모집단위 | 2026 수시모집 합계 | Selection reason |
|---:|---|---:|---|
| 1 | 경영학부 | 148 | Largest regular major-bearing unit |
| 2 | 컴퓨터인공지능학부 | 147 | Large regular major-bearing unit and current 2026 reorganization target |
| 3 | 정보통신융합학부 | 85 | Large regular major-bearing unit |
| 4 | 신소재공학과 | 85 | Tied with 정보통신융합학부; retained because it is a direct department target |
| 5 | 의예과 | 81 | Large regular major-bearing unit; high-impact graduation/curriculum domain |

Tie handling: when 모집인원 is tied, preserve the order in the 모집요강 table unless a direct department page is unavailable. If a selected unit has no usable official 졸업요건 source, record the failure and replace it with the next ranked regular unit by 2026 수시모집 합계.

## Use In The Data Expansion Plan

The first Priority 1 completion gate is fixed as follows:

- curriculum years: exactly `2023`, `2024`, `2025`, `2026`.
- representative departments/units: the five `Priority 1 Graduation Source Target Top 5` units above.
- top 5 evidence: this document must be linked from the source inventory/progress notes.
- if a top 5 source cannot be fetched or parsed, the failure must be logged before substituting the next ranked regular unit.

## Open Verification Item

Find and prefer a CNU admissions-site URL or official disclosure page for the same 2026 모집요강/headcount data before final submission. The current extracted PDF mirror is usable for planning but should not be treated as the final official source if an official CNU-hosted PDF can be located.
