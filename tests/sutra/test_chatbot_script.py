from __future__ import annotations

from pathlib import Path


def test_chatbot_sh_uses_8192_default_context_window() -> None:
    script = (Path(__file__).parents[2] / "chatbot.sh").read_text(encoding="utf-8")

    # The context window defaults to 8192, overridable via SUTRA_N_CTX, and is
    # passed to the llama server via --n-ctx.
    assert "${SUTRA_N_CTX:-8192}" in script
    assert '--n-ctx "$N_CTX"' in script
