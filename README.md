# NLP Term Project

Campus ChatBot term project workspace.

## Environment

Use `uv` and Python 3.10.12.

```powershell
uv python install 3.10.12
uv sync --extra xpu
```

This installs the local XPU development PyTorch build through the PyTorch XPU index:

```text
torch 2.9.1+xpu
pytorch-triton-xpu 3.5.0
```

Verification:

```powershell
uv run python --version
uv run python -c "import torch; print(torch.__version__); print(torch.xpu.is_available())"
```

Current local note:

- The assignment document lists `torch 2.5.1`.
- `torch 2.5.1+xpu` installed but failed to import locally because of a missing `c10_xpu.dll` dependency.
- `torch 2.9.1+xpu` works on this machine in the reference project `../aidm-term-proj`, so this repo uses it as the local development default.
- Revisit the torch version before final submission if strict version matching becomes a grading concern.

## Useful Commands

```powershell
uv sync --extra xpu
```

Generate a submission-oriented package list near the end of the project:

```powershell
uv run python -m pip freeze > requirements.txt
```
