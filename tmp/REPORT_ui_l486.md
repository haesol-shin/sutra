# REPORT — ui.py 근거부족 답변 한국어화

## 변경
- `src/sutra/ui.py:486`의 근거부족 답변만 한국어화:
  - `I do not have enough evidence in this workspace to answer.`
  - `제공된 자료에서 확인할 수 있는 근거를 찾지 못했습니다.`
- `tests/sutra/test_ui.py`에 `TestAnswerLocalization.test_insufficient_evidence_answer_is_korean` 추가.

## 범위 확인
- UI 라벨과 액션 텍스트 `Search`, `Live Lookup`, `Sources`, `Helpful`, `Not helpful`, `Comment`는 유지.
- 기존 오류 문구 `**Error**: ...`는 유지.
- `tool_no_result` 한국어 꼬리 경로는 변경하지 않음.

## 테스트
- RED: `SUTRA_LEAN_TESTS=1 UV_CACHE_DIR=tmp/uv-cache uv run --no-sync pytest tests/sutra/test_ui.py::TestAnswerLocalization::test_insufficient_evidence_answer_is_korean -q`
  - 실패 확인: 기존 영어 답변 `I do not have enough evidence in this workspace to answer.` 때문에 실패.
- GREEN: `SUTRA_LEAN_TESTS=1 UV_CACHE_DIR=tmp/uv-cache uv run --no-sync pytest tests/sutra/test_ui.py::TestAnswerLocalization::test_insufficient_evidence_answer_is_korean -q`
  - `1 passed in 0.55s`
- 전체 UI 테스트: `SUTRA_LEAN_TESTS=1 UV_CACHE_DIR=tmp/uv-cache uv run --no-sync pytest tests/sutra/test_ui.py -q`
  - `20 passed, 1 skipped in 0.41s`
- 문자열 감사: `rg -n "I do not have enough evidence|Unable to fetch live data|Search|Live Lookup|Sources|Helpful|Not helpful|Comment|\\*\\*Error\\*\\*" src\\sutra\\ui.py tests\\sutra\\test_ui.py`
  - 요청 대상 영어 근거부족 답변은 `src/sutra/ui.py`에서 제거됨.
  - 남은 영어 문자열은 유지해야 하는 UI 라벨, 피드백 라벨, 소스 제목, 오류 문구, 테스트 단언뿐임.
