#!/usr/bin/env bash
# CNU Campus ChatBot — Task 2 (chat) + Task 3 (realtime) entrypoint.
#
# Run with NO arguments:   bash chatbot.sh
#
# It bootstraps the full runtime by cloning the public Sutra repo, installing
# dependencies with uv, downloading the GGUF model, and starting llama-server.
# Then it asks (with a 30s timeout, default = generate files):
#   [Enter]  -> generate grading outputs: outputs/chat_output.json + realtime
#   u        -> launch the interactive Chainlit UI behind a public tunnel
#
# The package ships only the bootstrap + inputs + classifier; all source code,
# corpus, and prompts are pulled fresh from GitHub so they stay editable.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# --- configuration (all env-overridable for rehearsal) ---------------------
CLONE_URL="${SUTRA_CLONE_URL:-https://github.com/haesol-shin/sutra.git}"
CLONE_REF="${SUTRA_CLONE_REF:-submission}"

# Fast local disk for the clone + multi-GB model (avoid Drive FUSE + quota).
if [ -d /content ]; then
  RUNTIME_DIR="${SUTRA_RUNTIME_DIR:-/content/sutra_runtime}"
else
  RUNTIME_DIR="${SUTRA_RUNTIME_DIR:-$SCRIPT_DIR/.runtime}"
fi
REPO_DIR="$RUNTIME_DIR/repo"
WORKSPACE="$REPO_DIR/examples/cnu-campus/sutra.toml"

export SUTRA_MODEL_DIR="${SUTRA_MODEL_DIR:-$RUNTIME_DIR/models}"
export SUTRA_CLASSIFIER_PATH="${SUTRA_CLASSIFIER_PATH:-$SCRIPT_DIR/model/classifier.joblib}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$RUNTIME_DIR/uv-cache}"
# 4096 fits the short grading inputs with room for RAG + tool context and keeps
# GPU memory headroom on a 15GB T4. Override with SUTRA_N_CTX for longer context.
N_CTX="${SUTRA_N_CTX:-4096}"

mkdir -p "$RUNTIME_DIR" "$SCRIPT_DIR/outputs" "$SUTRA_MODEL_DIR"

PYTHON_CMD=()
SUTRA_CMD=()

