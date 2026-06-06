# Task 2 Local LLM Backend Results

작성일: 2026-06-07

## Current Decision

Task 2의 다음 구현 backend는 `llama.cpp + Qwen3.5-9B Q4_K_M GGUF`를 현실 후보로 둔다.

- 목표였던 `INT4 weight + FP8 KV cache` 중 weight 쪽은 Q4_K_M GGUF로 충족한다.
- llama.cpp b9538의 KV cache options에는 `fp8`이 없으므로, `q8_0`을 nearest 8-bit KV cache로 사용한다.
- exact `FP8 KV`는 vLLM XPU 후보에 남긴다. 다만 현재 로컬 Windows 환경에서는 vLLM XPU보다 llama.cpp Vulkan 경로가 먼저 실측 가능하다.

## Local Smoke Evidence

Model:

- repo: `unsloth/Qwen3.5-9B-GGUF`
- file: `Qwen3.5-9B-Q4_K_M.gguf`
- local path: `model/generator/Qwen3.5-9B-Q4_K_M.gguf`
- size: 5,680,522,464 bytes

Runtime:

- llama.cpp: b9538, Windows x64 Vulkan build
- GPU: Intel(R) Arc(TM) 130V GPU (16GB)
- context: 2048
- KV cache: `--cache-type-k q8_0 --cache-type-v q8_0`
- reasoning: `--reasoning off --reasoning-budget 0`
- mode: `--single-turn --simple-io`

Verbose runtime evidence from `model/llama_verbose_runtime.log`:

- `using device Vulkan0 (Intel(R) Arc(TM) 130V GPU (16GB)) ... 17622 MiB free`
- `offloaded 33/33 layers to GPU`
- `Vulkan0 model buffer size = 4861.28 MiB`
- `CPU_Mapped model buffer size = 545.62 MiB`
- `Vulkan0 KV buffer size = 34.00 MiB`
- `Vulkan0 compute buffer size = 98.28 MiB`

Interpretation:

- The Q4_K_M model loads and generates locally under the 15GB VRAM target.
- This is not exact FP8 KV proof. It is INT4-ish GGUF weight quantization plus llama.cpp nearest KV cache quantization.

## Generation Comparison

Command:

```powershell
uv run --extra llm python -m nlp_term.llm.llama_compare --output model/llama_task2_generation_compare.json
```

Result summary:

- rows: 2
- no-context returncodes: `[0, 0]`
- retrieval-context returncodes: `[0, 0]`
- no-context generation speed: about 10.7-12.2 tok/s
- retrieval-context generation speed: about 9.9-11.7 tok/s
- thinking marker: false for all compared outputs

Observed quality:

- no-context answers are natural but hallucinate or guess generic locations such as student portals, apps, or unofficial-looking URLs.
- retrieval-context answers are more source-aligned and cite the intended official source domains, but they can still over-specify details from noisy or truncated source chunks.
- deterministic composer remains useful as a control because it is terse and source-safe, but it is less natural than the local LLM output.

## Next Work

1. Clean retrieval evidence chunks further before feeding the LLM.
2. Add a Task 2 runtime wrapper that can call llama.cpp when the model file is present.
3. Keep deterministic composer as a controlled emergency path, not the preferred generator.
4. Run a larger source-backed QA set once available, because the current comparison only covers the small `data/test_chat.json` smoke input.
