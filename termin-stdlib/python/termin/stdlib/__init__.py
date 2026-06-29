"""Termin standard library resources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


@dataclass(frozen=True)
class StdlibSyncResult:
    source_root: Path
    target_root: Path
    copied: int = 0
    removed: int = 0


def stdlib_root() -> Path:
    """Return the installed Termin standard library resource root."""
    return Path(__file__).resolve().parent / "resources"


def iter_stdlib_files() -> list[Path]:
    """Return all files owned by the Termin standard library."""
    root = stdlib_root()
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def sync_stdlib(
    project_root: str | Path,
    *,
    clean: bool = False,
    dry_run: bool = False,
) -> StdlibSyncResult:
    """Copy Termin stdlib resources into ``project_root / "stdlib"``.

    ``clean`` removes files from the target stdlib that no longer exist in the
    packaged stdlib. ``dry_run`` reports the changes without mutating files.
    """
    source_root = stdlib_root()
    if not source_root.is_dir():
        raise FileNotFoundError(f"Termin stdlib resource root was not found: {source_root}")

    target_root = Path(project_root) / "stdlib"
    copied = _copy_stdlib_files(source_root, target_root, dry_run=dry_run)
    removed = _remove_stale_stdlib_files(source_root, target_root, dry_run=dry_run) if clean else 0
    return StdlibSyncResult(
        source_root=source_root,
        target_root=target_root,
        copied=copied,
        removed=removed,
    )


def _copy_stdlib_files(source_root: Path, target_root: Path, *, dry_run: bool) -> int:
    copied = 0
    for source_path in sorted(path for path in source_root.rglob("*") if path.is_file()):
        relative_path = source_path.relative_to(source_root)
        target_path = target_root / relative_path
        if _same_file_content(source_path, target_path):
            continue
        copied += 1
        if dry_run:
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
    return copied


def _remove_stale_stdlib_files(source_root: Path, target_root: Path, *, dry_run: bool) -> int:
    if not target_root.exists():
        return 0

    removed = 0
    for target_path in sorted((path for path in target_root.rglob("*") if path.is_file()), reverse=True):
        relative_path = target_path.relative_to(target_root)
        if (source_root / relative_path).exists():
            continue
        removed += 1
        if not dry_run:
            target_path.unlink()

    if not dry_run:
        _remove_empty_directories(target_root)
    return removed


def _remove_empty_directories(root: Path) -> None:
    for path in sorted((path for path in root.rglob("*") if path.is_dir()), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass


def _same_file_content(left: Path, right: Path) -> bool:
    if not right.exists():
        return False
    if left.stat().st_size != right.stat().st_size:
        return False
    return left.read_bytes() == right.read_bytes()


__all__ = [
    "StdlibSyncResult",
    "iter_stdlib_files",
    "stdlib_root",
    "sync_stdlib",
]
