# CNU Campus Workspace

This is a minimal Sutra workspace example for the CNU Campus ChatBot use case.

It is intentionally outside `src/sutra` so Sutra stays a reusable local RAG runtime instead of a repository of built-in projects.

Try it with the echo backend:

```powershell
uv run sutra ask --workspace examples/cnu-campus/sutra.toml --echo "수강신청은 언제 시작하나요?"
```
