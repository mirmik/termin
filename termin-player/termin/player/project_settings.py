"""Lightweight project settings reader for player runtimes.

The editor owns the full project settings model. Player needs only the
persisted runtime subset and imports the lightweight shared resource-path
policy rather than editor/app settings code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from termin.project.resource_paths import normalize_project_resource_paths


SERVICE_RESOURCE_IGNORE_PATHS: tuple[str, ...] = (".termin",)
DEFAULT_PLAYER_WINDOW_WIDTH = 1280
DEFAULT_PLAYER_WINDOW_HEIGHT = 720
DEFAULT_PLAYER_WINDOW_FULLSCREEN = True
PROJECT_RENDER_PHASE_CAPACITY = 48


@dataclass(frozen=True)
class ProjectPlayerWindowSettings:
    width: int = DEFAULT_PLAYER_WINDOW_WIDTH
    height: int = DEFAULT_PLAYER_WINDOW_HEIGHT
    fullscreen: bool = DEFAULT_PLAYER_WINDOW_FULLSCREEN

    @staticmethod
    def from_dict(data: object) -> "ProjectPlayerWindowSettings":
        if data is None:
            return ProjectPlayerWindowSettings()
        if not isinstance(data, dict):
            _log_warning("[PlayerProjectSettings] player_window must be an object, using defaults")
            return ProjectPlayerWindowSettings()
        return ProjectPlayerWindowSettings(
            width=_positive_int_field(
                data.get("width"),
                default=DEFAULT_PLAYER_WINDOW_WIDTH,
                field_name="player_window.width",
            ),
            height=_positive_int_field(
                data.get("height"),
                default=DEFAULT_PLAYER_WINDOW_HEIGHT,
                field_name="player_window.height",
            ),
            fullscreen=_bool_field(
                data.get("fullscreen"),
                default=DEFAULT_PLAYER_WINDOW_FULLSCREEN,
                field_name="player_window.fullscreen",
            ),
        )


@dataclass(frozen=True)
class ProjectRuntimeSettings:
    build_output_dir: str = "dist"
    ignored_resource_paths: tuple[str, ...] = field(default_factory=tuple)
    render_phase_names: tuple[str, ...] = field(
        default_factory=lambda: ("",) * PROJECT_RENDER_PHASE_CAPACITY
    )
    player_window: ProjectPlayerWindowSettings = field(default_factory=ProjectPlayerWindowSettings)

    @staticmethod
    def from_dict(data: dict[str, object]) -> "ProjectRuntimeSettings":
        return ProjectRuntimeSettings(
            build_output_dir=_project_relative_path(
                data.get("build_output_dir"),
                fallback="dist",
                field_name="build_output_dir",
            ),
            ignored_resource_paths=tuple(
                normalize_project_resource_paths(
                    data.get("ignored_resource_paths"),
                    field_name="ignored_resource_paths",
                    warning=lambda message: _log_warning(f"[PlayerProjectSettings] {message}"),
                )
            ),
            render_phase_names=_render_phase_names(data.get("render_phase_names")),
            player_window=ProjectPlayerWindowSettings.from_dict(data.get("player_window")),
        )


def load_project_runtime_settings(project_path: str | Path) -> ProjectRuntimeSettings:
    settings_path = Path(project_path) / "project_settings" / "project.json"
    if not settings_path.exists():
        return ProjectRuntimeSettings()

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception as exc:
        _log_error(f"[PlayerProjectSettings] Failed to read project settings: {exc}")
        return ProjectRuntimeSettings()

    if not isinstance(data, dict):
        _log_error("[PlayerProjectSettings] Project settings root must be an object")
        return ProjectRuntimeSettings()

    return ProjectRuntimeSettings.from_dict(data)


def _render_phase_names(value: object) -> tuple[str, ...]:
    if value is None:
        return ("",) * PROJECT_RENDER_PHASE_CAPACITY
    if not isinstance(value, list) or len(value) != PROJECT_RENDER_PHASE_CAPACITY:
        raise ValueError(
            "render_phase_names must contain exactly "
            f"{PROJECT_RENDER_PHASE_CAPACITY} indexed entries"
        )
    if any(not isinstance(name, str) for name in value):
        raise ValueError("render_phase_names entries must be strings")
    return tuple(name.strip() for name in value)


def _positive_int_field(value: object, *, default: int, field_name: str) -> int:
    if isinstance(value, bool):
        _log_warning(f"[PlayerProjectSettings] {field_name} must be a positive integer, using {default}")
        return default
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        _log_warning(f"[PlayerProjectSettings] {field_name} must be a positive integer, using {default}")
        return default
    if parsed <= 0:
        _log_warning(f"[PlayerProjectSettings] {field_name} must be a positive integer, using {default}")
        return default
    return parsed


def _bool_field(value: object, *, default: bool, field_name: str) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    _log_warning(f"[PlayerProjectSettings] {field_name} must be a boolean, using {default}")
    return default


def _project_relative_path(value: object, *, fallback: str, field_name: str) -> str:
    """Normalize the single build-output directory setting."""
    if not isinstance(value, str):
        if value is not None:
            _log_warning(f"[PlayerProjectSettings] {field_name} must be a relative path, using {fallback!r}")
        return fallback

    normalized = value.strip().replace("\\", "/")
    path = Path(normalized)
    if normalized in ("", ".", "..") or path.is_absolute() or ".." in path.parts:
        _log_warning(f"[PlayerProjectSettings] {field_name} must stay inside project, using {fallback!r}")
        return fallback
    return normalized


def _log_warning(message: str) -> None:
    from tcbase import log

    log.warning(message)


def _log_error(message: str) -> None:
    from tcbase import log

    log.error(message)
