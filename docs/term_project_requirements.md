# 자연어처리 Term Project 요구조건 정리

작성일: 2026-06-05

참조 문서:
- `docs/2026_자연어처리_term_project.pdf`
- `docs/2_term_project_QA.pdf`

## 1. 과제 해석

본 과제의 주제는 충남대학교 재학생을 위한 `Campus ChatBot` 구축이다.

`2_term_project_QA.pdf`는 과제 주제를 대체하는 문서가 아니라, Campus ChatBot을 LLM 기반 Q/A 시스템으로 구현할 때의 보완 조건으로 해석한다. 따라서 최종 구현은 충남대학교 학사/생활 정보를 대상으로 하는 챗봇이어야 하며, RAG 또는 LLM-QA 방식은 선택 가능한 구현 방식으로 본다.

## 2. 핵심 과제

### Task 1. 질문 유형 분류기

사용자 질문을 다음 5개 카테고리 중 하나로 분류한다.

| 라벨 | 카테고리 | 예시 범위 |
| --- | --- | --- |
| 0 | 졸업요건 | 졸업학점, 전공/교양 졸업 요건 |
| 1 | 학교 공지사항 | 학교 공지, 학과 공지 |
| 2 | 학사일정 | 수강 신청, 수강 정정, 학기 일정 |
| 3 | 식단 안내 | 교내 식당 주간/일일 식단 |
| 4 | 통학/셔틀 버스 | 버스 시간표, 정류장 위치, 운행 여부 |

평가 조건:
- 정량 평가 대상이다.
- F1 Score로 평가된다.
- 평가 시 `/data/test_cls.json`에 대해 작동해야 한다.
- 실행 결과는 `/outputs/cls_output.json`으로 생성해야 한다.
- 배점은 40점이다.

입력 예시 구조:

```json
[
  {
    "question": "졸업까지 몇 학점을 들어야 하나요?"
  }
]
```

출력 예시 구조:

```json
[
  {
    "question": "졸업까지 몇 학점을 들어야 하나요?",
    "label": 0
  }
]
```

### Task 2. 챗봇 모델 및 UI

질문 유형과 질문 내용을 바탕으로 적절한 응답을 생성하는 챗봇 모델과 웹 기반 UI를 구현한다.

필수 UI 기능:
- 사용자가 직접 질문을 입력할 수 있어야 한다.
- 챗봇 응답을 확인할 수 있어야 한다.
- 대화 흐름이 표시되어야 한다.

평가 조건:
- 정성 평가 대상이다.
- UI 구동 여부: 10점
- Chat Interface 형식 구현 여부: 10점
- 질문 맥락에 알맞은 응답: 40점
- 총 배점은 60점이다.
- 평가 시 `/data/test_chat.json`에 대해 작동해야 한다.
- 실행 결과는 `/outputs/chat_output.json`으로 생성해야 한다.
- UI는 작동 영상으로도 평가된다.

입력 예시 구조:

```json
[
  {
    "user": "이번 학기 수강신청은 언제 시작하나요?"
  }
]
```

출력 예시 구조:

```json
[
  {
    "user": "이번 학기 수강신청은 언제 시작하나요?",
    "model": "이번 학기 수강신청 일정은 학사일정 공지를 기준으로 확인해야 합니다."
  }
]
```

### Task 3. 실시간 정보 반영

실시간 업데이트가 필요한 정보에 대해 최신 정보를 반영한 응답을 제공한다.

대상 예시:
- 통학/셔틀 버스
- 식단 안내
- 학교/학과 공지사항
- 학사일정 변경

가능한 구현 방식:
- RAG
- Crawling
- 외부 데이터 동기화
- Tool call

평가 조건:
- Optional 과제이다.
- 정성 평가 대상이다.
- 실제 정보와의 동기화 정확성을 평가한다.
- 평가 시 `/data/test_realtime.json`에 대해 작동해야 한다.
- 실행 결과는 `/outputs/realtime_output.json`으로 생성해야 한다.
- 배점은 30점이다.

입력 예시 구조:

```json
[
  {
    "user": "가장 최근에 올라온 공지사항은 언제 게시되었나요?"
  }
]
```

