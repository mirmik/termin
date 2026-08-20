"""Editor-presentation adapter used by GameModeModel."""

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
        self._session.attach(
            scene,
            restore_state=restore_state,
            transfer_camera_state=transfer_camera_state,
        )
        return True

    def detach_editor_from_scene(
        self,
        *,
        save_state: bool,
        clear_editor_scene_name: bool,
    ) -> bool:
        del clear_editor_scene_name
        self._session.detach(save_state=save_state)
        return True


__all__ = ["EditorGameModeConnector"]
