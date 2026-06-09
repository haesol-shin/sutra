# CNU Campus Workspace

A Sutra workspace for the CNU Campus ChatBot use case.

The active checked-in index is a small dining proof of concept built from raw
CNU dining HTML. It is intentionally separate from the legacy 2414-document
`knowledge_seed.json` corpus, which is noisy and should not be treated as the
canonical Sutra workspace index.

Try it with the echo backend:

```powershell
uv run sutra ask --workspace examples/cnu-campus/sutra.toml --echo "수강신청은 언제 시작하나요?"
```