# --- helpers ----------------------------------------------------------------
log() { echo "[chatbot] $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

preflight() {
  # The classifier is shipped in the zip (the clone's model/ is gitignored), so
  # the router can only find it via this absolute path. Fail loudly if missing.
  if [ ! -f "$SUTRA_CLASSIFIER_PATH" ]; then
    fail "classifier not found at SUTRA_CLASSIFIER_PATH=$SUTRA_CLASSIFIER_PATH (expected in the unzipped package)."
  fi
  log "classifier: $SUTRA_CLASSIFIER_PATH"
}

clone_or_update_repo() {
  if [ -d "$REPO_DIR/.git" ]; then
    log "Updating existing clone ($CLONE_REF) ..."
    git -C "$REPO_DIR" fetch --depth 1 origin "$CLONE_REF" \
      && git -C "$REPO_DIR" checkout -q FETCH_HEAD \
      || log "WARNING: update failed; reusing existing clone."
  else
    log "Cloning $CLONE_URL ($CLONE_REF) -> $REPO_DIR"
    rm -rf "$REPO_DIR"
    git clone --depth 1 --branch "$CLONE_REF" "$CLONE_URL" "$REPO_DIR" \
      || fail "git clone failed (is the repo public and does branch '$CLONE_REF' exist?)."
  fi
  [ -f "$WORKSPACE" ] || fail "workspace missing in clone: $WORKSPACE"
  log "workspace: $WORKSPACE"
}

select_python() {
  if [ -n "${SUTRA_PYTHON:-}" ] && [ -x "$SUTRA_PYTHON" ]; then
    PYTHON_CMD=("$SUTRA_PYTHON")
  elif [ -x "$REPO_DIR/.venv/Scripts/python.exe" ]; then
    PYTHON_CMD=("$REPO_DIR/.venv/Scripts/python.exe")
  elif [ -x "$REPO_DIR/.venv/bin/python" ]; then
    PYTHON_CMD=("$REPO_DIR/.venv/bin/python")
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=(python3)
  elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD=(python)
  else
    fail "Python 3.10+ not found."
  fi
}

ensure_uv() {
  command -v uv >/dev/null 2>&1 && return 0
  log "Installing uv ..."
  "${PYTHON_CMD[@]}" -m pip install -q uv
}

uv_install() {
  # Install editable clone + runtime extras into the active interpreter.
  if command -v uv >/dev/null 2>&1; then
    uv pip install --system -e "$REPO_DIR[rag,ui,legacy]" || return 1
  else
    "${PYTHON_CMD[@]}" -m pip install -e "$REPO_DIR[rag,ui,legacy]" || return 1
  fi
}

python_can_import() {
  "${PYTHON_CMD[@]}" - "$1" <<'PY' >/dev/null 2>&1
import importlib.util, sys
raise SystemExit(0 if importlib.util.find_spec(sys.argv[1]) else 1)
PY
}

install_llama_cpp() {
  if python_can_import llama_cpp; then
    log "llama-cpp-python already importable."
    return 0
  fi
  # The abetlen CUDA index publishes a prebuilt 0.3.28 wheel tagged
  # py3-none-linux_x86_64; pinning the exact version makes pip pick that wheel
  # instead of building PyPI's sdist from source (slow + CPU-only).
  local spec="llama-cpp-python[server]==0.3.28"
  local index=()
  if command -v nvidia-smi >/dev/null 2>&1; then
    index=(--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121)
    log "Installing llama-cpp-python 0.3.28 (CUDA wheel) ..."
  else
    log "WARNING: no GPU detected (nvidia-smi absent). Select a Colab GPU runtime (T4) — CPU inference of a 9B model is far too slow for grading."
    log "Installing llama-cpp-python 0.3.28 (CPU) ..."
  fi
  if command -v uv >/dev/null 2>&1; then
    uv pip install --system "$spec" "${index[@]}" \
      || "${PYTHON_CMD[@]}" -m pip install "$spec" "${index[@]}"
  else
    "${PYTHON_CMD[@]}" -m pip install "$spec" "${index[@]}"
  fi
  python_can_import llama_cpp \
    || fail "llama-cpp-python is not importable after install; aborting before the 5.5GB model download."
}

setup_deps() {
  if [ "${SUTRA_SKIP_DEPS:-0}" = "1" ]; then
    log "SUTRA_SKIP_DEPS=1; skipping dependency install."
    return 0
  fi
  ensure_uv
  log "Installing Sutra + extras from clone ..."
  uv_install || fail "dependency install failed."
  install_llama_cpp || fail "llama-cpp-python backend install failed."
}

resolved_model_path() {
  "${SUTRA_CMD[@]}" llama serve --workspace "$WORKSPACE" --n-ctx "$N_CTX" --dry-run \
    | sed -n 's/^Resolved model path: //p' | tail -n 1
}

ensure_model() {
  local model_path model_file
  model_path="$(resolved_model_path)"
  [ -n "$model_path" ] || fail "could not resolve model path."
  model_file="$model_path"
  command -v cygpath >/dev/null 2>&1 && model_file="$(cygpath -u "$model_path" 2>/dev/null || echo "$model_path")"
  if [ -f "$model_file" ]; then
    log "Model present: $model_path"
    return 0
  fi
  if [ "${SUTRA_SKIP_MODEL_DOWNLOAD:-0}" = "1" ]; then
    log "WARNING: model missing; SUTRA_SKIP_MODEL_DOWNLOAD=1, skipping download."
    return 0
  fi
  log "Downloading Qwen GGUF (~5.5GB; several minutes on a Colab T4) -> $SUTRA_MODEL_DIR"
  # No HF_HUB_ENABLE_HF_TRANSFER: hf_transfer is not a declared dependency and
  # enabling it without the package raises ImportError at download time.
  "${SUTRA_CMD[@]}" llama download --workspace "$WORKSPACE"
}

health_ready() { "${SUTRA_CMD[@]}" llama health --workspace "$WORKSPACE" >/dev/null 2>&1; }

cleanup_stale_servers() {
  # A llama-server launched from a previous run keeps holding the GPU (terminal
  # background processes survive notebook/kernel restarts), so a new one OOMs.
  # Only called when no healthy server is reachable, so we never kill a good one.
  if command -v pkill >/dev/null 2>&1; then
    pkill -9 -f "sutra.cli llama serve" 2>/dev/null || true
    pkill -9 -f "llama_cpp.server" 2>/dev/null || true
    sleep 2
  fi
}

start_server() {
  if [ "${SUTRA_SKIP_SERVER:-0}" = "1" ]; then
    log "SUTRA_SKIP_SERVER=1; skipping llama-server startup."
    return 0
  fi
  if health_ready; then
    log "llama-server already healthy."
    return 0
  fi
  cleanup_stale_servers
  local log_path="$RUNTIME_DIR/llama-server.log"
  log "Starting llama-server (n_ctx=$N_CTX, log: $log_path) ..."
  ("${SUTRA_CMD[@]}" llama serve --workspace "$WORKSPACE" --n-ctx "$N_CTX" >"$log_path" 2>&1) &
  local pid=$! timeout="${SUTRA_HEALTH_TIMEOUT:-300}" elapsed=0
  while [ "$elapsed" -lt "$timeout" ]; do
    health_ready && { log "llama-server healthy."; return 0; }
    kill -0 "$pid" 2>/dev/null || { echo "ERROR: llama-server exited early. See $log_path" >&2; return 1; }
    [ $((elapsed % 15)) -eq 0 ] && log "waiting for llama-server health... ${elapsed}s/${timeout}s"
    sleep 2; elapsed=$((elapsed + 2))
  done
  echo "ERROR: llama-server not healthy within ${timeout}s. See $log_path" >&2
  return 1
}

validate_output() {
  local path="$1"
  "${PYTHON_CMD[@]}" - "$path" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
if not isinstance(rows, list) or not rows:
    print(f"ERROR: output missing or empty: {path}", file=sys.stderr); raise SystemExit(1)
for i, row in enumerate(rows):
    if not str(row.get("model", "")).strip():
        print(f"ERROR: row {i} has empty answer: {path}", file=sys.stderr); raise SystemExit(1)
print(f"Verified non-empty output: {path} ({len(rows)} rows)")
PY
}

summarize_provenance() {
  # Non-fatal heads-up: warn (do not fail) if any row used the deterministic fallback.
  local out="$1" prov="${1%.json}.provenance.json"
  [ -f "$prov" ] || return 0
  "${PYTHON_CMD[@]}" - "$prov" <<'PY'
import json, sys
from pathlib import Path
rows = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
fb = [r for r in rows if r.get("mode") == "fallback"]
print(f"  provenance: {len(rows)} rows, {len(fb)} fallback")
if fb:
    print(f"  WARNING: {len(fb)} row(s) used the deterministic fallback (degraded answer).")
PY
}

run_batch() {
  local name="$1" input="$2" output="$3"; shift 3
  echo; log "==> $name"
  "${SUTRA_CMD[@]}" batch --input "$input" --output "$output" --workspace "$WORKSPACE" "$@" \
    || { echo "ERROR: $name batch failed." >&2; return 1; }
  validate_output "$output" || return 1
  summarize_provenance "$output"
}

generate_outputs() {
  local rc=0
  run_batch "Task 2 (chat)"     "$SCRIPT_DIR/data/test_chat.json"     "$SCRIPT_DIR/outputs/chat_output.json"     || rc=1
  run_batch "Task 3 (realtime)" "$SCRIPT_DIR/data/test_realtime.json" "$SCRIPT_DIR/outputs/realtime_output.json" --live || rc=1
  echo
  if [ "$rc" -eq 0 ]; then
    log "DONE. Outputs in: $SCRIPT_DIR/outputs/"
  else
    echo "ERROR: one or more stages failed." >&2
  fi
  return "$rc"
}

ensure_cloudflared() {
  command -v cloudflared >/dev/null 2>&1 && { CF=cloudflared; return 0; }
  CF="$RUNTIME_DIR/cloudflared"
  if [ ! -x "$CF" ]; then
    log "Downloading cloudflared ..."
    curl -fsSL -o "$CF" \
      https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
      || return 1
    chmod +x "$CF"
  fi
}

launch_ui() {
  local port="${SUTRA_UI_PORT:-8000}"
  log "Starting Chainlit UI on 127.0.0.1:$port ..."
  ("${SUTRA_CMD[@]}" ui --workspace "$WORKSPACE" --host 127.0.0.1 --port "$port" \
    >"$RUNTIME_DIR/ui.log" 2>&1) &
  local ui_pid=$!
  if ensure_cloudflared; then
    log "Opening public tunnel ..."
    ("$CF" tunnel --url "http://localhost:$port" >"$RUNTIME_DIR/cloudflared.log" 2>&1) &
    local elapsed=0 url=""
    while [ "$elapsed" -lt 30 ]; do
      url="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$RUNTIME_DIR/cloudflared.log" 2>/dev/null | head -n1)"
      [ -n "$url" ] && break
      sleep 1; elapsed=$((elapsed + 1))
    done
    echo
    if [ -n "$url" ]; then
      log "UI public URL: $url"
    else
      log "Tunnel URL not detected yet; check $RUNTIME_DIR/cloudflared.log"
    fi
  else
    log "cloudflared unavailable; UI is local only at http://127.0.0.1:$port"
  fi
  log "UI running. Press Ctrl+C to stop."
  wait "$ui_pid"
}

choose_mode() {
  # Default = generate files. Never block grading: non-tty or timeout -> files.
  if [ ! -t 0 ]; then
    log "non-interactive stdin; generating grading files."
    return 0
  fi
  echo
  echo "  [Enter] generate grading output files (Task 2 & 3)   <-- default"
  echo "  u       launch interactive Chainlit UI (demo)"
  local choice=""
  read -t 30 -r -p "Choice [Enter/u] (auto in 30s): " choice || choice=""
  echo
  case "$choice" in
    u|U|ui|UI) return 1 ;;
    *) return 0 ;;
  esac
}

# --- main -------------------------------------------------------------------
preflight
clone_or_update_repo
select_python
setup_deps
select_python
export PYTHONPATH="$REPO_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
SUTRA_CMD=("${PYTHON_CMD[@]}" -m sutra.cli)

ensure_model || fail "model unavailable."
start_server || fail "llama-server failed to start."

if choose_mode; then
  generate_outputs
  exit $?
else
  launch_ui
  exit $?
fi
