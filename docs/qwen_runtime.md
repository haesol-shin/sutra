# Qwen Runtime Notes

작성일: 2026-06-08 (갱신 2026-06-12)

이 문서는 로컬 Qwen 실행 정보를 고정해 두기 위한 문서다. 매번 model directory를 재귀 탐색하지 말고, 아래 경로와 명령을 먼저 사용한다.

> **참고(2026-06-12):** 아래 예시의 `context: 4096` / `-c 4096`은 초기 값이며, 현재 운영/채점 경로(`chatbot.sh`)는 `--n-ctx 8192`를 사용한다. 강제 툴 경로의 2차 호출(시스템 프롬프트 + RAG + 라이브 증거)이 4096을 초과하기 때문이다.

## Canonical Model

현재 Task 2 writer 기본 후보:

```text
model/generator/Qwen3.5-9B-Q4_K_M.gguf
```

Model metadata:

- source repo: `unsloth/Qwen3.5-9B-GGUF`
- file: `Qwen3.5-9B-Q4_K_M.gguf`
- quantization: Q4_K_M GGUF
- local backend: llama.cpp
- local GPU: Intel(R) Arc(TM) 130V GPU (16GB)

`model/`은 `.gitignore` 대상이다. 모델 파일 존재 여부만 확인하면 된다.

```powershell
Test-Path model\generator\Qwen3.5-9B-Q4_K_M.gguf
```

## Backend Contract

현재 로컬 실행 기본값:

```text
backend: llama.cpp llama-server
context: 4096
KV cache: q8_0 / q8_0
reasoning: off
reasoning budget: 0
```

주의:

- 프로젝트 목표였던 `INT4 weight + FP8 KV cache` 중 weight 쪽은 Q4_K_M으로 충족한다.
- llama.cpp 현재 로컬 경로에서는 exact FP8 KV가 아니라 `q8_0` KV를 사용한다.
- exact FP8 KV는 vLLM/XPU 후보로 남아 있지만, 현재 검증된 실사용 경로는 llama.cpp다.

## Health Probe

과거 실행 가능 여부 확인 명령(현재는 **removed/historical**): `nlp_term.llm.env_probe` was removed with `src/nlp_term/` on 2026-06-13, so this command is no longer runnable. The dated backend probe result below is kept as a historical record.

```powershell
uv run python -X utf8 -m nlp_term.llm.env_probe --output model/llm_backend_probe_now.json --pretty
```

2026-06-08 확인 결과:

```text
pytorch_xpu_stack_available=True
gguf_runner_available=True
llama-cli: found
llama-server: found
exact_int4_weight_fp8_kv_supported_locally=False
```

## Start Llama Server

과거 임시 실험용 서버 실행 예시(현재는 **removed/historical**): the `nlp_term.llm.env_probe` helper was removed with `src/nlp_term/` on 2026-06-13, so this command is no longer runnable. It is preserved only with the dated probe notes below.

```powershell
$llama = (& uv run python -X utf8 -c "from nlp_term.llm.env_probe import executable_path; print(executable_path('llama-server') or '')").Trim()
$model = "model\generator\Qwen3.5-9B-Q4_K_M.gguf"
& $llama -m $model -c 4096 -ngl auto --cache-type-k q8_0 --cache-type-v q8_0 --host 127.0.0.1 --port 18080 --reasoning off --reasoning-budget 0
```

다른 터미널에서 health check:

```powershell
Invoke-WebRequest http://127.0.0.1:18080/health -UseBasicParsing
```

## Run Sample Through Server

Sutra uses the OpenAI-compatible chat completions endpoint provided by `llama-server`. You can query it using `sutra.llama.LlamaClient`:

```powershell
uv run python -X utf8 - <<'PY'
from sutra.llama import LlamaClient
from sutra.models import Message

client = LlamaClient(base_url="http://127.0.0.1:18080")
result = client.chat(
    messages=[
        Message(role="user", content="너는 충남대학교 학생을 돕는 챗봇이다.\n\n질문: 셔틀 시간표 어디서 봐?\n\n짧게 답변:")
    ],
    max_tokens=160,
)
print(result.content)
PY
```

