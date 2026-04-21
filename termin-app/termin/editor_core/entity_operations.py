"""Scene entity operations — UI-agnostic business logic.

All create/delete/rename/reparent/duplicate/drop flows live here. Both Qt
and tcgui scene-tree controllers delegate to an EntityOperations instance.

The view provides a small surface:
    - add_entity(entity)
    - add_entity_hierarchy(entity)
    - remove_entity(entity, select_parent=True)
    - move_entity(entity, new_parent)
    - update_entity(entity)
    - select_object(obj | None)

EntityOperations calls these after pushing undo commands, so the view only
knows how to render tree state, not how to compute it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from tcbase import log

from termin.editor.editor_commands import (
    AddEntityCommand,
    DeleteEntityCommand,
    DuplicateEntityCommand,
    RenameEntityCommand,
    ReparentEntityCommand,
)
from termin.editor.undo_stack import UndoCommand
from termin.editor_core.dialog_service import DialogService
from termin.kinematic.transform import Transform3
from termin.visualization.core.entity import Entity


class EntityOperations:
    def __init__(
        self,
        scene,
        undo_handler: Callable[[UndoCommand, bool], None],
        dialog_service: DialogService,
        view,
        request_viewport_update: Callable[[], None] | None = None,
    ):
        self._scene = scene
        self._undo_handler = undo_handler
        self._dialog = dialog_service
        self._view = view
        self._request_viewport_update = request_viewport_update

    def set_scene(self, scene) -> None:
        self._scene = scene

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_entity(self, parent: Entity | None) -> None:
        if self._scene is None:
            return

        parent_transform: Transform3 | None = None
        if isinstance(parent, Entity):
            parent_transform = parent.transform

        name = self._unique_entity_name("entity")
        ent = self._scene.create_entity(name)
        if parent_transform is not None:
            ent.transform.set_parent(parent_transform)

        cmd = AddEntityCommand(self._scene, ent, parent_transform=None)
        self._undo_handler(cmd, False)

        self._view.add_entity(ent)
        self._notify_viewport()

    def _unique_entity_name(self, base: str) -> str:
        existing = {e.name for e in self._scene.entities}
        i = 1
        while f"{base}{i}" in existing:
            i += 1
        return f"{base}{i}"

    # ------------------------------------------------------------------
    # Rename
    # ------------------------------------------------------------------

    def rename_entity(self, entity: Entity) -> None:
        if not isinstance(entity, Entity):
            return
        self._dialog.show_input(
            title="Rename entity",
            message="Name:",
            default=entity.name or "",
            on_result=lambda new: self._on_rename_result(entity, new),
        )

    def _on_rename_result(self, entity: Entity, new_name: str | None) -> None:
        if new_name is None:
            return
        new_name = new_name.strip()
        old_name = entity.name or ""
        if not new_name or new_name == old_name:
            return

        cmd = RenameEntityCommand(entity, old_name, new_name)
        self._undo_handler(cmd, False)

        self._view.update_entity(entity)
        self._notify_viewport()

    # ------------------------------------------------------------------
    # Duplicate
    # ------------------------------------------------------------------

    def duplicate_entity(self, entity: Entity) -> None:
        if not isinstance(entity, Entity) or self._scene is None:
            return

        cmd = DuplicateEntityCommand(self._scene, entity)
        self._undo_handler(cmd, False)

        copy = cmd.entity
        if copy is not None:
            self._view.add_entity_hierarchy(copy)

        self._notify_viewport()

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_entity(self, entity: Entity) -> None:
        if not isinstance(entity, Entity):
            return

        children = list(entity.transform.children) if entity.transform else []
        if not children:
            self._delete_with_children(entity)
            return

        self._dialog.show_choice(
            title="Delete Entity",
            message=f"Entity '{entity.name}' has {len(children)} child(ren).",
            choices=["Delete With Children", "Delete Only This", "Cancel"],
            default="Delete With Children",
            cancel="Cancel",
            on_result=lambda choice: self._on_delete_choice(entity, choice),
        )

    def _on_delete_choice(self, entity: Entity, choice: str | None) -> None:
        if choice == "Delete With Children":
            self._delete_with_children(entity)
        elif choice == "Delete Only This":
            self._delete_only_this(entity)

    def _delete_with_children(self, entity: Entity) -> None:
        parent_ent = None
        if entity.transform and entity.transform.parent:
            parent_ent = entity.transform.parent.entity

        self._delete_recursive(entity)
        self._view.remove_entity(entity, select_parent=False)

        if parent_ent is not None:
            self._view.select_object(parent_ent)

        self._notify_viewport()

    def _delete_only_this(self, entity: Entity) -> None:
        parent_transform = entity.transform.parent if entity.transform else None
        parent_entity = parent_transform.entity if parent_transform else None

        if entity.transform is not None:
            for child_transform in list(entity.transform.children):
                child_entity = child_transform.entity
                if child_entity is None:
                    continue
                cmd = ReparentEntityCommand(child_entity, entity.transform, parent_transform)
                self._undo_handler(cmd, False)
                self._view.move_entity(child_entity, parent_entity)

        cmd = DeleteEntityCommand(self._scene, entity)
        self._undo_handler(cmd, False)
        self._view.remove_entity(entity, select_parent=False)

        if parent_entity is not None:
            self._view.select_object(parent_entity)

        self._notify_viewport()

    def _delete_recursive(self, entity: Entity) -> None:
        if entity.transform:
            for child_t in list(entity.transform.children):
                child = child_t.entity
                if child is not None:
                    self._delete_recursive(child)
        cmd = DeleteEntityCommand(self._scene, entity)
        self._undo_handler(cmd, False)

    # ------------------------------------------------------------------
    # Reparent
    # ------------------------------------------------------------------

    def reparent_entity(self, entity: Entity, new_parent: Entity | None) -> None:
        if not isinstance(entity, Entity):
            return

        old_parent_t = entity.transform.parent if entity.transform else None
        new_parent_t = new_parent.transform if new_parent else None

        if old_parent_t is new_parent_t:
            return

        cmd = ReparentEntityCommand(entity, old_parent_t, new_parent_t)
        self._undo_handler(cmd, False)

        self._view.move_entity(entity, new_parent)
        self._notify_viewport()

    # ------------------------------------------------------------------
    # Drops from project browser
    # ------------------------------------------------------------------

    def drop_prefab(self, prefab_path: str, parent: Entity | None) -> None:
        from termin.visualization.core.resources import ResourceManager

        rm = ResourceManager.instance()
        prefab_name = Path(prefab_path).stem
        parent_transform = parent.transform if parent else None

        entity = rm.instantiate_prefab(prefab_name, parent=parent_transform)
        if entity is None:
            log.error(f"Failed to instantiate prefab: {prefab_name}")
            self._dialog.show_error("Prefab", f"Failed to instantiate prefab: {prefab_name}")
            return

        cmd = AddEntityCommand(self._scene, entity, parent_transform=None)
        self._undo_handler(cmd, False)
        self._view.add_entity_hierarchy(entity)
        self._notify_viewport()

    def drop_fbx(self, fbx_path: str, parent: Entity | None) -> None:
        from termin.loaders.fbx_instantiator import instantiate_fbx

        try:
            entity = instantiate_fbx(Path(fbx_path))
        except Exception as e:
            log.error(f"Failed to load FBX: {e}")
            self._dialog.show_error("FBX", f"Failed to load FBX: {e}")
            return

        parent_transform = parent.transform if parent else None
        cmd = AddEntityCommand(self._scene, entity, parent_transform=parent_transform)
        self._undo_handler(cmd, False)
        self._view.add_entity_hierarchy(entity)
        self._notify_viewport()

    def drop_glb(self, glb_path: str, parent: Entity | None) -> None:
        from termin.loaders.glb_instantiator import instantiate_glb
        from termin.visualization.core.resources import ResourceManager

        rm = ResourceManager.instance()
        glb_name = Path(glb_path).stem
        glb_asset = rm.get_glb_asset(glb_name)

        if glb_asset is None:
            log.error(f"GLBAsset '{glb_name}' not found in ResourceManager")
            self._dialog.show_error("GLB", f"GLBAsset '{glb_name}' not found")
            return

        try:
            result = instantiate_glb(glb_asset, scene=self._scene)
        except Exception as e:
            log.error(f"Failed to load GLB: {e}")
            self._dialog.show_error("GLB", f"Failed to load GLB: {e}")
            return

        entity = result.entity
        parent_transform = parent.transform if parent else None
        cmd = AddEntityCommand(self._scene, entity, parent_transform=parent_transform)
        self._undo_handler(cmd, False)
        self._view.add_entity_hierarchy(entity)
        self._notify_viewport()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _notify_viewport(self) -> None:
        if self._request_viewport_update is not None:
            self._request_viewport_update()
