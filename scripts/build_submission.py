from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path
from typing import NamedTuple


PACKAGE_NAME = "Termproject_신해솔"

# The submission zip is a minimal bootstrap. All source code (sutra + nlp_term),
# the CNU workspace corpus, and the prompts are cloned fresh from GitHub by
# chatbot.sh at run time, so they stay editable after submission. Only the two
# entrypoints, the grading inputs, and the frozen Task 1 classifier are shipped.
SUBMISSION_FILES = (
    Path("chatbot.sh"),
    Path("src") / "classifier.ipynb",
    Path("data") / "test_cls.json",
    Path("data") / "test_chat.json",
    Path("data") / "test_realtime.json",
    Path("model") / "classifier.joblib",
)


class BuildResult(NamedTuple):
    package_dir: Path
    zip_path: Path
    file_count: int
    total_bytes: int


def _copy_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"required submission file is missing: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _make_executable(path: Path) -> None:
    try:
        path.chmod(path.stat().st_mode | 0o755)
    except OSError:
        pass


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def _create_zip(package_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in _iter_files(package_dir):
            archive.write(path, path.relative_to(package_dir.parent))


def _print_summary(result: BuildResult) -> None:
    zip_mb = result.zip_path.stat().st_size / (1024 * 1024)
    total_mb = result.total_bytes / (1024 * 1024)
    print(f"Package directory: {result.package_dir}")
    print(f"Zip path: {result.zip_path}")
    print(f"Included files: {result.file_count}")
    print(f"Package size: {total_mb:.2f} MB")
    print(f"Zip size: {zip_mb:.2f} MB")


def build_submission(
    repo_root: Path | None = None,
    dist_root: Path | None = None,
) -> BuildResult:
    repo_root = (repo_root or Path(__file__).resolve().parents[1]).resolve()
    dist_root = (dist_root or repo_root / "dist").resolve()
    package_dir = dist_root / PACKAGE_NAME
    zip_path = dist_root / f"{PACKAGE_NAME}.zip"

    if package_dir.exists():
        shutil.rmtree(package_dir)
    if zip_path.exists():
        zip_path.unlink()
    dist_root.mkdir(parents=True, exist_ok=True)

    for relative_path in SUBMISSION_FILES:
        _copy_file(repo_root / relative_path, package_dir / relative_path)
    _make_executable(package_dir / "chatbot.sh")

    file_paths = list(_iter_files(package_dir))
    total_bytes = sum(path.stat().st_size for path in file_paths)
    _create_zip(package_dir, zip_path)

    result = BuildResult(
        package_dir=package_dir,
        zip_path=zip_path,
        file_count=len(file_paths),
        total_bytes=total_bytes,
    )
    _print_summary(result)
    return result


def main() -> int:
    try:
        build_submission()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