PowerShell here-doc 호환이 불편하면 `python -c` 또는 임시 파일을 사용한다.

## Live Sample Results

2026-06-08에 `llama-server`로 실제 생성 확인을 했다. 서버는 정상 로드됐고, 3개 RAG evidence-pack 질문을 처리했다.

Runtime:

```text
context: 4096
KV cache: q8_0 / q8_0
generation speed: about 6.2 tok/s
reasoning marker: disabled
```

Sample 1:

```text
Q: 생화학과 졸업요건은 어디서부터 확인하면 돼?

A: 생화학과 졸업요건은 학과 공식 홈페이지의 '학사정보 > 졸업요건' 메뉴에서 확인하실 수 있습니다.

입학 연도에 따라 기준이 다를 수 있으므로, 본인의 교육과정 년도에 맞는 내용을 먼저 확인하시는 것이 좋습니다. 주요 요건으로는 전공 81 과목 중 130 학점 이상 이수, 초교양 필수 13 학점, 균형교양 및 소양교양을 포함한 총 36~48 학점 이상 이수 등이 있습니다.

더 정확한 정보는 아래 링크를 통해 직접 확인하시기 바랍니다.
https://biochemistry.cnu.ac.kr/biochemistry/info/requirements.do
```

Sample 2:

```text
Q: 학사일정표는 어디서 확인해?

A: 충남대학교 학사일정은 충남대학교 홈페이지 (plus.cnu.ac.kr)의 '학사일정' 메뉴에서 확인하실 수 있습니다.

학기별 주요 일정 (등록금 납부, 수강신청, 개강일, 학위수여식 등) 은 시점에 따라 변동될 수 있으므로, 가장 정확한 정보는 공식 홈페이지를 통해 확인하시는 것을 권장합니다.
```

Sample 3:

```text
Q: 셔틀 시간표 어디서 봐?

A: 충남대학교 셔틀버스 시간표는 학교 셔틀버스 운영 안내 페이지에서 확인하실 수 있습니다.

주요 운행 노선과 시간은 다음과 같습니다.
* 교내 순환 (대덕캠퍼스 내): 08:20 (월평역 등교)부터 17:30까지 운행
* 캠퍼스 순환 (대덕캠퍼스 ↔ 보운캠퍼스): 08:10 (골프연습장 출발)부터 08:50 (회차 보운캠퍼스)까지 운행

※ 운행 시간표는 학교 사정, 교통 상황, 행사 등에 따라 변경될 수 있으니, 정확한 최신 정보는 공식 홈페이지를 참고하시기 바랍니다.
```

## Quality Notes

- 모델은 정상 작동하고 답변은 자연스럽다.
- 그대로 신뢰하면 안 된다. 첫 번째 샘플의 `전공 81 과목 중 130 학점` 같은 표현은 source chunk noise와 숫자 claim 조립 문제가 섞인 것으로 보인다.
- 따라서 다음 품질 병목은 모델 실행이 아니라 evidence chunk cleaning, numeric claim validation, answer validator 강화다.

## Do Not Repeat

다음 작업에서 모델 실행 상태를 확인할 때는 이 순서만 따르면 된다.

1. `Test-Path model\generator\Qwen3.5-9B-Q4_K_M.gguf`
2. 필요하면 위 `llama-server` 명령으로 서버 실행
3. `sutra doctor` 또는 `sutra llama health` 명령으로 로컬 서버 상태 검증:
   ```powershell
   uv run python -m sutra.cli doctor --workspace examples/cnu-campus/sutra.toml
   ```
4. Python 코드에서는 `sutra.llama.LlamaClient` 사용

모델 파일명을 다시 찾기 위해 `Get-ChildItem -Recurse model`부터 시작하지 않는다.
