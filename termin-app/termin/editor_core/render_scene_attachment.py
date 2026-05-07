"""Scene render attachment service shared by editor frontends."""

from __future__ import annotations

from typing import Callable


class RenderSceneAttachment:
    """Attach/detach scene-owned render state by scene name.

    The editor display is managed by ``EditorSceneAttachment``. This class
    owns only scene display orchestration: save live configs, mount scene
    configs into ``RenderingManager``, and detach them again.
    """

    def __init__(
        self,
        scene_manager,
        rendering_controller,
        log_error: Callable[[str], None] | None = None,
    ) -> None:
        self._scene_manager = scene_manager
        self._rendering_controller = rendering_controller
        self._log_error = log_error

    def sync_scene_render_state(self, scene_name: str) -> bool:
        if self._rendering_controller is None:
            self._error("Cannot sync render state: RenderingController not available")
            return False
        scene = self._scene_manager.get_scene(scene_name)
        if scene is None:
            self._error(f"Cannot sync render state for scene '{scene_name}': not found")
            return False
        self._rendering_controller.sync_viewport_configs_to_scene(scene)
        self._rendering_controller.sync_render_target_configs_to_scene(scene)
        return True

    def attach_scene_to_render(self, scene_name: str) -> bool:
        if self._rendering_controller is None:
            self._error("Cannot attach scene to render: RenderingController not available")
            return False
        scene = self._scene_manager.get_scene(scene_name)
        if scene is None:
            self._error(f"Cannot attach scene '{scene_name}' to render: not found")
            return False
        self._rendering_controller.attach_scene(scene)
        return True

    def detach_scene_from_render(
        self,
        scene_name: str,
        save_state: bool = True,
    ) -> bool:
        if self._rendering_controller is None:
            self._error("Cannot detach scene from render: RenderingController not available")
            return False
        scene = self._scene_manager.get_scene(scene_name)
        if scene is None:
            self._error(f"Cannot detach scene '{scene_name}' from render: not found")
            return False
        if save_state:
            self.sync_scene_render_state(scene_name)
        self._rendering_controller.detach_scene(scene)
        return True

    def _error(self, message: str) -> None:
        if self._log_error is not None:
            self._log_error(message)

