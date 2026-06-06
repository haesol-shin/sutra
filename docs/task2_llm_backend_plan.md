# Task 2 Local LLM Backend Plan

작성일: 2026-06-06

## 결정

Task 2의 기본 응답 생성 후보는 로컬 LLM이다. 목표 설정은 다음과 같다.

- Model: `Qwen/Qwen3.5-9B`를 1차 후보로 둔다.
- Size cap: 9B 이하.
- Quantization target: INT4 weight + FP8 KV cache.
- Context: 2048을 1차 smoke 기준, 4096을 제출 후보 기준으로 둔다.
- Batch: 1.
- VRAM gate: peak GPU memory 15GB 이하.
- Runtime: 최종 inference time에 외부 LLM API, MCP, full LLM tool-call agent를 사용하지 않는다.

`deterministic composer`는 기본 생성기가 아니라 비교 기준, 디버그 기준, 비상 경로다. Task 2의 정성 평가 목표가 자연스러운 응답이므로, 모델 로딩과 품질이 통과하면 로컬 LLM 경로를 우선한다.

## 현재 로컬 환경 관찰

2026-06-06 기준 로컬 머신 관찰:

- GPU: Intel(R) Arc(TM) 130V GPU (16GB)
- Driver: 32.0.101.8826
- CUDA/NVIDIA backend: `nvidia-smi` 없음
- PyTorch XPU: `uv sync --extra xpu` 후 `torch 2.9.1+xpu`, `torch.xpu.is_available() == True`, XPU total memory 약 16837MB 확인
- Transformers/runtime stack: `uv sync --extra xpu --extra llm` 후 `transformers 5.10.2`, `accelerate 1.13.0` 설치 확인
- Qwen3.5 tokenizer smoke: `AutoConfig`와 `AutoTokenizer`는 `Qwen/Qwen3.5-9B`를 읽고 chat template을 렌더링한다.
- Multimodal processor note: `AutoProcessor`는 video/image processor 경로에서 `torchvision`을 요구한다. Task 2는 text-only QA이므로 현재 smoke는 `AutoTokenizer` 기준으로 둔다.
- 아직 미설치: `bitsandbytes`, `vllm`, `llama_cpp`, `llama-cli`, `llama-server`, `ollama`
- Level Zero SDK: `LEVEL_ZERO_V1_SDK_PATH` 존재

따라서 로컬 검증 기준에서는 CUDA 전용 경로를 기본 백엔드로 둘 수 없다. 우선순위는 `PyTorch XPU + Transformers` smoke, 그 다음 `vLLM XPU` 또는 Intel GPU 지원 GGUF runner 검증이다.

## Backend 후보

Hub metadata scan 결과, Qwen3.5-9B 계열 실행 후보는 base model이 아니라 quantized artifact 단위로 추적한다.

- `RedHatAI/Qwen3.5-9B-quantized.w4a16`: INT4 W4A16, vLLM/LLM Compressor 계열 후보. `INT4 weight + FP8 KV cache` 목표와 가장 직접적으로 맞는 후보지만, 로컬 Windows에서 vLLM XPU 설치 가능성이 먼저 확인되어야 한다.
- `unsloth/Qwen3.5-9B-GGUF`: Q4_K_M 약 5.68GB 등 여러 GGUF quantization을 제공한다. 15GB VRAM feasibility에는 유리하지만 exact FP8 KV cache는 runner 지원 여부가 불확실하다.
- `Intel/Qwen3.5-9B-int4-AutoRound`: Intel stack을 의식한 INT4 후보로 보인다. 로컬 Intel/XPU 실험 후보지만 KV FP8 지원은 별도 backend 증거가 필요하다.

### 1. PyTorch XPU + Transformers

장점:

- Python 코드와 직접 통합하기 쉽다.
- 로컬 머신의 Intel Arc/XPU 방향과 맞다.
- PyTorch 문서는 Intel Client GPU에 대한 XPU 지원과 `torch.xpu.is_available()` 확인 경로를 제공하며, 현재 로컬에서 이 경로가 실제로 통과했다.

검증 필요:

- Qwen3.5-9B 계열을 INT4 weight로 실제 로딩 가능한가.
- FP8 KV cache를 이 경로에서 정확히 설정할 수 있는가.
- 정확한 FP8 KV가 안 되면 가장 가까운 지원 설정과 품질/VRAM 차이를 기록한다.

### 2. vLLM XPU

장점:

