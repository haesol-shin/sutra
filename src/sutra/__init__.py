from __future__ import annotations

import os

# Keep JAX off the GPU. Several RAG dependencies (e.g. bm25s) import JAX
# transitively when it is available — as it is on Colab — and JAX preallocates
# ~75% of GPU VRAM (~11 GB on a T4) the instant it is imported. That starves the
# llama server and makes model loading fail with a spurious CUDA "out of memory"
# (intermittently, depending on whether a jax-holding sutra process is alive when
# the server loads). Sutra never uses JAX for GPU compute, so pin it to CPU. This
# must run before any submodule (and any transitive `import jax`) loads; spawned
# subprocesses such as the Chainlit UI inherit these env vars.
os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")

from sutra.config import Config, load_config  # noqa: E402
from sutra.models import Answer, Document, Evidence  # noqa: E402
from sutra.pdf import PdfExtraction, PdfPage, PdfTable, PdfWarning, extract_pdf  # noqa: E402
from sutra.service import ChatClient, ask, chat  # noqa: E402

__all__ = [
    "Answer",
    "ChatClient",
    "Config",
    "Document",
    "Evidence",
    "PdfExtraction",
    "PdfPage",
    "PdfTable",
    "PdfWarning",
    "ask",
    "chat",
    "extract_pdf",
    "load_config",
]
