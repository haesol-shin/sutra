#!/usr/bin/env bash
set -euo pipefail

COMMAND="${1:-batch}"
DATA_DIR="${NLP_TERM_DATA_DIR:-/data}"
OUTPUTS_DIR="${NLP_TERM_OUTPUTS_DIR:-/outputs}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT_DIR="$SCRIPT_DIR"
PY_PATH_SEP=":"
PY_WINDOWS_PATHS=0

if command -v cygpath >/dev/null 2>&1; then
  PY_SCRIPT_DIR="$(cygpath -w "$SCRIPT_DIR")"
  PY_PATH_SEP=";"
  PY_WINDOWS_PATHS=1
elif command -v wslpath >/dev/null 2>&1 && [ -x "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
  PY_SCRIPT_DIR="$(wslpath -w "$SCRIPT_DIR")"
  PY_PATH_SEP=";"
  PY_WINDOWS_PATHS=1
fi

export PYTHONPATH="$PY_SCRIPT_DIR/src${PYTHONPATH:+$PY_PATH_SEP$PYTHONPATH}"

if [ ! -d "$DATA_DIR" ]; then
  DATA_DIR="$PY_SCRIPT_DIR/data"
elif [ "$PY_WINDOWS_PATHS" = 1 ] && command -v cygpath >/dev/null 2>&1; then
  DATA_DIR="$(cygpath -w "$DATA_DIR")"
elif [ "$PY_WINDOWS_PATHS" = 1 ] && command -v wslpath >/dev/null 2>&1; then
  DATA_DIR="$(wslpath -w "$DATA_DIR")"
fi

if [ ! -d "$OUTPUTS_DIR" ]; then
  OUTPUTS_DIR="$PY_SCRIPT_DIR/outputs"
elif [ "$PY_WINDOWS_PATHS" = 1 ] && command -v cygpath >/dev/null 2>&1; then
  OUTPUTS_DIR="$(cygpath -w "$OUTPUTS_DIR")"
elif [ "$PY_WINDOWS_PATHS" = 1 ] && command -v wslpath >/dev/null 2>&1; then
  OUTPUTS_DIR="$(wslpath -w "$OUTPUTS_DIR")"
fi

if [ "$PY_WINDOWS_PATHS" = 1 ] && command -v uv.exe >/dev/null 2>&1; then
  RUNNER=(uv.exe --project "$PY_SCRIPT_DIR" run python)
elif command -v uv >/dev/null 2>&1; then
  RUNNER=(uv --project "$PY_SCRIPT_DIR" run python)
elif [ -x "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
  RUNNER=("$SCRIPT_DIR/.venv/Scripts/python.exe")
elif [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  RUNNER=("$SCRIPT_DIR/.venv/bin/python")
elif command -v py >/dev/null 2>&1; then
  RUNNER=(py -3)
elif command -v python3 >/dev/null 2>&1; then
  RUNNER=(python3)
elif command -v python >/dev/null 2>&1; then
  RUNNER=(python)
else
  echo "Python runtime not found. Install Python 3.10 or run through uv." >&2
  exit 127
fi

case "$COMMAND" in
  batch|--batch-only)
    "${RUNNER[@]}" -m nlp_term.chat.batch --input "$DATA_DIR/test_chat.json" --output "$OUTPUTS_DIR/chat_output.json"
    ;;
  ui|--ui)
    "${RUNNER[@]}" -m nlp_term.ui.app --host "${CHATBOT_HOST:-127.0.0.1}" --port "${CHATBOT_PORT:-7860}"
    ;;
  realtime|--realtime)
    "${RUNNER[@]}" -m nlp_term.chat.realtime --input "$DATA_DIR/test_realtime.json" --output "$OUTPUTS_DIR/realtime_output.json"
    ;;
  all)
    "${RUNNER[@]}" -m nlp_term.chat.batch --input "$DATA_DIR/test_chat.json" --output "$OUTPUTS_DIR/chat_output.json"
    "${RUNNER[@]}" -m nlp_term.chat.realtime --input "$DATA_DIR/test_realtime.json" --output "$OUTPUTS_DIR/realtime_output.json"
    ;;
  *)
    echo "Usage: ./chatbot.sh [batch|ui|realtime|all]" >&2
    exit 2
    ;;
esac
