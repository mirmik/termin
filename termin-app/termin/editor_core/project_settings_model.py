"""Toolkit-neutral project settings state and mutation policy."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable

from termin.project.settings import ProjectSettingsManager, RenderSyncMode


_logger = logging.getLogger(__name__)
RENDER_SYNC_MODES = tuple(RenderSyncMode)


@dataclass(frozen=True)
class ProjectSettingsSnapshot:
    render_sync_mode: RenderSyncMode
    build_output_dir: str
    player_width: int
    player_height: int
    player_fullscreen: bool
    ignored_resource_paths: tuple[str, ...]


class ProjectSettingsController:
    def __init__(
        self,
        manager: ProjectSettingsManager | None = None,
        *,
        on_resource_settings_changed: Callable[[], None] | None = None,
        on_render_settings_changed: Callable[[], None] | None = None,
    ) -> None:
        self._manager = manager or ProjectSettingsManager.instance()
        self._on_resource_settings_changed = on_resource_settings_changed
        self._on_render_settings_changed = on_render_settings_changed

    def load(self) -> ProjectSettingsSnapshot:
        if self._manager.project_path is None:
            _logger.error("Project settings requested without an open project")
            raise RuntimeError("no project is open")
        settings = self._manager.settings
        return ProjectSettingsSnapshot(
            render_sync_mode=settings.render_sync_mode,
            build_output_dir=settings.build_output_dir,
            player_width=int(settings.player_window.width),
            player_height=int(settings.player_window.height),
            player_fullscreen=bool(settings.player_window.fullscreen),
            ignored_resource_paths=tuple(settings.ignored_resource_paths),
        )

    def set_render_sync_mode(self, mode: RenderSyncMode) -> ProjectSettingsSnapshot:
        before = self.load()
        if before.render_sync_mode != mode:
            self._manager.set_render_sync_mode(mode)
            if self._on_render_settings_changed is not None:
                self._on_render_settings_changed()
        return self.load()

    def set_player_window(
        self,
        width: int,
        height: int,
        fullscreen: bool,
    ) -> ProjectSettingsSnapshot:
        self._manager.set_player_window(int(width), int(height), bool(fullscreen))
        return self.load()

    def save(self, snapshot: ProjectSettingsSnapshot) -> ProjectSettingsSnapshot:
        before = self.load()
        if before.render_sync_mode != snapshot.render_sync_mode:
            self._manager.set_render_sync_mode(snapshot.render_sync_mode)
            if self._on_render_settings_changed is not None:
                self._on_render_settings_changed()
        if (
            before.player_width != int(snapshot.player_width)
            or before.player_height != int(snapshot.player_height)
            or before.player_fullscreen != bool(snapshot.player_fullscreen)
        ):
            self._manager.set_player_window(
                int(snapshot.player_width),
                int(snapshot.player_height),
                bool(snapshot.player_fullscreen),
            )
        resource_before = (
            before.build_output_dir,
            before.ignored_resource_paths,
        )
        self._manager.set_build_output_dir(snapshot.build_output_dir)
        self._manager.set_ignored_resource_paths(list(snapshot.ignored_resource_paths))
        saved = self.load()
        resource_after = (saved.build_output_dir, saved.ignored_resource_paths)
        if resource_after != resource_before and self._on_resource_settings_changed is not None:
            self._on_resource_settings_changed()
        return saved


__all__ = [
    "ProjectSettingsController",
    "ProjectSettingsSnapshot",
    "RENDER_SYNC_MODES",
]
