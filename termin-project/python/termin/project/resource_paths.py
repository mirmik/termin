"""Canonical policy for project-relative resource path settings."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import PurePosixPath


def normalize_project_resource_paths(
    value: object,
    *,
    field_name: str,
    warning: Callable[[str], None],
) -> list[str]:
    """Normalize project-owned resource paths without allowing root escapes.

    The returned values use portable POSIX separators. Invalid entries are
    deliberately ignored rather than interpreted differently by editor, build,
    and source-player consumers.
    """
    if not isinstance(value, list):
        warning(f"{field_name} must be a list, ignoring")
        return []

    normalized_paths: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        normalized = normalize_project_resource_path(
            item,
            field_name=f"{field_name}[{index}]",
            warning=warning,
        )
        if normalized is None or normalized in seen:
            continue
        normalized_paths.append(normalized)
        seen.add(normalized)
    return normalized_paths


def normalize_project_resource_path(
    value: object,
    *,
    field_name: str,
    warning: Callable[[str], None],
) -> str | None:
    """Return one portable project-relative path or log and reject it."""
    if type(value) is not str:
        warning(f"{field_name} must be a string, ignoring")
        return None

    normalized = value.strip().replace("\\", "/")
    relative_path = PurePosixPath(normalized)
    if (
        normalized == ""
        or relative_path.is_absolute()
        or normalized == "."
        or ".." in relative_path.parts
    ):
        warning(f"{field_name} must be a relative path without dot segments, ignoring")
        return None
    return relative_path.as_posix()
