"""Adapters from GameModeModel's stable protocol to scene sessions."""

from __future__ import annotations


class EditorGameModeConnector:
    def __init__(self, scene_manager, session) -> None:
        self._scene_manager = scene_manager
        self._session = session

    def attach_editor_to_scene(
        self,
        name: str,
        *,
        restore_state: bool,
        transfer_camera_state: bool,
        update_editor_scene_name: bool,
    ) -> bool:
        del update_editor_scene_name
        scene = self._scene_manager.get_scene(name)
        if scene is None:
            raise ValueError(f"scene '{name}' does not exist")
        return self._session.attach(
            scene,
            restore_state=restore_state,
            transfer_camera_state=transfer_camera_state,
        )

    def detach_editor_from_scene(
        self,
        *,
        save_state: bool,
        clear_editor_scene_name: bool,
    ) -> bool:
        del clear_editor_scene_name
        return self._session.detach(save_state=save_state)


class RenderGameModeConnector:
    def __init__(self, session) -> None:
        self._session = session

    def sync_scene_render_state(self, name: str) -> None:
        self._session.sync_scene_render_state(name)

    def attach_scene_to_render(self, name: str) -> bool:
        return self._session.attach(name)

    def detach_scene_from_render(self, name: str, *, save_state: bool) -> bool:
        return self._session.detach(name, save_state=save_state)


__all__ = ["EditorGameModeConnector", "RenderGameModeConnector"]
