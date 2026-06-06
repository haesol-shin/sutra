# NLP Term Project Architecture Plan

작성일: 2026-06-06

이 문서는 현재 대화에서 확정한 구현 방향을 정리한다. 원문 과제 조건은 `docs/term_project_requirements.md`를 기준으로 유지하고, 이 문서는 구현 구조와 의사결정의 기준으로 사용한다.

## 1. 확정 결정

- 우선순위는 `Task 1 분류기 -> Task 2 챗봇/UI -> Task 3 최소 실시간 구현`이다.
- `src/classifier.ipynb`는 Task 1 평가 진입점으로 고정한다.
- `chatbot.sh`는 repository root의 Task 2/3 평가 진입점으로 고정한다.
- 실제 로직은 `src/nlp_term/` 아래 Python 모듈에 둔다.
- UI는 Gradio로 구현한다.
- Task 3는 최소 구현으로 진행한다. 공지, 학사일정, 셔틀, 식단 중 검증된 source부터 처리하고 실패 시 cached/static fallback을 사용한다.
- 최종 제출 환경은 Colab 기준 Python 3.10.12와 과제 문서의 `torch 2.5.1`을 우선한다.
- 로컬 Windows XPU 개발 환경은 `torch 2.9.1+xpu`를 개발용으로 유지하되, 최종 제출 runtime 기준으로 삼지 않는다.
- 최종 inference time에는 외부 LLM API를 사용하지 않는다.
- MCP나 full LLM tool-call agent는 제출 runtime 핵심 경로에 넣지 않는다.
- Task 2의 기본 generator 목표는 로컬 LLM이다. 1차 후보는 Qwen3.5-9B이며, 목표 quantization은 INT4 weight + FP8 KV cache다.
- deterministic composer는 Task 2의 비교 기준, 디버그 기준, 비상 경로로 유지한다. 기본 제출 경로로 승격하려면 로컬 LLM 경로가 모델 로딩 또는 품질 gate를 통과하지 못했다는 증거가 필요하다.

## 2. 전체 데이터 흐름

```text
공식 CNU source
  -> collect/*
  -> RawSource, SourceVerification
  -> prepare/normalize.py
  -> KnowledgeDoc
  -> retrieve/index.py

KnowledgeDoc
  -> prepare/cls_data.py
  -> ClassificationExample
  -> classify/train.py
  -> model/classifier.joblib

Task 1:
src/classifier.ipynb
  -> nlp_term.classify.predict.predict_file()
  -> data/test_cls.json
  -> outputs/cls_output.json

Task 2:
chatbot.sh batch
  -> nlp_term.chat.batch.run_chat_file()
  -> classify.predict_label()
  -> retrieve.rank_docs()
  -> local Qwen3.5-9B generator target
  -> deterministic composer reference/emergency path
  -> outputs/chat_output.json

Task 2 UI:
chatbot.sh ui
  -> nlp_term.ui.app
  -> Gradio ChatInterface
  -> same router/retriever/composer/generator path

Task 3:
chatbot.sh realtime
  -> verified live fetch if available
  -> cached KnowledgeDoc fallback
  -> outputs/realtime_output.json
```

## 3. 파일 구조

```text
chatbot.sh
data/
model/
  classifier.joblib
  generator/                  # optional, local <=9B model only
outputs/
src/
  classifier.ipynb
  nlp_term/
    __init__.py
    paths.py
    schemas.py
    validators.py

    collect/
      base.py
      graduation.py
      notices.py
      academic_calendar.py
      dining.py
      shuttle.py
      run_collect.py

    prepare/
      normalize.py
      knowledge.py
      cls_data.py
      split.py

    classify/
      features.py
      train.py
      predict.py
      evaluate.py
      cli.py

    retrieve/
      index.py
      rank.py

    chat/
      router.py
      templates.py
      composer.py
      batch.py
      realtime.py
      generator_gate.py

    ui/
      app.py
      state.py
```

