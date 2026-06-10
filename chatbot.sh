#!/usr/bin/env bash
set -euo pipefail

WS_FLAG="--workspace examples/cnu-campus/sutra.toml"
if [ -n "${SUTRA_WORKSPACE:-}" ]; then
    WS_FLAG=""
fi

case "${1:-}" in
    batch)
        uv run sutra batch \
            --input /data/test_chat.json \
            --output /outputs/chat_output.json \
            $WS_FLAG
        ;;
    ui)
        uv run sutra ui $WS_FLAG
        ;;
    realtime)
        uv run sutra batch \
            --input /data/test_realtime.json \
            --output /outputs/realtime_output.json \
            --live \
            $WS_FLAG
        ;;
    all)
        uv run sutra batch --input /data/test_chat.json --output /outputs/chat_output.json $WS_FLAG
        uv run sutra batch --input /data/test_realtime.json --output /outputs/realtime_output.json --live $WS_FLAG
        ;;
    *)
        echo "Usage: $0 {batch|ui|realtime|all}"
        exit 1
        ;;
esac
