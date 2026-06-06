# Data Expansion Failure Log

작성일: 2026-06-07

## Stage 0 Attempt 1: Knowledge Doc Count Below Gate

- step: Phase 1.1 Stage 0 Serial Source Loop
- command:
  - `uv run python -m nlp_term.prepare.from_sources --source-probe data/sources/source_probe.json --output data/knowledge_seed.json --failures-output data/source_parse_failures.json`
  - `uv run python -m nlp_term.validators --knowledge-quality data/knowledge_seed.json --source-probe data/sources/source_probe.json --min-total-docs 50 --min-docs-per-label 1 --min-body-chars 80 --min-source-parse-ratio 0.9`
- observed failure:
  - first generation produced 24 knowledge docs.
  - validator failed with `knowledge-quality: total docs 24 below 50`.
- suspected cause:
  - `from_sources.py` defaulted to 3 chunks per source, which is too small for the Stage 0 gate.
- next change:
  - added `--chunks-per-source` and raised the default to 9.
- result:
  - regenerated 53 knowledge docs.
  - knowledge quality validator passed.
- meeting loop opened: no.

## Stage 0 Attempt 2: Shell Path Invocation Error

- step: Phase 1.1 Chatbot Batch Smoke
- command:
  - `bash .\chatbot.sh batch`
- observed failure:
  - bash interpreted the path as `.chatbot.sh` and returned `No such file or directory`.
- suspected cause:
  - Windows PowerShell path escaping did not map to the bash path form.
- next change:
  - reran with `bash ./chatbot.sh batch`.
- result:
  - command wrote `outputs/chat_output.json`.
  - chat quality validator passed.
- meeting loop opened: no.

## Stage 0 Attempt 3: Auto Backend Timeout

- step: Stage 0 Review Repair Chatbot Batch Smoke
- command:
  - `bash ./chatbot.sh batch`
- observed failure:
  - command timed out after 124 seconds.
- suspected cause:
  - `NLP_TERM_CHAT_BACKEND=auto` selects the local llama backend when `llama-cli` and the GGUF model are present.
  - local llama generation completed in later probes, but it is much slower than deterministic smoke output and can exceed short command timeouts.
- next change:
  - add an explicit backend argument to `chatbot.sh`, so PowerShell users can run `bash ./chatbot.sh batch deterministic` without relying on environment propagation into bash.
  - keep local llama backend evaluation as a separate backend decision task.
- result:
  - `bash ./chatbot.sh batch deterministic` wrote `outputs/chat_output.json` in a bounded smoke run.
  - direct module rerun with `uv run python -m nlp_term.chat.batch --input data/test_chat.json --output outputs/chat_output.json --knowledge data/knowledge_seed.json --backend deterministic` completed quickly.
  - evidence-alignment validation is handled by the Stage 0 review repair gate.
- meeting loop opened: no.

## Stage 0 Attempt 4: Bash Environment Probe Timeout

- step: Stage 0 Review Repair Chatbot Backend Check
- command:
  - `$env:NLP_TERM_CHAT_BACKEND='deterministic'; bash -lc 'echo BACKEND=$NLP_TERM_CHAT_BACKEND'`
- observed failure:
  - the bash process printed an empty backend value.
  - PowerShell-set environment variables were not visible inside the WSL/bash process.
- suspected cause:
  - environment propagation across the PowerShell to WSL/bash boundary is not reliable for this command style.
- next change:
  - use `bash ./chatbot.sh batch deterministic` or direct `uv run python -m nlp_term.chat.batch ... --backend deterministic` for evidence-alignment validation.
  - keep `chatbot.sh` runtime/back-end reliability as a later backend decision task.
- result:
  - explicit `chatbot.sh` backend argument and direct batch module output both passed `--require-evidence-alignment`.
- meeting loop opened: no.