출력 예시 구조:

```json
[
  {
    "user": "가장 최근에 올라온 공지사항은 언제 게시되었나요?",
    "model": "가장 최근 공지사항은 ..."
  }
]
```

## 3. 데이터 조건

필수 조건:
- 학사 관련 데이터를 직접 수집해야 한다.
- 데이터를 카테고리별로 분류하고 라벨링된 데이터셋을 구축해야 한다.
- 이미 구축된 데이터셋을 그대로 사용하는 것은 금지된다.
- 데이터 구축은 수동 또는 자동 방식 모두 가능하다.

권장 조건:
- 성능을 빠르게 확인하여 사용할 언어와 데이터 범위를 결정한다.
- 필요하다면 추가 LLM 훈련을 고려할 수 있다.

해석:
- 공개 웹페이지, 공지사항, 식단표, 학사일정, 셔틀버스 안내 등 원천 정보를 직접 수집해 가공하는 것은 허용되는 것으로 본다.
- 이미 완성된 QA 데이터셋이나 분류 데이터셋을 그대로 가져와 사용하는 것은 금지되는 것으로 본다.

## 4. 실행 및 디렉터리 조건

평가에 사용되는 주요 실행 파일:
- `src/classifier.ipynb`
- `chatbot.sh`

문서에 따르면 평가 시 `classifier.ipynb`와 `chatbot.sh`만 실행한다. 따라서 다음 조건을 만족해야 한다.

- `classifier.ipynb`는 `/data/test_cls.json`을 읽고 `/outputs/cls_output.json`을 생성해야 한다.
- `chatbot.sh`는 챗봇 UI 실행과 JSON 출력 생성을 지원해야 한다.
- Optional Task를 수행하는 경우 `chatbot.sh` 또는 그 내부 호출 경로를 통해 `/outputs/realtime_output.json` 생성이 가능해야 한다.

문서상 예시 디렉터리 구조:

```text
Termproject_{이름}/
  data/
    test_cls.json
    test_chat.json
    test_realtime.json
  src/
    classifier.ipynb
    chatbot_ui.py
    realtime_model.py
  model/
    model.bin
  chatbot.sh
  outputs/
    cls_output.json
    chat_output.json
    realtime_output.json
  requirements.txt
  README.md
```

빨간색으로 표시된 평가 경로는 그대로 유지해야 한다. 세부 파일 구성은 유동적으로 조정할 수 있지만, 평가자가 기대하는 입력/출력 경로와 실행 파일명은 보존해야 한다.

## 5. 환경 및 패키지 조건

지정 환경:
- Python 3.10.12
- torch 2.5.1
- Pytorch-lightning 2.4.0, 사용할 경우

현재 개발환경:
- `uv`를 사용한다.
- `.python-version`은 `3.10.12`로 고정한다.
- `pyproject.toml`의 `xpu` extra는 현재 로컬 개발 기본값으로 `torch==2.9.1`과 `pytorch-triton-xpu==3.5.0`을 PyTorch XPU index에서 설치하도록 설정한다.
- 아직 구현 코드에서 사용하지 않는 RAG/UI/training 패키지는 optional extra로 미리 추가하지 않는다.
- 참고 repo `../aidm-term-proj`의 uv/XPU 패턴을 따르되, 이 과제 문서의 Python/torch 버전을 우선한다.
- 현재 Windows 로컬에서는 `torch 2.5.1+xpu` 설치는 성공하지만 `c10_xpu.dll` 의존 DLL 문제로 import가 실패한다.
- 같은 머신의 참고 repo에서는 `torch 2.9.1+xpu`가 import되고 XPU 사용 가능 상태로 확인된다.
- 따라서 개발 기본값은 `torch 2.9.1+xpu`로 두되, 최종 제출 전 과제 문서의 `torch 2.5.1` 조건과의 차이를 다시 검토한다.

허용 조건:
- 필요한 패키지를 추가 설치할 수 있다.
- LangChain, Chroma 등 외부 도구를 사용할 수 있다.
- 직접 만든 Python 라이브러리도 사용할 수 있다.

