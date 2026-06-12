from __future__ import annotations

from pathlib import Path

import pytest

from sutra import Document, load_config
from sutra.documents import load_documents
from sutra.errors import ConfigError


def test_load_config_resolves_workspace_relative_paths(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "data" / "index.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "prompts" / "system.md").write_text("system", encoding="utf-8")
    config_path = tmp_path / "sutra.toml"
    config_path.write_text(
        """
[workspace]
name = "fixture"

[runtime]
base_url = "http://127.0.0.1:18080"
model = "qwen"

[rag]
index_path = "data/index.jsonl"
top_k = 4

[prompts]
system = "prompts/system.md"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.workspace.name == "fixture"
    assert config.rag.index_path == (tmp_path / "data" / "index.jsonl").resolve()
    assert config.prompts.system == (tmp_path / "prompts" / "system.md").resolve()
    assert config.rag.top_k == 4


def test_load_config_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="workspace config not found"):
        load_config(tmp_path / "missing.toml")


@pytest.mark.parametrize("path", [None, ""])
def test_load_config_rejects_missing_path(path: object) -> None:
    with pytest.raises(ConfigError, match="workspace config path is required"):
        load_config(path)  # type: ignore[arg-type]


def test_load_config_resolves_explicit_model_path(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "model" / "generator").mkdir(parents=True)
    (tmp_path / "data" / "index.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "prompts" / "system.md").write_text("system", encoding="utf-8")
    model_file = tmp_path / "model" / "generator" / "Qwen3.5-9B-Q4_K_M.gguf"
    model_file.write_text("dummy model content", encoding="utf-8")
    config_path = tmp_path / "sutra.toml"
    config_path.write_text(
        """
[workspace]
name = "fixture"

[runtime]
model_path = "model/generator/Qwen3.5-9B-Q4_K_M.gguf"

[rag]
index_path = "data/index.jsonl"

[prompts]
system = "prompts/system.md"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.runtime.model_path == model_file.resolve()


def test_load_config_defaults_model_path_when_omitted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    (tmp_path / "data").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "data" / "index.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "prompts" / "system.md").write_text("system", encoding="utf-8")
    config_path = tmp_path / "sutra.toml"
    config_path.write_text(
        """
[workspace]
name = "fixture"

[runtime]
base_url = "http://127.0.0.1:18080"

[rag]
index_path = "data/index.jsonl"

[prompts]
system = "prompts/system.md"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.runtime.model_path == (
        tmp_path / ".cache" / "sutra" / "models" / "Qwen3.5-9B-Q4_K_M.gguf"
    ).resolve()


def test_sutra_model_path_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    (tmp_path / "data").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "data" / "index.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "prompts" / "system.md").write_text("system", encoding="utf-8")
    config_path = tmp_path / "sutra.toml"
    config_path.write_text(
        """
[workspace]
name = "fixture"

[rag]
index_path = "data/index.jsonl"

[prompts]
system = "prompts/system.md"
""".strip(),
        encoding="utf-8",
    )

    model_path_override = tmp_path / "overrides" / "my-model.gguf"
    monkeypatch.setenv("SUTRA_MODEL_PATH", str(model_path_override))

    config = load_config(config_path)

    assert config.runtime.model_path == model_path_override.resolve()


def test_sutra_model_path_env_overrides_configured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    (tmp_path / "data").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "model" / "generator").mkdir(parents=True)
    (tmp_path / "data" / "index.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "prompts" / "system.md").write_text("system", encoding="utf-8")
    config_path = tmp_path / "sutra.toml"
    config_path.write_text(
        """
[workspace]
name = "fixture"

[runtime]
model_path = "model/generator/Qwen3.5-9B-Q4_K_M.gguf"

[rag]
index_path = "data/index.jsonl"

[prompts]
system = "prompts/system.md"
""".strip(),
        encoding="utf-8",
    )

    model_path_override = tmp_path / "overrides" / "override.gguf"
    monkeypatch.setenv("SUTRA_MODEL_PATH", str(model_path_override))

    config = load_config(config_path)

    assert config.runtime.model_path == model_path_override.resolve()


def test_sutra_model_dir_env_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    (tmp_path / "data").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "data" / "index.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "prompts" / "system.md").write_text("system", encoding="utf-8")
    config_path = tmp_path / "sutra.toml"
    config_path.write_text(
        """
[workspace]
name = "fixture"

[rag]
index_path = "data/index.jsonl"

[prompts]
system = "prompts/system.md"
""".strip(),
        encoding="utf-8",
    )

    model_dir = tmp_path / "my-models"
    monkeypatch.setenv("SUTRA_MODEL_DIR", str(model_dir))

    config = load_config(config_path)

    assert config.runtime.model_path == (model_dir / "Qwen3.5-9B-Q4_K_M.gguf").resolve()


def test_sutra_model_dir_not_used_when_config_model_path_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    (tmp_path / "data").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "data" / "index.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "prompts" / "system.md").write_text("system", encoding="utf-8")
    config_path = tmp_path / "sutra.toml"
    config_path.write_text(
        """
[workspace]
name = "fixture"

[runtime]
model_path = "../other-model.gguf"

[rag]
index_path = "data/index.jsonl"

[prompts]
system = "prompts/system.md"
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("SUTRA_MODEL_DIR", str(tmp_path / "ignored-models"))

    config = load_config(config_path)

    assert config.runtime.model_path == (tmp_path.parent / "other-model.gguf").resolve()


def test_absolute_model_path_preserved(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    (tmp_path / "data").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "data" / "index.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "prompts" / "system.md").write_text("system", encoding="utf-8")
    config_path = tmp_path / "sutra.toml"
    config_path.write_text(
        """
[workspace]
name = "fixture"

[runtime]
model_path = "/absolute/path/to/model.gguf"

[rag]
index_path = "data/index.jsonl"

[prompts]
system = "prompts/system.md"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.runtime.model_path == Path("/absolute/path/to/model.gguf").resolve()


def test_load_config_rejects_unsupported_backend(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "data" / "index.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "prompts" / "system.md").write_text("system", encoding="utf-8")
    config_path = tmp_path / "sutra.toml"
    config_path.write_text(
        """
[workspace]
name = "fixture"

[runtime]
backend = "openai"

[rag]
index_path = "data/index.jsonl"

[prompts]
system = "prompts/system.md"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="invalid workspace config"):
        load_config(config_path)


def test_load_config_rejects_invalid_numeric_limits(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "data" / "index.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "prompts" / "system.md").write_text("system", encoding="utf-8")
    config_path = tmp_path / "sutra.toml"
    config_path.write_text(
        """
[workspace]
name = "fixture"

[runtime]
max_tokens = 0

[rag]
index_path = "data/index.jsonl"
top_k = 0

[prompts]
system = "prompts/system.md"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="invalid workspace config"):
        load_config(config_path)


def test_load_documents_reads_jsonl_documents(tmp_path: Path) -> None:
    path = tmp_path / "index.jsonl"
    path.write_text(
        '{"id":"doc-1","title":"Title","text":"Body","source_name":"fixture","metadata":{"label":"notice"}}\n',
        encoding="utf-8",
    )

    docs = load_documents(path)

    assert docs == [
        Document(
            id="doc-1",
            title="Title",
            text="Body",
            source_name="fixture",
            metadata={"label": "notice"},
        )
    ]


def test_load_documents_reports_bad_jsonl_line(tmp_path: Path) -> None:
    path = tmp_path / "index.jsonl"
    path.write_text('{"id": "doc-1"}\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="invalid document"):
        load_documents(path)
