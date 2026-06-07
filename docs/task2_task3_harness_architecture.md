# Task 2/3 Evidence Harness Architecture

작성일: 2026-06-07

이 문서는 Task 2 챗봇과 Optional Task 3 실시간 응답 경로에 적용할 evidence harness 구조를 정리한다. 목표는 Qwen3.5-9B를 자유로운 tool-call agent로 쓰는 것이 아니라, 검증 가능한 상태 전이 안에서 근거 기반 답변 writer로 사용하는 것이다.

## 1. 결정

- Phase A에서는 Qwen3.5-9B를 action/tool planner로 사용하지 않는다.
- Qwen3.5-9B는 정리된 evidence pack을 받아 자연스러운 한국어 답변을 작성하는 writer로 둔다.
- RAG/evidence store가 충분한지, controlled fetch가 필요한지는 orchestrator가 deterministic하게 결정한다.
- web search는 open web search가 아니다. fetch는 `SourceSpec` registry에 등록된 active source에 대해서만 허용한다.
- 최신/현재 정보를 묻는 `current_fact` 질문은 freshness와 구조화 필드가 없으면 fail-closed한다.
- deterministic composer는 비교 기준, 디버그 기준, 비상 경로다. deterministic output은 llama/Qwen 품질 근거로 계산하지 않는다.

이 결정은 영구적으로 Qwen의 tool-use 가능성을 배제한다는 뜻이 아니다. Phase A의 목적은 먼저 harness의 실패 지점을 관측 가능하게 만드는 것이다. 이후 Phase B/C에서 Qwen을 constrained advisor 또는 state 안의 제한된 action proposer로 실험할 수 있다.

## 2. 큰 구조

실제 코드는 단순한 Python orchestrator로 시작하되, trace에는 세부 state를 기록한다.

```text
intent_state
  -> source_scope_state
  -> evidence_lookup_state
  -> source_status_state
  -> evidence_sufficiency_state
  -> controlled_fetch_state
  -> parse_validate_state
  -> evidence_pack_state
  -> answer_state
  -> final_validate_state
  -> output_state
```

간단히 보면 네 단계다.

```text
질문 이해
  -> 근거 검색과 충분성 판정
  -> 필요 시 registry-only 보정
  -> 답변 생성과 검증
```

state를 세분화하는 이유는 구현을 복잡하게 만들기 위해서가 아니라, 실패 원인을 분리하기 위해서다. 예를 들어 “식단 답변 실패”가 RAG 실패인지, 공식 source 미검증인지, 구조화 parser 부재인지, Qwen hallucination인지 trace로 구분해야 한다.

## Temporal Intent Policy

Task 2와 Task 3 질문은 single-turn으로 처리한다. 따라서 harness는 한 번의 요청 안에서 시간 표현을 해석하고, 근거를 검색하고, 충분성을 검증한 뒤, 최종 답변까지 생성해야 한다. Qwen3.5-9B는 temporal planner가 아니라 정리된 evidence pack을 자연스럽게 쓰는 writer로 둔다.

주 단위 표현은 ISO 방식에 맞춰 월요일부터 일요일까지를 한 주로 본다. 예를 들어 runtime date가 `2026-06-08`이면 `다음주 화요일`은 가장 가까운 미래 화요일인 `2026-06-09`가 아니라, 다음 ISO week의 화요일인 `2026-06-16`으로 해석한다. 최종 답변에는 필요한 경우 해석된 날짜나 기간을 자연스럽게 명시한다.

`TemporalIntent`는 다음 정보를 trace에 남긴다.

