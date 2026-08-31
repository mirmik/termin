"""Preparation of the repository-pinned host Slang compiler."""

from __future__ import annotations

from pathlib import Path
import subprocess


class SlangToolchainError(RuntimeError):
    """The pinned Slang host toolchain could not be prepared."""


def prepare_slang_toolchain(
    repo_root: Path,
    python_executable: Path,
    *,
    install_root: Path | None = None,
    post_extract_script: Path | None = None,
) -> Path:
    """Install or verify the pinned Slang compiler and return ``slangc``."""
    root = install_root or repo_root / "build" / "toolchains"
    command = [
        str(python_executable),
        str(repo_root / "scripts" / "install_slang_toolchain.py"),
        "--install-root",
        str(root),
        "--no-configure",
        "--print-path",
    ]
    if post_extract_script is not None:
        command.extend(["--post-extract-script", str(post_extract_script)])
    result = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise SlangToolchainError("failed to prepare the pinned Slang toolchain")

    path = Path(result.stdout.strip())
    if not path.is_file():
        raise SlangToolchainError(
            f"Slang installer returned a missing executable: {path}"
        )
    return path.resolve()