- Qwen3.5 model card는 vLLM/SGLang/Transformers 호환성을 명시한다.
- vLLM 문서는 Intel GPU/XPU backend를 제공한다.
- vLLM XPU platform 문서는 `VLLM_ATTENTION_BACKEND=TRITON_ATTN`일 때 `fp8_e4m3`, `fp8_e5m2`, `fp8` KV cache dtype을 지원한다고 명시한다.
- vLLM quantization 표는 Intel GPU에서 AWQ/GPTQ를 지원 대상으로 표시한다.

검증 필요:

- 로컬 Windows에서 vLLM XPU 설치가 가능한가. 공식 XPU 설치 문서는 Linux/oneAPI 중심이므로 Windows local proof가 막힐 수 있다.
- Qwen3.5-9B INT4 artifact가 vLLM XPU의 Intel GPU 지원 quantization 경로와 맞는가.
- `VLLM_ATTENTION_BACKEND=TRITON_ATTN` + `kv_cache_dtype=fp8` 조합으로 context 2048/4096을 통과하는가.

### 3. GGUF runner with Intel GPU backend

장점:

- INT4 weight 모델을 다루기 좋다.
- `llama.cpp`는 Intel GPU용 SYCL backend를 지원한다.
- Python 의존성보다 독립 실행형 검증이 쉬울 수 있다.
- `llama.cpp`에서 model weight quantization은 GGUF 파일 선택으로 결정된다. 예: `Q4_K_M`, `IQ4_XS`, `Q5_K_M`.
- KV cache는 `--cache-type-k`, `--cache-type-v`로 별도 설정한다. 일반적으로 `f16`, `q8_0`, `q4_0` 같은 ggml type을 사용하며, 이는 vLLM의 FP8 KV cache와 동일한 옵션이 아니다.

검증 필요:

- Qwen3.5-9B quantized artifact가 텍스트 QA에 충분히 안정적인가.
- runner가 정확한 FP8 KV cache를 지원하는지, 아니면 Q8/Q4 등 다른 KV cache quantization만 지원하는지 확인한다.
- exact FP8 KV가 아니면 `nearest_supported_kv_cache`로 기록하고, INT4 weight + nearest KV 기준으로 별도 비교한다.

예상 smoke command:

```powershell
llama-server `
  -m models/Qwen3.5-9B-Q4_K_M.gguf `
  -c 4096 `
  -ngl 999 `
  --cache-type-k q8_0 `
  --cache-type-v q8_0
```

## 검증 기준

로컬 LLM backend는 아래를 통과해야 Task 2 기본 경로가 될 수 있다.

1. Capability probe
   - command: `uv run python -m nlp_term.llm.env_probe --output model/llm_backend_probe.json`
   - pass: GPU, driver, installed packages, available runner, quantization support 판단이 JSON으로 기록된다.

2. Prompt preflight
   - command: `uv run python -m nlp_term.llm.prompt_eval --output model/task2_prompt_preflight.json`
   - pass: no-context, retrieval-context, deterministic composer baseline이 같은 입력 set에서 비교되고, retrieval-context prompt가 context 2048/4096 budget 안에 들어오는지 기록된다.

3. Load probe
   - target: Qwen3.5-9B INT4 weight + FP8 KV cache.
   - pass: context 2048, batch 1에서 로딩 및 1개 질문 생성 성공.
   - memory: peak GPU memory 15GB 이하.
   - if exact FP8 KV unsupported: nearest supported KV cache setting을 기록하고 계속 비교한다.

4. Quality probe
   - compare:
     - no-context LLM generation
     - retrieval-context LLM generation
     - deterministic composer baseline
   - pass:
     - retrieval-context 답변이 no-context보다 source/domain alignment에서 높아야 한다.
     - deterministic composer보다 자연스러운 문장성이 낮으면 안 된다.
     - fallback output 사용률은 최소화한다.

## 참고 source

- [Qwen/Qwen3.5-9B model card](https://huggingface.co/Qwen/Qwen3.5-9B)
- [PyTorch Intel GPU/XPU guide](https://docs.pytorch.org/docs/2.12/notes/get_start_xpu.html)
- [vLLM Quantized KV Cache](https://docs.vllm.ai/en/latest/features/quantization/quantized_kvcache/)
- [vLLM XPU platform API](https://docs.vllm.ai/en/v0.11.0/api/vllm/platforms/xpu.html)
- [vLLM XPU installation](https://docs.vllm.ai/en/v0.6.4/getting_started/xpu-installation.html)
- [llama.cpp repository](https://github.com/ggml-org/llama.cpp)