- `temporal_type`: `none`, `date_lookup`, `current_snapshot`, `future_schedule`, `latest_item`, `changed_since`, `ongoing_status`, `period_summary` 중 하나다.
- `confidence`: `high`, `medium`, `low`와 confidence reason을 함께 기록한다.
- `target_start`, `target_end`: 정규화된 날짜 또는 기간이다.
- `freshness_required`: 오늘/현재/최신/미래 식단처럼 바뀌는 정보면 true다.
- `version_match_required`: 졸업요건/교육과정처럼 학과, 입학연도, 교육과정 연도 일치가 중요한 경우 true다.
- `retrieval_requirements`: 하나의 enum이 아니라 list다. 예를 들어 `다음주 화요일 2학생회관 메뉴`는 날짜 필터와 구조화 source 선호가 동시에 필요하다.

Low temporal confidence가 곧 방어적 답변을 뜻하지는 않는다. 먼저 승인된 기본 정책을 적용하고 검색을 강화한다. 예를 들어 `최근에 바뀐 학사일정`은 최근 30일 기본 창으로 검색한다. 근거가 충분하면 정상 답변하고, 근거가 부족할 때만 단정을 피한다.

Qwen prompt에는 전체 `TemporalIntent`를 넣지 않는다. prompt에는 현재 기준일, 질문의 시간 표현, 해석된 날짜/기간, 날짜가 맞지 않는 근거로 단정하지 말라는 사용자 안전 문장만 넣는다. 최종 답변에는 `TemporalIntent`, `confidence`, `retrieval_requirement`, `evidence_status` 같은 내부 상태명이 노출되면 안 된다.

## Evidence Pack Context Policy

Evidence pack은 각 chunk를 첫 문장으로 줄이지 않는다. 작은 chunk 안에서도 날짜, 학점, 장소, 조건 정보가 뒤쪽에 나올 수 있으므로, 정규화된 chunk 본문을 bounded context로 보존한다.

기본 pack 크기는 static 질문 3개, 날짜/current/freshness 질문 5개, 기간 요약 또는 변경사항 요약 질문 8개다. 이는 Qwen3.5-9B가 근거를 조립할 재료를 충분히 받도록 하기 위한 Phase A 기본값이며, 이후 retrieval 품질과 context budget 실험에 따라 조정할 수 있다.

## 3. Phase A Target Modules

Phase A는 production switch가 아니라 실험용 harness다.

- `src/nlp_term/chat/state_contract.py`
  - enum, pydantic state model, `HarnessTrace`, `HarnessResult`
- `src/nlp_term/chat/source_status.py`
  - `KnowledgeDoc` metadata와 `SourceSpec` registry를 합쳐 `SourceStatus`로 정규화
- `src/nlp_term/chat/evidence_sufficiency.py`
  - RAG-vs-fetch truth table evaluator
- `src/nlp_term/chat/controlled_fetch.py`
  - registry-only fetch boundary
- `src/nlp_term/chat/orchestrator.py`
  - state sequence runner

Phase A에서는 `batch.py`, `ui/app.py`, `evaluate_gold.py`, `compare_backends` 경로를 바로 바꾸지 않는다. 10-question smoke가 통과한 뒤 Phase B에서 production/evaluation path를 orchestrator로 옮긴다.

## 4. Harness Signature

Phase A target signature:

```python
def answer_with_harness(
    question: str,
    *,
    mode: Literal["chat", "realtime"] = "chat",
    backend: Literal["auto", "llama", "deterministic"] = "auto",
    knowledge_path: Path | None = None,
    model_path: Path = DEFAULT_MODEL_PATH,
    generator: Callable[[str], str] | None = None,
    live_fetch_enabled: bool = False,
    min_top_score: float = 0.20,
    question_time: datetime | None = None,
    allowed_stages: set[Stage] = {"stage0"},
) -> HarnessResult:
    ...
```

- `generator`는 테스트와 smoke용 injected generator다. 지정되면 `generation_backend = "injected"`로 기록한다.
- `live_fetch_enabled=False`이면 fetch 가능 여부만 판정하고 네트워크 호출은 하지 않는다.
- `mode="realtime"`은 명백한 source navigation이 아닌 freshness-sensitive 질문을 더 엄격하게 `current_fact`로 올린다.
- `min_top_score` 기본값은 smoke용 `0.20`이며 trace에 기록하고 fixture로 조정 가능하게 둔다.