구현 초기에는 기능을 작은 파일로 나누되, 불필요하게 세분화하지 않는다. 예를 들어 baseline 학습과 embedding 실험은 `classify/train.py --strategy baseline|embedding` 형태로 한 파일에서 관리한다.

## 4. Source 계획

| Label | Domain | Source | Parser 전략 | 리스크/검증 |
| ---: | --- | --- | --- | --- |
| 0 | graduation | `https://plus.cnu.ac.kr/html/kr/25file/2025_book.pdf` | PDF text extraction, page/section 보존 | 표 추출 오류 가능. 학과별 요건은 scope 제한 필요 |
| 1 | notices | `plus.cnu.ac.kr` 학사정보 board, `sub07_0702` | board list/detail HTML parse | notice id, pagination, attachments 검증 필요 |
| 2 | academic_calendar | `https://plus.cnu.ac.kr/_prog/academic_calendar/?menu_dvs_cd=05020101&site_dvs_cd=kr` | calendar DOM/date/event parse | 날짜 정규화와 연도/학기 parameter 확인 |
| 3 | dining | `https://mobileadmin.cnu.ac.kr/food/index.jsp`, `https://www.cnucoop.co.kr/` | mobileadmin 식단 table parse, cnucoop은 official discovery chain 검증 | date parameter, encoding, 공식 연결고리 검증 필요 |
| 4 | shuttle | `https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html` | timetable table parse | 운행 기간/학기/개정일 checksum 기록 |

식단 source는 더 이상 source 없음 상태가 아니다. 다만 `mobileadmin`의 파라미터와 `cnucoop`의 공식 링크 연결을 검증하기 전에는 live 식단 답변을 단정하지 않는다. 검증 전에는 cached/static 안내로 fallback한다.

## 5. Schema 계약

주요 schema는 `src/nlp_term/schemas.py`에 둔다.

```python
class RawSource(BaseModel):
    source_id: str
    label: int
    domain: str
    url: str
    fetched_at: str
    content_type: str
    raw_path: str
    status_code: int | None
    checksum: str

class SourceVerification(BaseModel):
    source_id: str
    official_chain_ok: bool
    parser_name: str
    parser_version: str
    evidence: list[str]
    warnings: list[str]
    verified_at: str

class KnowledgeDoc(BaseModel):
    doc_id: str
    label: int
    domain: str
    title: str
    body: str
    date: str | None
    source_url: str
    source_id: str
    section: str | None
    metadata: dict

class ClassificationExample(BaseModel):
    question: str
    label: int
    source_doc_id: str | None
    generation_method: str
    validated: bool

class ChatInput(BaseModel):
    user: str

class ChatOutput(BaseModel):
    user: str
    model: str

class RealtimeOutput(BaseModel):
    user: str
    model: str
```

모든 출력 파일은 `validators.py`를 통과한 뒤 저장한다.

## 6. Task 1 전략

Task 1은 학습 기반 분류가 기본이다.

1. 공식 source에서 `KnowledgeDoc`을 만든다.
2. `KnowledgeDoc` 기반으로 클래스별 질문을 만든다.
3. label 생성은 self-consistency로 검증한다.
4. 먼저 `TF-IDF char/word n-gram + LogisticRegression/LinearSVC` baseline을 학습한다.
5. 필요하면 `Qwen3-Embedding-0.6B + classifier`를 비교한다.
6. 최종 모델은 F1, 클래스별 성능, 추론 시간, 제출 재현성을 기준으로 선택한다.

Self-consistency 규칙:

- offline LLM/API는 labeling, paraphrase, review 보조에만 사용한다.
- 5 vote를 기본으로 한다.
- 4/5 이상 일치하면 accept.
- 3/5 이하 또는 schema 오류는 quarantine/review bucket으로 보내고 자동 학습 데이터에서는 제외한다.
- 수동 검증은 최종 품질 감사 단계에서 권장하지만, 현재 구현 단계의 성공 조건에는 넣지 않는다.
- audit log에는 question, source_id, vote labels, final label, confidence, reviewer_override를 남긴다.

## 7. Task 2 전략

