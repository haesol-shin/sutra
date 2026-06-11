from __future__ import annotations

from pathlib import Path


def test_chatbot_sh_uses_8192_default_context_window() -> None:
    script = (Path(__file__).parents[2] / "chatbot.sh").read_text(encoding="utf-8")

    assert '--n-ctx "${SUTRA_N_CTX:-8192}"' in script
