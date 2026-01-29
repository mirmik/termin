"""
Project settings — project-level configuration.

Stores render settings and other project-wide parameters.
Settings are saved to project_settings/project.json.

The C core (tc_project_settings) holds the actual runtime values.
This Python module handles persistence and synchronization.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from termin._native import log
from termin.graphics._graphics_native import (
    RenderSyncMode as CRenderSyncMode,
    get_render_sync_mode as c_get_render_sync_mode,
    set_render_sync_mode as c_set_render_sync_mode,
)


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
class ProjectSettings:
    """
    Project-level settings.

    Contains render settings and other global project parameters.
    """

    render_sync_mode: RenderSyncMode = RenderSyncMode.NONE

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "render_sync_mode": self.render_sync_mode.value,
        }

    @staticmethod
    def from_dict(data: dict) -> "ProjectSettings":
        """Deserialize from dictionary."""
        sync_mode_str = data.get("render_sync_mode", "none")
        try:
            sync_mode = RenderSyncMode(sync_mode_str)
        except ValueError:
            sync_mode = RenderSyncMode.NONE

        return ProjectSettings(
            render_sync_mode=sync_mode,
        )


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
        if path is None or not path.exists():
            self._settings = ProjectSettings()
            self._sync_to_c()
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._settings = ProjectSettings.from_dict(data)
            self._sync_to_c()
            log.info(f"[ProjectSettings] Loaded from {path}")
        except Exception as e:
            log.error(f"[ProjectSettings] Failed to load settings: {e}")
            self._settings = ProjectSettings()
            self._sync_to_c()

    def _sync_to_c(self) -> None:
        """Sync Python settings to C global state."""
        c_set_render_sync_mode(self._settings.render_sync_mode.to_c())

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
            log.info(f"[ProjectSettings] Saved to {path}")
            return True
        except Exception as e:
            log.error(f"[ProjectSettings] Failed to save settings: {e}")
            return False

    def set_render_sync_mode(self, mode: RenderSyncMode) -> None:
        """Set render sync mode, sync to C, and save."""
        self._settings.render_sync_mode = mode
        c_set_render_sync_mode(mode.to_c())
        self.save()
