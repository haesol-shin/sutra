#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
    batch)
        uv run sutra batch \
            --input /data/test_chat.json \
            --output /outputs/chat_output.json \
            --workspace examples/cnu-campus/sutra.toml
        ;;
    ui)
        uv run sutra ui --workspace examples/cnu-campus/sutra.toml
        ;;
    realtime)
        uv run sutra batch \
            --input /data/test_realtime.json \
            --output /outputs/realtime_output.json \
            --live \
            --workspace examples/cnu-campus/sutra.toml
        ;;
    all)
        uv run sutra batch --input /data/test_chat.json --output /outputs/chat_output.json --workspace examples/cnu-campus/sutra.toml
        uv run sutra batch --input /data/test_realtime.json --output /outputs/realtime_output.json --live --workspace examples/cnu-campus/sutra.toml
        ;;
    *)
        echo "Usage: $0 {batch|ui|realtime|all}"
        exit 1
        ;;
esac
