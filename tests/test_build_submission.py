from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest


def _load_build_module(repo_root: Path):
    module_path = repo_root / "scripts" / "build_submission.py"
    spec = importlib.util.spec_from_file_location("build_submission", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXPECTED_FILES = {
    "chatbot.sh",
    "src/classifier.ipynb",
    "data/test_cls.json",
    "data/test_chat.json",
    "data/test_realtime.json",
    "model/classifier.joblib",
}


def _make_inputs(tmp_path: Path) -> Path:
    """A hermetic source tree holding exactly the bootstrap submission inputs."""
    repo = tmp_path / "src_repo"
    contents = {
        "chatbot.sh": "#!/usr/bin/env bash\necho hi\n",
        "src/classifier.ipynb": "{}\n",
        "data/test_cls.json": "[]\n",
        "data/test_chat.json": "[]\n",
        "data/test_realtime.json": "[]\n",
        "model/classifier.joblib": "BINARY-PLACEHOLDER",
    }
    for relative, text in contents.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return repo


def test_build_submission_ships_only_bootstrap_manifest(tmp_path):
    real_repo = Path(__file__).resolve().parents[1]
    module = _load_build_module(real_repo)
    source = _make_inputs(tmp_path)

    result = module.build_submission(repo_root=source, dist_root=tmp_path / "dist")

    package_dir = result.package_dir
    actual = {
        path.relative_to(package_dir).as_posix()
        for path in package_dir.rglob("*")
        if path.is_file()
    }
    assert actual == EXPECTED_FILES

    # No source code, corpus, or workspace must leak into the minimal zip.
    assert not (package_dir / "src" / "sutra").exists()
    assert not (package_dir / "src" / "nlp_term").exists()
    assert not (package_dir / "examples").exists()
    assert not (package_dir / "pyproject.toml").exists()
    assert not (package_dir / "requirements.txt").exists()
    assert not any("__pycache__" in path.parts for path in package_dir.rglob("*"))

    assert result.zip_path.is_file()
    with zipfile.ZipFile(result.zip_path) as archive:
        zipped = {
            name.split("/", 1)[1]
            for name in archive.namelist()
            if "/" in name and not name.endswith("/")
        }
    assert zipped == EXPECTED_FILES
    assert result.file_count == len(EXPECTED_FILES)
    assert result.total_bytes > 0


def test_build_submission_requires_classifier(tmp_path):
    real_repo = Path(__file__).resolve().parents[1]
    module = _load_build_module(real_repo)
    source = _make_inputs(tmp_path)
    (source / "model" / "classifier.joblib").unlink()

    with pytest.raises(FileNotFoundError):
        module.build_submission(repo_root=source, dist_root=tmp_path / "dist")
