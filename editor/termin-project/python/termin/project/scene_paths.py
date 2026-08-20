"""Canonical identities and display labels for project-owned scene files."""

from __future__ import annotations

from pathlib import Path, PurePosixPath


def project_scene_identity(project_root: str | Path, scene_path: str | Path) -> str:
    """Return the portable project-relative identity of one ``.scene`` file."""
    root = Path(project_root).resolve()
    candidate = Path(scene_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    if candidate.suffix != ".scene":
        raise ValueError(f"scene path must have a .scene suffix: {candidate}")
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"scene path is outside project root: scene={candidate} project={root}"
        ) from exc
    if relative == Path("."):
        raise ValueError(f"scene path does not name a file: {candidate}")
    return PurePosixPath(*relative.parts).as_posix()


def scene_display_label(identity: str) -> str:
    """Derive a concise UI label without turning it into a lookup key."""
    normalized = identity.strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    if normalized in {"", "."} or path.name == "":
        raise ValueError(f"invalid scene identity: {identity!r}")
    return path.stem
