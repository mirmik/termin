"""Render-scene attachment orchestration independent of the UI toolkit."""

from __future__ import annotations

import logging
from typing import Callable


_logger = logging.getLogger(__name__)


class RenderSceneSession:
    def __init__(
        self,
        scene_manager,
        rendering_model,
        display_workspace,
        *,
        sync_viewports: Callable[[], None],
        request_render: Callable[[], None],
    ) -> None:
        self._scene_manager = scene_manager
        self._rendering_model = rendering_model
        self._workspace = display_workspace
        self._sync_viewports = sync_viewports
        self._request_render = request_render

    def attach(self, name: str) -> bool:
        scene = self._require_scene(name)
        viewports = self._rendering_model.attach_scene(scene)
        try:
            for viewport in viewports:
                display = self._rendering_model.manager.get_display_for_viewport(viewport)
                if display is not None:
                    self._workspace.configure_viewport_input(display, viewport)
        except Exception:
            _logger.exception("Render scene attach input setup failed; rolling back")
            emptied = self._rendering_model.detach_scene(scene)
            self._remove_empty_displays(emptied)
            raise
        self._publish()
        return True

    def detach(self, name: str, *, save_state: bool = True) -> bool:
        scene = self._require_scene(name)
        if save_state:
            self.sync_scene_render_state(name)
        emptied = self._rendering_model.detach_scene(scene)
        self._remove_empty_displays(emptied)
        self._publish()
        return True

    def sync_scene_render_state(self, name: str) -> None:
        scene = self._require_scene(name)
        self._rendering_model.sync_viewport_configs_to_scene(scene)
        self._rendering_model.sync_render_target_configs_to_scene(scene)

    def reconcile_attached_scene(self, scene) -> None:
        """Reconcile editor presentation after EngineCore changed primary.

        RuntimeSession owns the gameplay attachment itself. The editor only
        wires host input, removes now-empty display pages, and republishes its
        viewport projection; failures here do not participate in the gameplay
        transaction.
        """
        topology = self._rendering_model.manager.topology
        if not topology.is_attached(scene):
            raise RuntimeError(
                f"primary scene '{scene.name}' has no render attachment"
            )
        for viewport in topology.viewports(scene):
            display = self._rendering_model.manager.get_display_for_viewport(viewport)
            if display is not None:
                self._workspace.configure_viewport_input(display, viewport)
        empty_displays = {
            display.handle
            for display in tuple(self._workspace.displays)
            if not self._workspace.is_editor_display(display) and not display.viewports
        }
        self._remove_empty_displays(empty_displays)
        self._publish()

    def _require_scene(self, name: str):
        scene = self._scene_manager.get_scene(name)
        if scene is None:
            raise ValueError(f"scene '{name}' does not exist")
        return scene

    def _remove_empty_displays(self, display_handles: set[tuple[int, int]]) -> None:
        for display in tuple(self._workspace.displays):
            if self._workspace.is_editor_display(display):
                continue
            if display.handle in display_handles and not display.viewports:
                self._workspace.remove_display(display)

    def _publish(self) -> None:
        self._sync_viewports()
        self._request_render()


__all__ = ["RenderSceneSession"]
