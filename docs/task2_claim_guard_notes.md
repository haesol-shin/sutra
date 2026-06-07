# Task 2 Claim Guard Notes

작성일: 2026-06-07

## 목적

Task 2 vertical slice smoke에서 자연스러운 답변은 생성됐지만, 근거에 없는 URL, 기관명, 수치, 메뉴 경로를 모델이 만들어낼 수 있는 위험이 확인됐다.

이 문서는 데이터셋 강화 전에 적용한 0.5단계 최소 안전장치를 기록한다.

## 적용한 최소 변경

- Task 2 prompt에 근거 없는 URL, 기관명, 수치, 메뉴명을 새로 만들지 말라는 문장을 추가했다.
- `validate_task2_answer()`가 `evidence_texts`를 받을 때 답변의 URL, 수치 claim, 기관명 claim, 메뉴 claim을 evidence text와 대조한다.
- `run_task2_vertical_slice()`는 생성 답변을 검증할 때 현재 `EvidencePack` 텍스트를 validator에 넘긴다.
- 검증 실패는 retry나 deterministic fallback으로 덮지 않고 artifact에 그대로 남긴다.

## 의도적으로 하지 않은 것

- 프롬프트를 최적화했다고 주장하지 않는다.
- 한국어 prompt와 영어 prompt 중 어느 쪽이 더 좋은지 아직 결정하지 않는다.
- LLM judge나 외부 LLM API를 inference-time 검증에 쓰지 않는다.
- 숫자, 기관명, 메뉴명 검증을 완전한 사실성 판정기로 보지 않는다. 현재 guard는 명백한 unsupported claim을 잡는 얇은 방어선이다.

## 다음 순서

이 guard는 데이터 확장을 시작하기 전 큰 누수만 막기 위한 조치다. 다음 본 작업은 졸업요건, 교육과정, PDF/HWP 중심의 데이터셋 강화다.

Prompt 언어, 표현 방식, answer formatting은 데이터 확장 후 Task 2 smoke 결과를 다시 본 뒤 조정한다.
