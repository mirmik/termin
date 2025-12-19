from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QTreeView, QMenu, QInputDialog, QMessageBox
from PyQt6.QtGui import QAction

from termin.editor.undo_stack import UndoCommand
from termin.editor.editor_commands import (
    AddEntityCommand,
    DeleteEntityCommand,
    RenameEntityCommand,
    ReparentEntityCommand,
)
from termin.visualization.core.entity import Entity
from termin.kinematic.transform import Transform3
from termin.geombase.pose3 import Pose3
from termin.editor.editor_tree import SceneTreeModel
from termin.visualization.core.resources import ResourceManager


class SceneTreeController:
    """
    Управляет QTreeView для сцены:
    - держит SceneTreeModel;
    - обрабатывает контекстное меню (Add/Rename/Delete entity);
    - прокидывает выбор наружу через колбэк on_object_selected.
    """

    def __init__(
        self,
        tree_view: QTreeView,
        scene,
        undo_handler: Callable[[UndoCommand, bool], None],
        on_object_selected: Callable[[object | None], None],
        request_viewport_update: Optional[Callable[[], None]] = None,
    ) -> None:
        self._tree = tree_view
        self._scene = scene
        self._undo_handler = undo_handler
        self._on_object_selected = on_object_selected
        self._request_viewport_update = request_viewport_update

        self._model: SceneTreeModel = SceneTreeModel(self._scene)
        self._setup_tree()

    @property
    def model(self) -> SceneTreeModel:
        return self._model

    def _setup_tree(self) -> None:
        self._tree.setModel(self._model)
        self._tree.expandAll()
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)

        # Enable drag-drop (DragDrop mode allows both internal moves and external drops)
        self._tree.setDragEnabled(True)
        self._tree.setAcceptDrops(True)
        self._tree.setDropIndicatorShown(True)
        self._tree.setDragDropMode(QTreeView.DragDropMode.DragDrop)
        self._tree.setDefaultDropAction(Qt.DropAction.MoveAction)

        # Connect model signals for reparenting and prefab/fbx drops
        self._model.entity_reparent_requested.connect(self._on_entity_reparent_requested)
        self._model.prefab_drop_requested.connect(self._on_prefab_drop_requested)
        self._model.fbx_drop_requested.connect(self._on_fbx_drop_requested)
        self._model.glb_drop_requested.connect(self._on_glb_drop_requested)

        sel_model = self._tree.selectionModel()
        if sel_model is not None:
            sel_model.currentChanged.connect(self._on_tree_current_changed)

    # ---------- публичный API для EditorWindow ----------

    def rebuild(self, select_obj: object | None = None) -> None:
        """
        Перестраивает модель по текущей сцене и опционально выделяет объект.
        Вызывается, когда структура сцены поменялась (Add/Delete/Rename, undo/redo).
        """
        self._model = SceneTreeModel(self._scene)
        self._setup_tree()
        if select_obj is not None:
            self.select_object(select_obj)

    def select_object(self, obj: object | None) -> None:
        """
        Выделяет объект в дереве, если он там есть.
        """
        if obj is None:
            return
        model: SceneTreeModel = self._tree.model()
        idx = model.index_for_object(obj)
        if not idx.isValid():
            return
        self._tree.setCurrentIndex(idx)
        self._tree.scrollTo(idx)

    # ---------- обработчики событий дерева ----------

    def _on_tree_current_changed(self, current, _previous) -> None:
        if not current.isValid():
            self._on_object_selected(None)
            return
        self._on_tree_clicked(current)

    def _on_tree_clicked(self, index) -> None:
        node = index.internalPointer()
        obj = node.obj if node is not None else None
        self._on_object_selected(obj)

    # ---------- контекстное меню ----------

    def _on_tree_context_menu(self, pos: QPoint) -> None:
        index = self._tree.indexAt(pos)
        node = index.internalPointer() if index.isValid() else None
        target_obj = node.obj if node is not None else None

        menu = QMenu(self._tree)
        action_add = menu.addAction("Add entity")

        action_rename: Optional[QAction] = None
        action_delete: Optional[QAction] = None
        if isinstance(target_obj, Entity):
            action_rename = menu.addAction("Rename entity")
            action_delete = menu.addAction("Delete entity")

        global_pos = self._tree.viewport().mapToGlobal(pos)
        action = menu.exec(global_pos)

        if action == action_add:
            self._create_entity_from_context(target_obj)
        elif action == action_rename:
            self._rename_entity_from_context(target_obj)
        elif action == action_delete:
            self._delete_entity_from_context(target_obj)

    # ---------- операции над сущностями ----------

    def _create_entity_from_context(self, target_obj: object | None) -> None:
        parent_transform: Optional[Transform3] = None
        if isinstance(target_obj, Entity):
            parent_transform = target_obj.transform
        elif isinstance(target_obj, Transform3):
            parent_transform = target_obj

        existing = {e.name for e in self._scene.entities}
        base = "entity"
        i = 1
        while f"{base}{i}" in existing:
            i += 1
        name = f"{base}{i}"

        ent = Entity(pose=Pose3.identity(), name=name)
        cmd = AddEntityCommand(self._scene, ent, parent_transform=parent_transform)
        self._undo_handler(cmd, merge=False)

        self.rebuild(select_obj=ent)
        if self._request_viewport_update is not None:
            self._request_viewport_update()

    def _delete_entity_from_context(self, ent: Entity | None) -> None:
        if not isinstance(ent, Entity):
            return

        children = list(ent.transform.children)

        delete_children = False
        if children:
            # Entity has children - ask user what to do
            msg_box = QMessageBox(self._tree)
            msg_box.setWindowTitle("Delete Entity")
            msg_box.setText(f"Entity '{ent.name}' has {len(children)} child(ren).")
            msg_box.setInformativeText("What do you want to do?")

            btn_with_children = msg_box.addButton("Delete With Children", QMessageBox.ButtonRole.DestructiveRole)
            btn_only_this = msg_box.addButton("Delete Only This", QMessageBox.ButtonRole.AcceptRole)
            btn_cancel = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)

            msg_box.setDefaultButton(btn_cancel)
            msg_box.exec()

            clicked = msg_box.clickedButton()
            if clicked == btn_cancel:
                return

            if clicked == btn_only_this:
                # Move children to parent, then delete entity
                parent_transform = ent.transform.parent
                for child_transform in children:
                    child_entity = child_transform.entity
                    if child_entity is not None:
                        cmd = ReparentEntityCommand(child_entity, ent.transform, parent_transform)
                        self._undo_handler(cmd, merge=False)
            else:
                # Delete with children
                delete_children = True

        parent_ent_for_select = ent.transform.parent.entity if ent.transform.parent else None

        if delete_children:
            # Delete children first (bottom-up to handle nested hierarchies)
            self._delete_entity_recursive(ent)
        else:
            # Delete only this entity
            cmd = DeleteEntityCommand(self._scene, ent)
            self._undo_handler(cmd, merge=False)

        self.rebuild(select_obj=parent_ent_for_select)

        if self._request_viewport_update is not None:
            self._request_viewport_update()

    def _delete_entity_recursive(self, ent: Entity) -> None:
        """Delete entity and all its children recursively (children first)."""
        # First delete all children
        for child_transform in list(ent.transform.children):
            child_entity = child_transform.entity
            if child_entity is not None:
                self._delete_entity_recursive(child_entity)

        # Then delete this entity
        cmd = DeleteEntityCommand(self._scene, ent)
        self._undo_handler(cmd, merge=False)

    def _rename_entity_from_context(self, ent: Entity | None) -> None:
        if not isinstance(ent, Entity):
            return

        old_name = ent.name or ""
        new_name, ok = QInputDialog.getText(
            self._tree, "Rename entity", "Name:", text=old_name
        )
        if not ok:
            return

        new_name = new_name.strip()
        if not new_name or new_name == old_name:
            return

        cmd = RenameEntityCommand(ent, old_name, new_name)
        self._undo_handler(cmd, merge=False)

        self.rebuild(select_obj=ent)

        if self._request_viewport_update is not None:
            self._request_viewport_update()

    # ---------- drag-drop reparenting ----------

    def _on_entity_reparent_requested(
        self,
        entity: Entity,
        new_parent_entity: Entity | None,
    ) -> None:
        """Handle entity reparenting from drag-drop."""
        old_parent = entity.transform.parent
        new_parent = new_parent_entity.transform if new_parent_entity else None

        # Don't do anything if parent isn't changing
        if old_parent is new_parent:
            return

        cmd = ReparentEntityCommand(entity, old_parent, new_parent)
        self._undo_handler(cmd, merge=False)

        self.rebuild(select_obj=entity)

        if self._request_viewport_update is not None:
            self._request_viewport_update()

    # ---------- prefab drop ----------

    def _on_prefab_drop_requested(
        self,
        prefab_path: str,
        parent_entity: Entity | None,
    ) -> None:
        """Handle prefab drop from Project Browser."""
        rm = ResourceManager.instance()

        # Use PrefabAsset.instantiate() to properly add PrefabInstanceMarker
        prefab_name = Path(prefab_path).stem
        parent_transform = parent_entity.transform if parent_entity else None

        entity = rm.instantiate_prefab(prefab_name, parent=parent_transform)
        if entity is None:
            print(f"Failed to instantiate prefab: {prefab_name}")
            return

        cmd = AddEntityCommand(self._scene, entity, parent_transform=None)  # Already parented
        self._undo_handler(cmd, merge=False)

        self.rebuild(select_obj=entity)

        if self._request_viewport_update is not None:
            self._request_viewport_update()

    # ---------- fbx drop ----------

    def _on_fbx_drop_requested(
        self,
        fbx_path: str,
        parent_entity: Entity | None,
    ) -> None:
        """Handle FBX drop from Project Browser."""
        from termin.loaders.fbx_instantiator import instantiate_fbx

        try:
            entity = instantiate_fbx(Path(fbx_path))
        except Exception as e:
            print(f"Failed to load FBX: {e}")
            return

        parent_transform = parent_entity.transform if parent_entity else None
        cmd = AddEntityCommand(self._scene, entity, parent_transform=parent_transform)
        self._undo_handler(cmd, merge=False)

        self.rebuild(select_obj=entity)

        if self._request_viewport_update is not None:
            self._request_viewport_update()

    # ---------- glb drop ----------

    def _on_glb_drop_requested(
        self,
        glb_path: str,
        parent_entity: Entity | None,
    ) -> None:
        """Handle GLB drop from Project Browser."""
        from pathlib import Path
        from termin.loaders.glb_instantiator import instantiate_glb
        from termin.visualization.core.resources import ResourceManager

        rm = ResourceManager.instance()
        glb_name = Path(glb_path).stem
        glb_asset = rm.get_glb_asset(glb_name)

        if glb_asset is None:
            print(f"Failed to load GLB: GLBAsset '{glb_name}' not found in ResourceManager")
            return

        try:
            result = instantiate_glb(glb_asset)
        except Exception as e:
            print(f"Failed to load GLB: {e}")
            return

        entity = result.entity
        parent_transform = parent_entity.transform if parent_entity else None
        cmd = AddEntityCommand(self._scene, entity, parent_transform=parent_transform)
        self._undo_handler(cmd, merge=False)

        self.rebuild(select_obj=entity)

        if self._request_viewport_update is not None:
            self._request_viewport_update()