제출 조건:
- 본인 local에 설치한 패키지 정보를 `requirements.txt`로 제출한다.
- 문서에서는 다음 명령을 예시로 제시한다.

```bash
pip freeze > requirements.txt
```

## 6. 제출 조건

제출 방식:
- 사이버캠퍼스 제출
- 전체 코드 압축 후 제출
- 파일명: `Termproject_{이름}.zip`

제출물:
- 소스코드
- 모델 파일 또는 다운로드 링크
- 발표자료
- UI 작동 영상
- `requirements.txt`
- README

추가 조건:
- Colab 환경에서 실행 가능한 `.ipynb` 또는 `.py` 형식으로 제출한다.
- 용량이 큰 모델 파일은 Google Drive에 올리고 다운로드 가능하도록 공유할 수 있다.
- 제출 전 코드가 정상 작동하는지 확인해야 한다.
- UI 작동 영상은 2분 내외이다.
- 발표 자료는 5분 내외이며, 구현 방법과 챗 인터페이스 동작 여부를 포함해야 한다.

마감:
- 제출 기한은 `6월 12일(금) 23:59`로 해석한다.

## 7. 현재 합의한 해석

현재까지의 대화에서 합의한 해석은 다음과 같다.

- QA 문서의 LLM/RAG 설명은 Campus ChatBot 과제를 보완하는 조건으로 본다.
- RAG는 필수 조건으로 확정하지 않는다.
- 기본 점수 100점에 해당하는 Task 1과 Task 2의 완성도를 우선한다.
- Task 3 실시간 정보 반영은 Optional로 본다.
- Optional 30점은 기본 100점에 더해지는 가산점으로 본다.
- Task 1은 정량 평가이므로 Task 2/3 응답 생성과 실행 경로를 분리하는 것을 우선 검토한다.
- Task 1 모델 선택 기준은 모델 크기가 아니라 F1 Score, 클래스별 성능, 추론 시간, 모델 파일 크기, Colab/평가 환경 재현성이다.
- Task 2와 Task 3는 같은 응답 파이프라인을 공유할 수 있으나, Task 3는 실시간 정보 조회 실패 시 기본 응답으로 fallback할 수 있어야 한다.

## 8. 미확정 질문

다음 조건은 아직 명확하지 않으며, 추후 확인 또는 설계 시 결정이 필요하다.

1. Task 1 분류 모델을 어느 수준의 모델로 구현할 것인가?
   - 가벼운 분류 모델로 충분한지, 더 큰 언어모델 또는 임베딩 기반 접근이 필요한지는 실험으로 결정해야 한다.
   - 후보군은 TF-IDF + Logistic Regression/SVM, KLUE/BERT 계열 fine-tuning, 임베딩 기반 분류, LLM prompting 분류 등을 비교할 수 있다.

2. Task 2에 RAG를 기본 적용할 것인가?
   - RAG를 사용하면 학교 정보 기반 응답의 정확성과 사실성을 높일 수 있다.
   - 반면 구현 복잡도, 데이터 정제, 제출 환경 재현성 리스크가 증가한다.

3. Task 3를 RAG + tool call로 구현할 것인가?
   - 실시간 정보 반영에는 tool call 또는 crawling이 자연스럽다.
   - 단, 네트워크 실패와 평가 환경 차이를 고려해 fallback 전략이 필요하다.

4. `chatbot.sh`의 책임 범위는 어디까지인가?
   - UI 실행만 담당하는지, `chat_output.json`과 `realtime_output.json` 생성까지 담당해야 하는지 명확하지 않다.
   - 문서상 평가 시 `classifier.ipynb`와 `chatbot.sh`만 실행한다고 되어 있으므로, 보수적으로는 `chatbot.sh`가 JSON 생성까지 지원해야 한다.

## 9. 다음 단계

이 문서를 기준으로 다음을 순서대로 결정한다.

1. Task 1 후보 모델과 실험 기준
2. Task 2의 기본 응답 생성 구조
3. RAG 적용 여부와 범위
4. Task 3 optional 구현 여부
5. 최종 디렉터리 구조와 실행 명령
6. README와 제출 체크리스트
