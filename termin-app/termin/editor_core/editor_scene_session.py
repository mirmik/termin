"""Atomic active-scene rebinding for editor frontends."""

from __future__ import annotations

import logging
from typing import Callable


_logger = logging.getLogger(__name__)


class EditorSceneSession:
    def __init__(
        self,
        attachment,
        *,
        scene_hierarchy,
        entity_inspector,
        scene_properties,
        scene_names,
        shadow_settings,
        clear_selection: Callable[[], None],
        before_switch: Callable[[], None] | None = None,
        on_switched: Callable[[object], None] | None = None,
    ) -> None:
        self._attachment = attachment
        self._scene_hierarchy = scene_hierarchy
        self._entity_inspector = entity_inspector
        self._scene_properties = scene_properties
        self._scene_names = scene_names
        self._shadow_settings = shadow_settings
        self._clear_selection = clear_selection
        self._before_switch = before_switch
        self._on_switched = on_switched

    @property
    def scene(self):
        return self._attachment.scene

    def attach(self, scene, *, restore_state: bool = True) -> bool:
        previous = self.scene
        if _same_scene(previous, scene):
            return False
        if scene is None:
            raise ValueError("editor scene must not be None")
        if self._before_switch is not None:
            self._before_switch()
        self._clear_selection()
        try:
            self._attachment.attach(scene, restore_state=restore_state, transfer_camera_state=False)
            self._bind_models(scene)
        except Exception:
            _logger.exception("Editor scene switch failed; restoring previous scene")
            if previous is not None:
                try:
                    self._attachment.attach(
                        previous,
                        restore_state=False,
                        transfer_camera_state=False,
                    )
                    self._bind_models(previous)
                except Exception:
                    _logger.exception("Editor scene switch rollback failed")
            raise
        if self._on_switched is not None:
            self._on_switched(scene)
        return True

    def detach(self, *, save_state: bool = True) -> bool:
        if self.scene is None:
            return False
        if self._before_switch is not None:
            self._before_switch()
        self._clear_selection()
        self._attachment.detach(save_state=save_state)
        self._scene_hierarchy.set_scene(None)
        self._entity_inspector.set_scene(None)
        self._scene_properties.set_scene(None)
        self._scene_names.set_scene(None)
        self._shadow_settings.set_scene(None)
        if self._on_switched is not None:
            self._on_switched(None)
        return True

    def _bind_models(self, scene) -> None:
        self._scene_hierarchy.set_scene(scene)
        self._entity_inspector.set_scene(scene)
        self._scene_properties.set_scene(scene)
        self._scene_names.set_scene(scene)
        self._shadow_settings.set_scene(scene)


def _same_scene(left, right) -> bool:
    if left is None or right is None:
        return left is right
    left_handle = left.scene_handle()
    right_handle = right.scene_handle()
    return (
        left_handle.index == right_handle.index
        and left_handle.generation == right_handle.generation
    )


__all__ = ["EditorSceneSession"]
