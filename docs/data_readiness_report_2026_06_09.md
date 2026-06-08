# Qwen Data Readiness Report

- 기준일: `2026-06-09`
- 입력: `data/knowledge_seed.json`
- 문서 수: `2414`
- 성격: diagnostic report, final performance claim 아님
- 현재 방향: Qwen에게 clean official evidence를 주는 단순 경로. confidence label이나 prose-derived structured graduation row는 사용하지 않는다.

## 전체 집계

| 항목 | 값 |
|---|---:|
| domain `graduation` | 85 |
| domain `notices` | 648 |
| domain `academic_calendar` | 480 |
| domain `dining` | 1145 |
| domain `shuttle` | 56 |
| generation `source_parse` | 945 |
| generation `structured_row` | 1374 |
| generation `structured_aggregate` | 95 |

## 도메인별 준비도

| Domain | Total | Answer-unit | Fragment/source_parse | Verdict | Caveat | Next |
|---|---:|---:|---:|---|---|---|
| `academic_calendar` | 480 | 418 | 62 | `ready` | calendar has source-native event and aggregate rows; use chunks only as supporting context | Inspect retrieval quality before adding more transformations. |
| `dining` | 1145 | 25 | 195 | `usable_with_caveat` | weekly bundles are answer-sized; row-level menu docs should support exact date/cafeteria questions | Inspect retrieval quality before adding more transformations. |
| `graduation` | 85 | 0 | 85 | `needs_explicit_parser_or_better_sources` | prose-to-structured graduation rows are disabled; graduation evidence is currently plain source text only | Collect explicit curriculum tables or keep graduation answers broad until a source-native parser exists. |
| `notices` | 648 | 60 | 588 | `usable_with_caveat` | notice coverage is broader after source expansion, but board rows should be preferred over page chunks | Inspect retrieval quality before adding more transformations. |
| `shuttle` | 56 | 2 | 15 | `usable_with_caveat` | route-level summaries are sparse; segment rows should support route summaries | Inspect retrieval quality before adding more transformations. |

## Simplification Checks

- graduation structured rows: `0`
- chunk confidence metadata keys: `0`
- source_parse chunks are plain recursive/plain window chunks in source order.

## Evidence JSON

- `docs/evidence/data-readiness-2026-06-09.json`
