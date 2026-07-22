"""
Project settings — project-level configuration.

Stores render settings and other project-wide parameters.
Settings are saved to project_settings/project.json.

The C core (tc_project_settings) holds the actual runtime values.
This Python module handles persistence and synchronization.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from pathlib import PurePosixPath
from typing import Optional

from tcbase import log
from termin.project.application_identity import (
    ProjectApplicationIdentity,
    default_project_application_identity,
)
from termin.render import (
    PROJECT_RENDER_PHASE_CAPACITY,
    RenderSyncMode as CRenderSyncMode,
    configure_project_render_phases,
    set_render_sync_mode as c_set_render_sync_mode,
)
from termin.project.resource_paths import normalize_project_resource_paths

SERVICE_RESOURCE_IGNORE_PATHS: tuple[str, ...] = (".termin",)
DEFAULT_PLAYER_WINDOW_WIDTH = 1280
DEFAULT_PLAYER_WINDOW_HEIGHT = 720
DEFAULT_PLAYER_WINDOW_FULLSCREEN = True
DEFAULT_PLAYER_WINDOW_VSYNC = True
_BUILTIN_RENDER_PHASE_NAMES = frozenset({
    "opaque", "transparent", "normal", "depth", "id", "shadow", "ui",
    "editor", "editor_debug", "editor_debug_transparent",
})
_RENDER_PHASE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class RenderSyncMode(Enum):
    """Render synchronization mode between passes."""
    NONE = "none"
    FLUSH = "flush"
    FINISH = "finish"

    def to_c(self) -> CRenderSyncMode:
        """Convert to C enum."""
        if self == RenderSyncMode.NONE:
            return CRenderSyncMode.NONE
        elif self == RenderSyncMode.FLUSH:
            return CRenderSyncMode.FLUSH
        else:
            return CRenderSyncMode.FINISH

    @staticmethod
    def from_c(c_mode: CRenderSyncMode) -> "RenderSyncMode":
        """Convert from C enum."""
        if c_mode == CRenderSyncMode.NONE:
            return RenderSyncMode.NONE
        elif c_mode == CRenderSyncMode.FLUSH:
            return RenderSyncMode.FLUSH
        else:
            return RenderSyncMode.FINISH


@dataclass
class ProjectPlayerWindowSettings:
    """Default standalone player window settings for this project."""

    width: int = DEFAULT_PLAYER_WINDOW_WIDTH
    height: int = DEFAULT_PLAYER_WINDOW_HEIGHT
    fullscreen: bool = DEFAULT_PLAYER_WINDOW_FULLSCREEN
    vsync: bool = DEFAULT_PLAYER_WINDOW_VSYNC

    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "fullscreen": self.fullscreen,
            "vsync": self.vsync,
        }

    @staticmethod
    def from_dict(data: object) -> "ProjectPlayerWindowSettings":
        if data is None:
            return ProjectPlayerWindowSettings()
        if not isinstance(data, dict):
            log.warning("[ProjectSettings] player_window must be an object, using defaults")
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
            vsync=_bool_field(
                data.get("vsync"),
                default=DEFAULT_PLAYER_WINDOW_VSYNC,
                field_name="player_window.vsync",
            ),
        )

@dataclass
class ProjectSettings:
    """
    Project-level settings.

    Contains render settings and other global project parameters.
    """

    render_sync_mode: RenderSyncMode = RenderSyncMode.NONE
    # Project-relative directory used by the build command. The editor
    # treats this directory as generated output and excludes it from asset
    # discovery and live file watching.
    build_output_dir: str = "dist"
    # Project-relative files/directories excluded from resource discovery,
    # live file watching, and project build manifests.
    ignored_resource_paths: list[str] = field(default_factory=list)
    # Indexed project render-phase registry. Slot N maps to runtime bit 16+N.
    render_phase_names: list[str] = field(
        default_factory=lambda: [""] * PROJECT_RENDER_PHASE_CAPACITY
    )
    player_window: ProjectPlayerWindowSettings = field(default_factory=ProjectPlayerWindowSettings)
    application: ProjectApplicationIdentity = field(
        default_factory=lambda: default_project_application_identity("Termin Project")
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "render_sync_mode": self.render_sync_mode.value,
            "build_output_dir": self.build_output_dir,
            "ignored_resource_paths": list(self.ignored_resource_paths),
            "render_phase_names": list(self.render_phase_names),
            "player_window": self.player_window.to_dict(),
            "application": self.application.to_dict(),
        }

    @staticmethod
    def from_dict(data: dict, *, project_name: str = "Termin Project") -> "ProjectSettings":
        """Deserialize from dictionary."""
        sync_mode_str = data.get("render_sync_mode", "none")
        try:
            sync_mode = RenderSyncMode(sync_mode_str)
        except ValueError:
            log.warning(f"[ProjectSettings] Unknown render_sync_mode '{sync_mode_str}', falling back to NONE")
            sync_mode = RenderSyncMode.NONE

        build_output_dir = _normalize_project_relative_dir(
            data.get("build_output_dir", "dist"),
            fallback="dist",
            field_name="build_output_dir",
        )
        ignored_resource_paths = _normalize_project_relative_paths(
            data.get("ignored_resource_paths", []),
            field_name="ignored_resource_paths",
        )
        render_phase_names = _normalize_render_phase_names(data.get("render_phase_names"))
        player_window = ProjectPlayerWindowSettings.from_dict(data.get("player_window"))
        application = ProjectApplicationIdentity.from_dict(
            data.get("application"),
            project_name=project_name,
        )

        return ProjectSettings(
            render_sync_mode=sync_mode,
            build_output_dir=build_output_dir,
            ignored_resource_paths=ignored_resource_paths,
            render_phase_names=render_phase_names,
            player_window=player_window,
            application=application,
        )

    @staticmethod
    def for_project(project_name: str) -> "ProjectSettings":
        return ProjectSettings(application=default_project_application_identity(project_name))


class ProjectSettingsManager:
    """
    Singleton manager for project settings.

    Handles loading/saving settings from project directory.
    """

    _instance: Optional["ProjectSettingsManager"] = None
    _settings: ProjectSettings
    _project_path: Optional[Path] = None

    def __init__(self) -> None:
        self._settings = ProjectSettings()

    @classmethod
    def instance(cls) -> "ProjectSettingsManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = ProjectSettingsManager()
        return cls._instance

    @property
    def settings(self) -> ProjectSettings:
        """Get current project settings."""
        return self._settings

    @property
    def project_path(self) -> Optional[Path]:
        """Get current project path."""
        return self._project_path

    def set_project_path(self, path: Path) -> None:
        """Set project path and load settings."""
        self._project_path = path
        self._load()

    def _get_settings_path(self) -> Optional[Path]:
        """Get path to settings file."""
        if self._project_path is None:
            return None
        settings_dir = self._project_path / "project_settings"
        return settings_dir / "project.json"

    def _load(self) -> None:
        """Load settings from file and sync to C."""
        path = self._get_settings_path()
        project_name = _read_project_name(self._project_path)
        if path is None or not path.exists():
            self._settings = ProjectSettings.for_project(project_name)
            self._sync_to_c()
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("project settings root must be an object")
            self._settings = ProjectSettings.from_dict(data, project_name=project_name)
            self._sync_to_c()
        except Exception as e:
            log.error(f"[ProjectSettings] Failed to load settings: {e}")
            self._settings = ProjectSettings.for_project(project_name)
            self._sync_to_c()

    def _sync_to_c(self) -> None:
        """Sync Python settings to C global state."""
        c_set_render_sync_mode(self._settings.render_sync_mode.to_c())
        configure_project_render_phases(self._settings.render_phase_names)

    def save(self) -> bool:
        """Save settings to file."""
        path = self._get_settings_path()
        if path is None:
            log.error("[ProjectSettings] No project path set, cannot save")
            return False

        try:
            # Create directory if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._settings.to_dict(), f, indent=2)
            return True
        except Exception as e:
            log.error(f"[ProjectSettings] Failed to save settings: {e}")
            return False

    def set_render_sync_mode(self, mode: RenderSyncMode) -> None:
        """Set render sync mode, sync to C, and save."""
        self._settings.render_sync_mode = mode
        c_set_render_sync_mode(mode.to_c())
        self.save()

    def set_build_output_dir(self, value: str) -> None:
        """Set project-relative build output directory and save."""
        self._settings.build_output_dir = _normalize_project_relative_dir(
            value,
            fallback="dist",
            field_name="build_output_dir",
        )
        self.save()

    def set_ignored_resource_paths(self, values: list[str]) -> None:
        """Set project-relative resource scanner ignore paths and save."""
        self._settings.ignored_resource_paths = _normalize_project_relative_paths(
            values,
            field_name="ignored_resource_paths",
        )
        self.save()

    def set_render_phase_names(self, values: list[str]) -> None:
        """Replace the indexed project render-phase registry and save it."""
        normalized = _normalize_render_phase_names(values)
        configure_project_render_phases(normalized)
        self._settings.render_phase_names = normalized
        self.save()

    def set_player_window(
        self,
        width: int,
        height: int,
        fullscreen: bool,
        vsync: bool,
    ) -> None:
        """Set standalone player window defaults and save."""
        self._settings.player_window = ProjectPlayerWindowSettings(
            width=_positive_int_field(
                width,
                default=DEFAULT_PLAYER_WINDOW_WIDTH,
                field_name="player_window.width",
            ),
            height=_positive_int_field(
                height,
                default=DEFAULT_PLAYER_WINDOW_HEIGHT,
                field_name="player_window.height",
            ),
            fullscreen=_bool_field(
                fullscreen,
                default=DEFAULT_PLAYER_WINDOW_FULLSCREEN,
                field_name="player_window.fullscreen",
            ),
            vsync=_bool_field(
                vsync,
                default=DEFAULT_PLAYER_WINDOW_VSYNC,
                field_name="player_window.vsync",
            ),
        )
        self.save()

    def set_application_identity(
        self,
        application_id: str,
        label: str,
        version_code: int,
        version_name: str,
    ) -> None:
        """Validate, set, and save product application identity."""
        self._settings.application = ProjectApplicationIdentity.from_dict(
            {
                "id": application_id,
                "label": label,
                "version_code": version_code,
                "version_name": version_name,
            },
            project_name=_read_project_name(self._project_path),
        )
        self.save()

    def _get_editor_state_path(self) -> Optional[Path]:
        """Get path to .editor_state.json (per-user, not committed)."""
        if self._project_path is None:
            return None
        return self._project_path / "project_settings" / ".editor_state.json"

    def get_last_scene(self) -> str | None:
        """Get the last opened scene path for this project."""
        path = self._get_editor_state_path()
        if path is None or not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("last_scene")
        except Exception as e:
            log.error(f"[ProjectSettings] Failed to read editor state: {e}")
            return None

    def set_last_scene(self, scene_path: str | None) -> None:
        """Set the last opened scene path (stored in .editor_state.json)."""
        path = self._get_editor_state_path()
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data: dict = {}
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["last_scene"] = scene_path
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.error(f"[ProjectSettings] Failed to save editor state: {e}")


def _normalize_project_relative_dir(value: object, *, fallback: str, field_name: str) -> str:
    if type(value) is not str:
        log.warning(f"[ProjectSettings] {field_name} must be a string, falling back to '{fallback}'")
        return fallback

    normalized = value.strip().replace("\\", "/")
    rel_path = PurePosixPath(normalized)
    if (
        normalized == ""
        or rel_path.is_absolute()
        or normalized == "."
        or ".." in rel_path.parts
    ):
        log.warning(f"[ProjectSettings] Invalid {field_name} '{value}', falling back to '{fallback}'")
        return fallback

    return rel_path.as_posix()


def _normalize_render_phase_names(value: object) -> list[str]:
    if value is None:
        return [""] * PROJECT_RENDER_PHASE_CAPACITY
    if not isinstance(value, list) or len(value) != PROJECT_RENDER_PHASE_CAPACITY:
        raise ValueError(
            "render_phase_names must be a list with exactly "
            f"{PROJECT_RENDER_PHASE_CAPACITY} entries"
        )

    result: list[str] = []
    used: set[str] = set()
    for index, raw_name in enumerate(value):
        if not isinstance(raw_name, str):
            raise ValueError(f"render_phase_names[{index}] must be a string")
        name = raw_name.strip()
        if not name:
            result.append("")
            continue
        if name in _BUILTIN_RENDER_PHASE_NAMES:
            raise ValueError(
                f"render_phase_names[{index}] duplicates built-in phase '{name}'"
            )
        if not _RENDER_PHASE_NAME_PATTERN.fullmatch(name):
            raise ValueError(f"render_phase_names[{index}] has invalid name '{name}'")
        if name in used:
            raise ValueError(f"render phase '{name}' is assigned more than once")
        used.add(name)
        result.append(name)
    return result


def _normalize_project_relative_paths(value: object, *, field_name: str) -> list[str]:
    return normalize_project_resource_paths(
        value,
        field_name=field_name,
        warning=lambda message: log.warning(f"[ProjectSettings] {message}"),
    )


def _positive_int_field(value: object, *, default: int, field_name: str) -> int:
    if value is None:
        return default
    if type(value) is not int or value <= 0:
        log.warning(f"[ProjectSettings] {field_name} must be a positive integer, using {default}")
        return default
    return value


def _bool_field(value: object, *, default: bool, field_name: str) -> bool:
    if value is None:
        return default
    if type(value) is not bool:
        log.warning(f"[ProjectSettings] {field_name} must be a boolean, using {default}")
        return default
    return value


def load_project_settings(project_root: str | Path) -> ProjectSettings:
    """Strictly load canonical settings for build and tooling consumers."""
    root = Path(project_root).resolve()
    project_name = _read_project_name(root)
    path = root / "project_settings" / "project.json"
    if not path.exists():
        return ProjectSettings.for_project(project_name)
    with path.open("r", encoding="utf-8") as settings_file:
        data = json.load(settings_file)
    if not isinstance(data, dict):
        raise ValueError(f"Project settings root must be an object: {path}")
    return ProjectSettings.from_dict(data, project_name=project_name)


def _read_project_name(project_root: Path | None) -> str:
    if project_root is None:
        return "Termin Project"
    project_files = sorted(project_root.glob("*.terminproj"))
    if not project_files:
        return project_root.name or "Termin Project"
    project_file = project_files[0]
    try:
        data = json.loads(project_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return project_file.stem
    if isinstance(data, dict):
        name = data.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return project_file.stem