## 5. AnswerKind

`AnswerKind`는 required fields와 freshness gate를 결정한다.

| Kind | 의미 | 최소 근거 |
| --- | --- | --- |
| `source_navigation` | 어디서 확인하는지, 링크/페이지/게시판을 묻는 질문 | 안전한 source URL과 source status |
| `static_fact` | 졸업요건, 교육과정 같은 안정적 사실 | slot이 맞는 RAG fact text |
| `current_fact` | 오늘, 이번 주, 최신, 현재, 마감, 운행 중, 메뉴/시간표를 묻는 질문 | freshness + 구조화 필드 |
| `procedural` | 신청 방법, 제출 절차 | source URL + 관련 절차/fact text |
| `unsupported` | 5개 카테고리 밖이거나 source path가 없는 질문 | fail-closed |

예시:

- “셔틀 시간표 어디서 봐?” -> `source_navigation`
- “오늘 점심 뭐야?” -> `current_fact`
- “2026 컴인 졸업요건 알려줘” -> `static_fact`
- “휴학 신청은 어떻게 해?” -> `procedural`

## 6. Candidate Source Selection

후보 source는 `SourceSpec` registry에서만 고른다.

1. `all_specs = STAGE0_SOURCES + STAGE1_CANDIDATE_SOURCES + STAGE2_CANDIDATE_SOURCES`로 본다. 존재하지 않는 tuple은 빈 목록으로 처리한다.
2. Phase A 기본 후보 조건:
   - `spec.active is True`
   - `spec.stage in allowed_stages`
   - `spec.domain == route_domain`
3. slot filter:
   - `slots.department`가 있고 `spec.department`도 있으면 정규화 exact match를 요구한다.
   - 정확히 맞는 active department source가 없으면 central same-domain source는 fallback 후보로 남길 수 있다.
   - 다만 central fallback은 retrieved evidence metadata에 department match가 없으면 department-specific static fact를 충분하다고 보지 않는다.
   - `slots.curriculum_year`도 같은 방식으로 `spec.curriculum_year`, `metadata.source_curriculum_year`, `metadata.curriculum_year`와 exact match해야 한다.
   - `date`, `meal`, `location`, `route_or_stop`은 Phase A에서 source 후보를 제거하지 않고 required-field check에서 처리한다.
4. answer kind filter:
   - `source_navigation`: active same-domain source면 후보 가능. 안전한 URL/status가 있으면 충분할 수 있다.
   - `static_fact`/`procedural`: active same-domain source가 후보. 공식 출처라고 말하려면 official chain 또는 allowlisted CNU host가 필요하다.
   - `current_fact`: active, `official_chain_ok=True`, freshness policy 지원, 구조화 parser 지원 가능성이 있어야 한다.

`registry_explicitly_supports_category`는 allowed stage 안에 active same-domain `SourceSpec`이 하나 이상 있다는 뜻이다.

## 7. SourceStatus

`SourceStatus`는 retrieved `KnowledgeDoc`와 registry `SourceSpec`의 metadata 차이를 흡수한다.

필드:

- `source_id`
- `source_url`
- `registry_present`
- `active`
- `official_chain_ok`
- `parser_type`
- `freshness_policy`
- `raw_fetched_at`
- `allowlist_status`: `allowed | blocked | unknown`
- `metadata_department`
- `metadata_curriculum_year`
- `metadata_domain`

metadata alias:

- department: `metadata.source_department`, `metadata.department`
- curriculum year: `metadata.source_curriculum_year`, `metadata.curriculum_year`
- fetched time: `metadata.raw.fetched_at`, `metadata.raw_fetched_at`, `metadata.fetched_at`

registry가 없거나 metadata가 불충분하면 `unknown`으로 기록한다. `unknown` source는 current/latest claim을 지원할 수 없다.

## 8. Required Evidence Keys

모든 answer kind 공통:

