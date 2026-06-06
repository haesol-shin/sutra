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
