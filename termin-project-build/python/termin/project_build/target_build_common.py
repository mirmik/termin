"""Shared helpers for platform-specific project build wrappers."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def resolve_termin_root(
    termin_root: str | Path | None,
    *,
    marker_script_name: str,
    target_name: str,
) -> Path:
    if termin_root is not None:
        root = Path(termin_root).resolve()
        if (root / marker_script_name).exists():
            return root
        raise FileNotFoundError(f"Termin root has no {marker_script_name}: {root}")

    candidates = _termin_root_candidates()
    for candidate in candidates:
        if (candidate / marker_script_name).exists():
            return candidate

    checked = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        f"Termin root has no {marker_script_name}. "
        f"Set TERMIN_ROOT or pass termin_root explicitly for {target_name}. "
        f"Checked: {checked}"
    )


def resolve_gradle(gradle: str | Path | None) -> Path | None:
    if gradle is not None:
        return Path(gradle).expanduser().resolve()

    env_gradle = os.environ.get("GRADLE_BIN")
    if env_gradle:
        return Path(env_gradle).expanduser().resolve()

    path_gradle = shutil.which("gradle")
    return Path(path_gradle).resolve() if path_gradle else None


def read_log_tail(log_path: Path, max_lines: int = 40) -> str:
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:
        return f"Failed to read build log tail: {exc}"
    tail = lines[-max_lines:]
    if not tail:
        return "Build log is empty."
    return "\n".join(tail)


def _termin_root_candidates() -> list[Path]:
    candidates: list[Path] = []

    env_root = os.environ.get("TERMIN_ROOT")
    if env_root:
        candidates.append(Path(env_root).resolve())

    cwd = Path.cwd().resolve()
    candidates.extend([cwd, *cwd.parents])

    package_path = Path(__file__).resolve()
    candidates.extend(package_path.parents)

    unique_candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique_candidates.append(candidate)
    return unique_candidates
