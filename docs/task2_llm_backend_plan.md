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
- PyTorch/Transformers stack: 현재 `uv` 환경에는 `torch`, `transformers`, `accelerate`, `bitsandbytes`, `vllm`, `llama_cpp`가 설치되어 있지 않음
- Level Zero SDK: `LEVEL_ZERO_V1_SDK_PATH` 존재

따라서 로컬 검증 기준에서는 CUDA 전용 경로를 기본 백엔드로 둘 수 없다. Intel Arc/XPU 또는 Intel GPU를 지원하는 GGUF runner 계열을 먼저 검증한다.

## Backend 후보

### 1. PyTorch XPU + Transformers

장점:

- Python 코드와 직접 통합하기 쉽다.
- 로컬 머신의 Intel Arc/XPU 방향과 맞다.
- PyTorch 문서는 Intel Client GPU에 대한 XPU 지원과 `torch.xpu.is_available()` 확인 경로를 제공한다.

검증 필요:

- Qwen3.5-9B 계열을 INT4 weight로 실제 로딩 가능한가.
- FP8 KV cache를 이 경로에서 정확히 설정할 수 있는가.
- 정확한 FP8 KV가 안 되면 가장 가까운 지원 설정과 품질/VRAM 차이를 기록한다.

### 2. GGUF runner with Intel GPU backend

장점:

- INT4 weight 모델을 다루기 좋다.
- `llama.cpp`는 Intel GPU용 SYCL backend를 지원한다.
- Python 의존성보다 독립 실행형 검증이 쉬울 수 있다.

검증 필요:

- Qwen3.5-9B quantized artifact가 텍스트 QA에 충분히 안정적인가.
- runner가 정확한 FP8 KV cache를 지원하는지, 아니면 Q8/Q4 등 다른 KV cache quantization만 지원하는지 확인한다.
- exact FP8 KV가 아니면 `nearest_supported_kv_cache`로 기록하고, INT4 weight + nearest KV 기준으로 별도 비교한다.

### 3. vLLM

장점:

- Qwen3.5 model card는 vLLM/SGLang/Transformers 호환성을 명시한다.
- vLLM 문서는 FP8 KV cache 설정을 제공한다.

제약:

- vLLM FP8 KV 문서는 CUDA/ROCm 중심 지원을 명시한다.
- 현재 로컬 머신에는 CUDA/NVIDIA backend가 없다.
- 따라서 로컬 기본 백엔드가 아니라, 별도 환경 검증 후보로 둔다.

## 검증 기준

로컬 LLM backend는 아래를 통과해야 Task 2 기본 경로가 될 수 있다.

1. Capability probe
   - command: `uv run python -m nlp_term.llm.env_probe --output model/llm_backend_probe.json`
   - pass: GPU, driver, installed packages, available runner, quantization support 판단이 JSON으로 기록된다.

2. Load probe
   - target: Qwen3.5-9B INT4 weight + FP8 KV cache.
   - pass: context 2048, batch 1에서 로딩 및 1개 질문 생성 성공.
   - memory: peak GPU memory 15GB 이하.
   - if exact FP8 KV unsupported: nearest supported KV cache setting을 기록하고 계속 비교한다.

3. Quality probe
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
- [llama.cpp repository](https://github.com/ggml-org/llama.cpp)
