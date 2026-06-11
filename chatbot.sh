#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1
export UV_CACHE_DIR="${UV_CACHE_DIR:-$SCRIPT_DIR/.uv-cache}"

COMMAND="${1:-all}"
WORKSPACE_REL="${SUTRA_WORKSPACE_REL:-examples/cnu-campus/sutra.toml}"
WORKSPACE_ARGS=()
if [ -z "${SUTRA_WORKSPACE:-}" ]; then
  WORKSPACE_ARGS=(--workspace "$WORKSPACE_REL")
fi

PY_SCRIPT_DIR="$SCRIPT_DIR"
PY_PATH_SEP=":"
if command -v cygpath >/dev/null 2>&1; then
  PY_SCRIPT_DIR="$(cygpath -w "$SCRIPT_DIR")"
  PY_PATH_SEP=";"
elif command -v wslpath >/dev/null 2>&1 && [ -x "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
  PY_SCRIPT_DIR="$(wslpath -w "$SCRIPT_DIR")"
  PY_PATH_SEP=";"
fi
export PYTHONPATH="$PY_SCRIPT_DIR/src${PYTHONPATH:+$PY_PATH_SEP$PYTHONPATH}"

PYTHON_CMD=()
SUTRA_CMD=()

select_python() {
  if [ -x "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
    PYTHON_CMD=("$SCRIPT_DIR/.venv/Scripts/python.exe")
  elif [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_CMD=("$SCRIPT_DIR/.venv/bin/python")
  elif command -v py >/dev/null 2>&1; then
    PYTHON_CMD=(py -3)
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=(python3)
  elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD=(python)
  else
    echo "ERROR: Python runtime not found. Install Python 3.10+." >&2
    return 127
  fi
}

select_sutra() {
  if command -v uv.exe >/dev/null 2>&1; then
    SUTRA_CMD=(uv.exe --project "$PY_SCRIPT_DIR" run sutra)
  elif command -v uv >/dev/null 2>&1; then
    SUTRA_CMD=(uv --project "$SCRIPT_DIR" run sutra)
  else
    SUTRA_CMD=("${PYTHON_CMD[@]}" -m sutra.cli)
  fi
}

ensure_uv() {
  if command -v uv.exe >/dev/null 2>&1 || command -v uv >/dev/null 2>&1; then
    return 0
  fi
  echo "Installing uv..."
  "${PYTHON_CMD[@]}" -m pip install -q uv
}

uv_pip_install() {
  if command -v uv.exe >/dev/null 2>&1; then
    uv.exe pip install --system "$@"
  elif command -v uv >/dev/null 2>&1; then
    uv pip install --system "$@"
  else
    "${PYTHON_CMD[@]}" -m uv pip install --system "$@"
  fi
}

plain_pip_install() {
  "${PYTHON_CMD[@]}" -m pip install "$@"
}

install_with_uv_or_pip() {
  if ensure_uv; then
    uv_pip_install "$@" || plain_pip_install "$@"
  else
    plain_pip_install "$@"
  fi
}

python_can_import() {
  "${PYTHON_CMD[@]}" - "$1" <<'PY' >/dev/null 2>&1
import importlib.util
import sys
raise SystemExit(0 if importlib.util.find_spec(sys.argv[1]) else 1)
PY
}

setup_python_deps() {
  if [ "${SUTRA_SKIP_DEPS:-0}" = "1" ]; then
    echo "SUTRA_SKIP_DEPS=1; skipping dependency installation."
    return 0
  fi

  echo "Ensuring Python dependencies..."
  install_with_uv_or_pip -r requirements.txt || return $?
  install_with_uv_or_pip -e ".[rag,ui,legacy]" || return $?

  if python_can_import llama_cpp; then
    echo "llama-cpp-python is already importable."
    return 0
  fi

  extra_index=()
  if [ "$(uname -s 2>/dev/null || echo unknown)" = "Linux" ] && command -v nvidia-smi >/dev/null 2>&1; then
    extra_index=(--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121)
    echo "Installing llama-cpp-python CUDA wheel candidate..."
  else
    echo "Installing llama-cpp-python..."
  fi
  install_with_uv_or_pip "llama-cpp-python[server]>=0.3.28" "${extra_index[@]}"
}

shell_path() {
  local candidate="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -u "$candidate" 2>/dev/null || printf '%s\n' "$candidate"
  else
    printf '%s\n' "$candidate"
  fi
}

resolved_model_path() {
  "${SUTRA_CMD[@]}" llama serve "${WORKSPACE_ARGS[@]}" --n-ctx "${SUTRA_N_CTX:-4096}" --dry-run |
    sed -n 's/^Resolved model path: //p' |
    tail -n 1
}

ensure_model() {
  local model_path
  model_path="$(resolved_model_path)"
  if [ -z "$model_path" ]; then
    echo "ERROR: Could not resolve model path." >&2
    return 1
  fi

  local model_file
  model_file="$(shell_path "$model_path")"
  if [ -f "$model_file" ]; then
    echo "Model found: $model_path"
    return 0
  fi

  if [ "${SUTRA_SKIP_MODEL_DOWNLOAD:-0}" = "1" ]; then
    echo "WARNING: Model missing at $model_path; SUTRA_SKIP_MODEL_DOWNLOAD=1, skipping download." >&2
    return 0
  fi

  echo "Model missing at $model_path"
  echo "Downloading Qwen GGUF from Hugging Face. Rough ETA on Colab T4: 1-5 minutes depending on network."
  HF_HUB_ENABLE_HF_TRANSFER=1 "${SUTRA_CMD[@]}" llama download "${WORKSPACE_ARGS[@]}"
}

health_ready() {
  "${SUTRA_CMD[@]}" llama health "${WORKSPACE_ARGS[@]}" >/dev/null 2>&1
}

start_server_if_needed() {
  if [ "${SUTRA_SKIP_SERVER:-0}" = "1" ]; then
    echo "SUTRA_SKIP_SERVER=1; skipping llama-server startup."
    return 0
  fi
  if health_ready; then
    echo "llama-server is already healthy."
    return 0
  fi

  local log_path="${SUTRA_LLAMA_LOG:-$SCRIPT_DIR/outputs/llama-server.log}"
  mkdir -p "$(dirname "$log_path")"
  echo "Starting llama-server in the background; log: $log_path"
  ("${SUTRA_CMD[@]}" llama serve "${WORKSPACE_ARGS[@]}" --n-ctx "${SUTRA_N_CTX:-4096}" >"$log_path" 2>&1) &
  local pid=$!
  echo "$pid" > "$SCRIPT_DIR/outputs/llama-server.pid"

  local timeout="${SUTRA_HEALTH_TIMEOUT:-180}"
  local elapsed=0
  while [ "$elapsed" -lt "$timeout" ]; do
    if health_ready; then
      echo "llama-server is healthy."
      return 0
    fi
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      echo "ERROR: llama-server exited before becoming healthy. See $log_path" >&2
      return 1
    fi
    if [ $((elapsed % 10)) -eq 0 ]; then
      echo "Waiting for llama-server health... ${elapsed}s/${timeout}s"
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done

  echo "ERROR: llama-server did not become healthy within ${timeout}s. See $log_path" >&2
  return 1
}

cmd_setup() {
  select_python || return $?
  select_sutra
  setup_python_deps || return $?
  select_sutra

  if [ "${SUTRA_ECHO:-0}" = "1" ]; then
    echo "SUTRA_ECHO=1; setup skips model download and server startup."
    return 0
  fi

  ensure_model || return $?
  start_server_if_needed
}

validate_output() {
  local path="$1"
  "${PYTHON_CMD[@]}" - "$path" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    print(f"ERROR: missing output file: {path}", file=sys.stderr)
    raise SystemExit(1)
rows = json.loads(path.read_text(encoding="utf-8"))
if not isinstance(rows, list) or not rows:
    print(f"ERROR: output is missing or empty: {path}", file=sys.stderr)
    raise SystemExit(1)
for index, row in enumerate(rows):
    if not str(row.get("model", "")).strip():
        print(f"ERROR: output row {index} has an empty model answer: {path}", file=sys.stderr)
        raise SystemExit(1)
print(f"Verified non-empty output: {path} ({len(rows)} rows)")
PY
}

cmd_batch() {
  select_python || return $?
  select_sutra
  local args=(batch --input data/test_chat.json --output outputs/chat_output.json "${WORKSPACE_ARGS[@]}")
  if [ "${SUTRA_ECHO:-0}" = "1" ]; then
    args+=(--echo)
  fi
  "${SUTRA_CMD[@]}" "${args[@]}" || return $?
  validate_output outputs/chat_output.json
}

cmd_realtime() {
  select_python || return $?
  select_sutra
  local args=(batch --input data/test_realtime.json --output outputs/realtime_output.json --live "${WORKSPACE_ARGS[@]}")
  if [ "${SUTRA_ECHO:-0}" = "1" ]; then
    args+=(--echo)
  fi
  "${SUTRA_CMD[@]}" "${args[@]}" || return $?
  validate_output outputs/realtime_output.json
}

cmd_ui() {
  select_python || return $?
  select_sutra
  local args=(ui "${WORKSPACE_ARGS[@]}")
  if [ "${SUTRA_ECHO:-0}" = "1" ]; then
    args+=(--echo)
  fi
  "${SUTRA_CMD[@]}" "${args[@]}"
}

print_ui_hint() {
  echo
  echo "To launch the UI later, run:"
  echo "  bash chatbot.sh ui"
}

FAILURES=0
run_stage() {
  local name="$1"
  shift
  echo
  echo "==> $name"
  if "$@"; then
    echo "OK: $name"
  else
    local rc=$?
    echo "ERROR: $name failed with exit code $rc" >&2
    FAILURES=$((FAILURES + 1))
  fi
}

case "$COMMAND" in
  setup)
    run_stage setup cmd_setup
    ;;
  batch)
    run_stage batch cmd_batch
    ;;
  realtime)
    run_stage realtime cmd_realtime
    ;;
  ui)
    cmd_ui
    exit $?
    ;;
  all)
    run_stage setup cmd_setup
    run_stage batch cmd_batch
    run_stage realtime cmd_realtime
    print_ui_hint
    ;;
  *)
    echo "Usage: bash chatbot.sh [setup|batch|realtime|ui|all]" >&2
    exit 2
    ;;
esac

if [ "$FAILURES" -gt 0 ]; then
  echo "Completed with $FAILURES failed stage(s)." >&2
  exit 1
fi
