"""Shared project resource ignore policy."""

from __future__ import annotations

from pathlib import Path

from termin.project.settings import (
    ProjectSettings,
    ProjectSettingsManager,
    SERVICE_RESOURCE_IGNORE_PATHS,
)


def project_ignored_roots(
    project_root: str | Path,
    settings: ProjectSettings | None = None,
) -> tuple[Path, ...]:
    """Return absolute roots excluded from project resource discovery."""
    root = Path(project_root).resolve()
    active_settings = settings
    if active_settings is None:
        active_settings = ProjectSettingsManager.instance().settings

    service_roots = tuple(root / ignored_path for ignored_path in SERVICE_RESOURCE_IGNORE_PATHS)
    build_output_root = root / active_settings.build_output_dir
    user_roots = tuple(root / ignored_path for ignored_path in active_settings.ignored_resource_paths)
    return tuple(path.resolve() for path in (*service_roots, build_output_root, *user_roots))


def is_path_ignored(path: str | Path, ignored_roots: tuple[Path, ...]) -> bool:
    """Return whether path is inside one of ignored_roots."""
    if not ignored_roots:
        return False

    resolved = Path(path).resolve()
    for ignored_root in ignored_roots:
        if resolved == ignored_root or ignored_root in resolved.parents:
            return True
    return False