- `doc.source_url`
- `doc.source_id`
- `doc.domain`
- non-empty `doc.body`

구조화 필드는 나중에 parser가 추가할 때 `metadata.structured.*` 아래에 둔다.

| Domain | Structured keys |
| --- | --- |
| dining | `meal_date`, `meal_type`, `location`, `menu_items` |
| shuttle | `route_or_stop`, `departure_time`, `effective_date`, `timetable_url` |
| notices | `title`, `posted_date`, `source_url` |
| academic_calendar | `event_name`, `date_span`, `academic_year` |

Phase A에서는 `current_fact`가 구조화 필드를 요구하면 대체로 fail-closed될 수 있다. 이는 의도된 동작이다.

## 9. Freshness Policy

입력:

- `question_time`: 기본 현재 시각
- `raw_fetched_at`: metadata에서 추출, 없으면 `None`

정책:

| Policy | Non-current | Current fact |
| --- | --- | --- |
| `snapshot` | `not_required` | `unknown` |
| `latest_snapshot` | `fresh` | fetched_at 7일 이내면 `fresh`, 오래되면 `stale`, 없으면 `unknown` |
| `short_ttl` | `not_required` | fetched_at 1일 이내면 `fresh`, 오래되면 `stale`, 없으면 `unknown` |
| `snapshot_with_term_check` | source navigation은 `fresh` | fetched_at 180일 이내이거나 structured effective date/term이 현재 학기와 맞으면 `fresh`, 없으면 `unknown` |

`official_chain_ok=False`이면서 `current_fact`이면 TTL과 무관하게 `unverified_source`로 본다.

## 10. Allowlist

Phase A allowlist:

- `*.cnu.ac.kr`
- `plus.cnu.ac.kr`
- `computer.cnu.ac.kr`
- `mobileadmin.cnu.ac.kr` only if registry `SourceSpec` exists

cached docs:

- `source_url` host가 allowlist에 맞으면 `allowlist_status=allowed`
- 아니면 `blocked` 또는 `unknown`

live fetch:

- fetch 전 source host가 allowlisted이고 `SourceSpec.active=True`여야 한다.
- redirect 후 final URL도 allowlisted이고 `cnu.ac.kr` registrable university domain을 유지해야 한다.
- open web search는 사용하지 않는다.

## 11. Conflict Rules

Phase A conflict detection은 구조화 metadata가 있는 경우만 수행한다. free text에서 숫자를 임의 추출해 conflict를 만들지 않는다.

비교 조건:

- 같은 domain
- 같은 requested slot scope
- 둘 이상의 comparable official docs

Conflict keys:

| Domain | Keys |
| --- | --- |
| graduation | `total_credits`, `major_credits`, `liberal_credits`, `curriculum_year`, `department` |
| dining | `meal_date`, `meal_type`, `location` |
| shuttle | `route_or_stop`, `departure_time`, `effective_date` |
| notices/calendar | `title/event_name`, `posted_date/date_span` |

같은 key에 서로 다른 non-empty value가 있으면 `conflict`로 보고 fail-closed한다.

## 12. RAG-vs-Fetch Truth Table

- unsupported intent -> unsupported/fail closed. 단, route domain이 5개 범위 안이고 registry가 category를 지원하면 no-docs/needs-fetch path로 계속 갈 수 있다.
- no docs -> candidate source가 있으면 `needs_fetch`, 없으면 `insufficient`.
- top score < `min_top_score` -> candidate source가 있으면 `needs_fetch`, 없으면 `insufficient`.
- `source_navigation` + allowed source URL + source status ok -> `sufficient`.
- `static_fact`/`procedural`에서 requested department/year slot match 또는 fact text가 없으면 candidate source가 있을 때 `needs_fetch`, 없으면 `insufficient`.
- `current_fact`에서 structured required keys가 없으면 official-chain 후보와 supported structured parser가 있을 때 `needs_fetch`, 아니면 `insufficient` 또는 `fetch_blocked_unsupported_parser`.
- `current_fact`에서 freshness가 stale/unknown/unverified이면 eligible candidate가 있을 때 `needs_fetch`, 없으면 `insufficient`.
- official chain false + current/latest claim -> `fetch_blocked_unofficial` / `insufficient`.
- conflict -> `conflict` / fail closed.
- 그 외에는 `sufficient`.

