from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QTreeView, QMenu, QInputDialog
from PyQt6.QtGui import QAction

from termin.editor.undo_stack import UndoCommand
from termin.editor.editor_commands import (
    AddEntityCommand,
    DeleteEntityCommand,
    RenameEntityCommand,
)
from termin.visualization.core.entity import Entity
from termin.kinematic.transform import Transform3
from termin.geombase.pose3 import Pose3
from termin.editor.editor_tree import SceneTreeModel


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

        cmd = DeleteEntityCommand(self._scene, ent)
        self._undo_handler(cmd, merge=False)

        parent_ent = cmd.parent_entity
        self.rebuild(select_obj=parent_ent)

        if self._request_viewport_update is not None:
            self._request_viewport_update()

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
