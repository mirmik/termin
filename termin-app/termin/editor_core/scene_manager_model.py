"""Toolkit-neutral scene manager viewer and action model."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Callable

from termin.engine import scene as engine_scene


_logger = logging.getLogger(__name__)
SceneMode = engine_scene.SceneMode


def _same_scene(left, right) -> bool:
    if left is None or right is None:
        return False
    left_handle = left.scene_handle()
    right_handle = right.scene_handle()
    return (
        left_handle.index == right_handle.index
        and left_handle.generation == right_handle.generation
    )


@dataclass(frozen=True)
class ManagedSceneSnapshot:
    name: str
    display_name: str
    mode: str
    entity_count: int
    handle: str
    path: str
    editing: bool
    extensions: tuple[str, ...]
    root_entities: tuple[str, ...]

    @property
    def details(self) -> str:
        lines = [
            f"Name: {self.name}",
            f"Handle: {self.handle} (index:generation)",
            f"Mode: {self.mode}",
            f"Path: {self.path or '(unsaved)'}",
            f"Editing: {'YES' if self.editing else 'no'}",
            "",
            f"=== Extensions ({len(self.extensions)}) ===",
            *(f"  {name}" for name in self.extensions),
            "" if self.extensions else "  (none)",
            "=== Entities ===",
            f"Total: {self.entity_count}",
            f"Root entities: {len(self.root_entities)}",
            "",
            *(f"  {name}" for name in self.root_entities[:20]),
        ]
        if len(self.root_entities) > 20:
            lines.append(f"  ... and {len(self.root_entities) - 20} more")
        return "\n".join(lines)


@dataclass(frozen=True)
class SceneManagerSnapshot:
    scenes: tuple[ManagedSceneSnapshot, ...]
    selected_name: str | None
    total_entities: int
    playing_count: int


class SceneManagerController:
    def __init__(
        self,
        scene_manager,
        *,
        get_editor_attachment: Callable[[], object | None] | None = None,
        on_render_attach: Callable[[str], object] | None = None,
        on_render_detach: Callable[[str], object] | None = None,
        on_editor_attach: Callable[[str], object] | None = None,
        on_editor_detach: Callable[[], object] | None = None,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        self._scene_manager = scene_manager
        self._get_editor_attachment = get_editor_attachment
        self._on_render_attach = on_render_attach
        self._on_render_detach = on_render_detach
        self._on_editor_attach = on_editor_attach
        self._on_editor_detach = on_editor_detach
        self._on_changed = on_changed
        self._selected_name: str | None = None

    @property
    def can_render_attach(self) -> bool:
        return self._on_render_attach is not None

    @property
    def can_render_detach(self) -> bool:
        return self._on_render_detach is not None

    @property
    def can_editor_attach(self) -> bool:
        return self._on_editor_attach is not None

    @property
    def can_editor_detach(self) -> bool:
        return self._on_editor_detach is not None

    def refresh(self) -> SceneManagerSnapshot:
        attachment = self._get_editor_attachment() if self._get_editor_attachment else None
        editing_scene = None if attachment is None else attachment.scene
        snapshots = []
        for name in sorted(self._scene_manager.scene_names()):
            scene = self._scene_manager.get_scene(name)
            if scene is None:
                continue
            path = self._scene_manager.get_scene_path(name) or ""
            handle = scene.scene_handle()
            entities = list(scene.entities)
            roots = tuple(
                f"[{'E' if entity.enabled else '-'}] {entity.name}"
                for entity in entities
                if entity.transform.parent is None
            )
            try:
                from termin.engine import scene_ext_attached_names

                extensions = tuple(str(value) for value in scene_ext_attached_names(scene))
            except Exception:
                _logger.exception("Failed to inspect extensions for scene '%s'", name)
                extensions = ()
            mode = self._scene_manager.get_mode(name)
            snapshots.append(ManagedSceneSnapshot(
                name=name,
                display_name=(f"{Path(path).stem} [{name}]" if path else f"{name} (unsaved)"),
                mode=mode.name if mode is not None else "?",
                entity_count=len(entities),
                handle=f"{handle.index}:{handle.generation}",
                path=path,
                editing=_same_scene(scene, editing_scene),
                extensions=extensions,
                root_entities=roots,
            ))
        names = {item.name for item in snapshots}
        if self._selected_name not in names:
            self._selected_name = snapshots[0].name if snapshots else None
        return SceneManagerSnapshot(
            tuple(snapshots),
            self._selected_name,
            sum(item.entity_count for item in snapshots),
            sum(item.mode == SceneMode.PLAY.name for item in snapshots),
        )

    def select(self, name: str | None) -> SceneManagerSnapshot:
        if name is not None and not self._scene_manager.has_scene(name):
            raise ValueError(f"scene '{name}' does not exist")
        self._selected_name = name
        return self.refresh()

    def duplicate_selected(self, new_name: str) -> SceneManagerSnapshot:
        source = self._require_selected()
        target = new_name.strip()
        if not target:
            raise ValueError("scene copy name must not be empty")
        if self._scene_manager.has_scene(target):
            raise ValueError(f"scene '{target}' already exists")
        if self._scene_manager.copy_scene(source, target) is None:
            raise RuntimeError(f"failed to copy scene '{source}'")
        self._selected_name = target
        return self._changed()

    def unload_selected(self) -> SceneManagerSnapshot:
        name = self._require_selected()
        scene = self._scene_manager.get_scene(name)
        attachment = self._get_editor_attachment() if self._get_editor_attachment else None
        if attachment is not None and _same_scene(attachment.scene, scene):
            if self._on_editor_detach is None:
                raise RuntimeError("cannot unload the editor-attached scene")
            self._require_success(self._on_editor_detach(), "failed to detach editor from scene")
        self._scene_manager.close_scene(name)
        self._selected_name = None
        return self._changed()

    def set_selected_mode(self, mode: SceneMode) -> SceneManagerSnapshot:
        name = self._require_selected()
        self._scene_manager.set_mode(name, mode)
        return self._changed()

    def render_attach_selected(self) -> SceneManagerSnapshot:
        return self._invoke_selected(self._on_render_attach, "render attach")

    def render_detach_selected(self) -> SceneManagerSnapshot:
        return self._invoke_selected(self._on_render_detach, "render detach")

    def editor_attach_selected(self) -> SceneManagerSnapshot:
        selected = self._require_selected()
        scene = self._scene_manager.get_scene(selected)
        attachment = self._get_editor_attachment() if self._get_editor_attachment else None
        if attachment is not None and _same_scene(attachment.scene, scene):
            return self.refresh()
        return self._invoke_selected(self._on_editor_attach, "editor attach")

    def editor_detach(self) -> SceneManagerSnapshot:
        if self._on_editor_detach is None:
            raise RuntimeError("editor detach is unavailable")
        attachment = self._get_editor_attachment() if self._get_editor_attachment else None
        if attachment is None or attachment.scene is None:
            return self.refresh()
        self._require_success(self._on_editor_detach(), "editor detach failed")
        return self._changed()

    def _invoke_selected(self, callback, label: str) -> SceneManagerSnapshot:
        if callback is None:
            raise RuntimeError(f"{label} is unavailable")
        self._require_success(callback(self._require_selected()), f"{label} failed")
        return self._changed()

    @staticmethod
    def _require_success(result: object, message: str) -> None:
        if result is False:
            raise RuntimeError(message)

    def _require_selected(self) -> str:
        if self._selected_name is None:
            raise RuntimeError("no scene is selected")
        if not self._scene_manager.has_scene(self._selected_name):
            raise RuntimeError(f"selected scene '{self._selected_name}' no longer exists")
        return self._selected_name

    def _changed(self) -> SceneManagerSnapshot:
        value = self.refresh()
        if self._on_changed is not None:
            self._on_changed()
        return value


__all__ = ["ManagedSceneSnapshot", "SceneManagerController", "SceneManagerSnapshot"]