## 13. Controlled Fetch

Phase A supported parser:

```python
CONTROLLED_FETCH_SUPPORTED_PARSERS = {"html", "pdf", "hwp", "hwpx"}
```

이는 text extraction만 의미한다. `calendar`, `dining`, `shuttle`, `board_detail`은 구조화 validator가 생기기 전까지 `current_fact` fetch에서는 blocked로 둔다. cached docs의 `source_navigation`에는 사용할 수 있다.

`live_fetch_enabled=False`이면 실제 네트워크 호출 없이 decision만 기록한다.

## 14. Fail-Closed Output

blocked/failed 상태에서는 근거 없는 사실을 만들지 않는다.

표준 형태:

```text
공식 근거가 충분하지 않아 확답하기 어렵습니다.
확인 가능한 공식 출처는 [source_name]([url])입니다.
```

안전한 source URL이 없으면:

```text
공식 근거가 충분하지 않아 확답하기 어렵습니다.
```

출력 provenance에는 다음을 기록한다.

- full state trace
- `min_top_score`
- `answer_kind`
- source statuses
- fetch decision
- backend requested/used
- fallback_used
- failure reason

## 15. Integration Phases

### Phase A: Experimental Harness

- 새 state contract와 evaluator를 구현한다.
- injected generator로 단위 테스트와 smoke를 돌릴 수 있게 한다.
- production `batch.py`, `ui/app.py`, `evaluate_gold.py`는 아직 바꾸지 않는다.
- 5 categories x 2 questions smoke fixture를 만든다.

### Phase B: Task 2 Path Migration

10-question smoke가 통과하면 아래를 orchestrator로 옮긴다.

- `src/nlp_term/chat/batch.py`
- `src/nlp_term/ui/app.py`
- `src/nlp_term/chat/evaluate_gold.py`
- backend comparison path

`composer.py`는 deterministic baseline으로 유지한다.

### Phase C: Optional Task 3

- `src/nlp_term/chat/realtime.py`를 orchestrator로 옮긴다.
- `mode="realtime"`에서는 current/freshness gate를 더 엄격하게 적용한다.
- fetch/parser가 준비되지 않은 current_fact는 fail-closed한다.

### Phase D: Scale Evaluation

- category당 20개 또는 총 100개 수준의 harness evaluation을 수행한다.
- per-category sufficiency rate, fail-closed rate, answer validation rate, latency를 보고한다.
- 이 전에는 Task 2/3 readiness를 주장하지 않는다.

## 16. Verification

Phase A acceptance checks:

- source candidate selection tests
  - department/year exact match
  - central fallback source
  - current_fact official-chain filter
  - unsupported category
- freshness policy table tests
- allowlist cached/live redirect blocking tests
- required keys by answer kind tests
- conflict rule tests
  - structured metadata conflict only
  - no free-text conflict inference in Phase A
- RAG-vs-fetch truth table tests
- fail-closed output tests
  - unsupported numeric/date/menu/time facts must not appear
- 5 categories x 2 questions smoke
  - expected sufficiency/fetch decisions
  - trace schema validation
  - per-state latency reporting

## 17. Known Consequences

- Phase A will intentionally fail closed for many current/latest questions, especially dining, shuttle, and latest notice questions without structured fields.
- This is not a failure of Qwen. It is a harness signal that parser/source registry/data expansion work is required.
- Data expansion should happen after the harness contract is stable enough to define required metadata and structured fields.
- If Phase A proves too conservative, later phases can test Qwen as a constrained advisor or action proposer, but only behind the same state schema and validators.