Task 2는 Gradio UI와 batch JSON 출력을 모두 지원한다.

기본 답변 경로:

```text
question
  -> classifier/router
  -> label/domain별 retrieval
  -> local Qwen3.5-9B generator target
  -> deterministic composer reference/emergency path
  -> ChatOutput
```

Qwen3.5-9B는 기본 generator 목표다. composer는 자연스러운 응답 생성기의 대체재가 아니라 품질 비교 기준과 비상 경로로 유지한다.

Generator gate:

- 모델 크기 9B 이하.
- 외부 API 사용 금지.
- INT4 weight + FP8 KV cache 목표. backend가 정확한 FP8 KV cache를 지원하지 않으면 nearest supported KV cache 설정을 기록하고 별도 비교한다.
- 로컬 Arc/XPU 또는 Intel GPU backend에서 load 성공.
- context 2048 smoke, context 4096 제출 후보 기준 peak VRAM이 15GB 이하.
- 10개 대표 질문 batch가 10분 안에 완료.
- no-context generation보다 retrieval-context generation의 source/domain alignment가 높음.
- deterministic composer보다 문장 자연성이 낮지 않음.
- fallback output 사용률을 최소화함.

## 8. Task 3 최소 구현

Task 3는 최소 구현으로 진행한다.

대상 우선순위:

1. 공지 latest fetch
2. 학사일정 live/cached fetch
3. 셔틀 live/cached fetch
4. 식단 live fetch는 parser 검증 후 enable

네트워크 실패, parser 실패, source 미검증 시에는 cached/static KnowledgeDoc 기반 답변을 생성한다. 파일 생성 자체는 실패하지 않도록 한다.

## 9. 실행 계약

`src/classifier.ipynb`:

- top-to-bottom 실행 가능해야 한다.
- 기본 입력은 `data/test_cls.json` 또는 `/data/test_cls.json`이다.
- 기본 출력은 `outputs/cls_output.json` 또는 `/outputs/cls_output.json`이다.
- 출력 row는 `{ "question": str, "label": int }` 형태다.
- 입력 순서를 보존한다.

`chatbot.sh`:

```bash
./chatbot.sh
./chatbot.sh batch
./chatbot.sh ui
./chatbot.sh realtime
```

- 인자 없음 또는 `batch`: `data/test_chat.json`을 읽고 `outputs/chat_output.json` 생성.
- `ui`: Gradio UI 실행.
- `realtime`: `data/test_realtime.json`을 읽고 `outputs/realtime_output.json` 생성.
- UI는 batch 출력의 전제 조건이 아니다.

## 10. 검증 명령

```powershell
uv run python -c "import nlp_term; print('import-ok')"
```

```powershell
uv run python -m nlp_term.validators --check-all --data-dir data --outputs-dir outputs
```

```powershell
uv run python -m nlp_term.classify.cli --input data/test_cls.json --output outputs/cls_output.json --dry-run
```

```powershell
uv run jupyter nbconvert --execute src/classifier.ipynb --to notebook --inplace
```

```powershell
uv run python -m nlp_term.chat.batch --input data/test_chat.json --output outputs/chat_output.json --dry-run
```

```powershell
bash chatbot.sh batch
```

```powershell
uv run python -m nlp_term.ui.app --host 127.0.0.1 --port 7860 --smoke-test
```

Optional Task 3:

```powershell
uv run python -m nlp_term.chat.realtime --input data/test_realtime.json --output outputs/realtime_output.json --dry-run
```

## 11. 남은 리스크

- 과제 문서의 `torch 2.5.1`과 로컬 XPU 개발용 `torch 2.9.1+xpu`가 다르다.
- Qwen3.5-9B INT4 + FP8 KV target은 로컬 backend 실측 전까지 안정성을 보장할 수 없다.
- CNU 사이트 HTML 구조가 바뀌면 crawler가 깨질 수 있다.
- 식단 endpoint의 date parameter와 공식 chain 검증이 필요하다.
- 졸업요건은 학과별 차이가 있으므로 답변 scope를 명시해야 한다.
