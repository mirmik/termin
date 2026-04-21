from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QTreeView, QMenu
from PyQt6.QtGui import QAction

from termin.editor.editor_tree import SceneTreeModel
from termin.editor.undo_stack import UndoCommand
from termin.editor_core.dialog_service import DialogService
from termin.editor_core.entity_operations import EntityOperations
from termin.visualization.core.entity import Entity


class SceneTreeController:
    """
    Управляет QTreeView для сцены:
    - держит SceneTreeModel;
    - рендерит контекстное меню и пробрасывает действия в EntityOperations;
    - отдаёт drag/drop и выделение наружу.

    Бизнес-логика (create/delete/rename/reparent/duplicate/drops) живёт в
    EntityOperations и общая с tcgui-редактором.
    """

    def __init__(
        self,
        tree_view: QTreeView,
        scene,
        undo_handler: Callable[[UndoCommand, bool], None],
        dialog_service: DialogService,
        on_object_selected: Callable[[object | None], None],
        request_viewport_update: Optional[Callable[[], None]] = None,
    ) -> None:
        self._tree = tree_view
        self._scene = scene
        self._on_object_selected = on_object_selected
        self._request_viewport_update = request_viewport_update

        self._model: SceneTreeModel = SceneTreeModel(self._scene)
        self._setup_tree_once()
        self._apply_model(expand_all=True)

        self._ops = EntityOperations(
            scene=scene,
            undo_handler=undo_handler,
            dialog_service=dialog_service,
            view=self,
            request_viewport_update=request_viewport_update,
        )

    @property
    def model(self) -> SceneTreeModel:
        return self._model

    @property
    def operations(self) -> EntityOperations:
        return self._ops

    def _setup_tree_once(self) -> None:
        """One-time tree view setup (signals that don't change with model)."""
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)

        self._tree.setDragEnabled(True)
        self._tree.setAcceptDrops(True)
        self._tree.setDropIndicatorShown(True)
        self._tree.setDragDropMode(QTreeView.DragDropMode.DragDrop)
        self._tree.setDefaultDropAction(Qt.DropAction.MoveAction)

    def _apply_model(self, expand_all: bool = False) -> None:
        """Apply current model to tree and connect model-specific signals."""
        self._tree.setModel(self._model)
        if expand_all:
            self._tree.expandAll()

        self._model.entity_reparent_requested.connect(self._on_entity_reparent_requested)
        self._model.prefab_drop_requested.connect(self._on_prefab_drop_requested)
        self._model.fbx_drop_requested.connect(self._on_fbx_drop_requested)
        self._model.glb_drop_requested.connect(self._on_glb_drop_requested)
        self._model.entity_enabled_changed.connect(self._on_entity_enabled_changed)

        sel_model = self._tree.selectionModel()
        if sel_model is not None:
            sel_model.currentChanged.connect(self._on_tree_current_changed)

    # ---------- публичный API для EditorWindow ----------

    def set_scene(self, scene) -> None:
        """Set scene, rebuilding model to avoid invalid entity access."""
        if self._scene is not scene:
            self._model.rebuild_for_scene(None)
        self._scene = scene
        self._ops.set_scene(scene)

    def rebuild(self, select_obj: object | None = None) -> None:
        """
        Перестраивает модель по текущей сцене и опционально выделяет объект.
        Вызывается, когда структура сцены поменялась (Add/Delete/Rename, undo/redo).
        """
        if self._scene is None:
            self._model.rebuild_for_scene(None)
            return

        expanded_uuids = self._get_expanded_entity_uuids()
        self._model.rebuild_for_scene(self._scene)
        self._restore_expanded_state(expanded_uuids)

        if select_obj is not None:
            self.select_object(select_obj)

    def _get_expanded_entity_uuids(self) -> set[str]:
        expanded = set()
        self._collect_expanded_recursive(self._model.root, expanded)
        return expanded

    def _collect_expanded_recursive(self, node, expanded: set[str]) -> None:
        from termin.editor.editor_tree import NodeWrapper

        for child in node.children:
            if isinstance(child, NodeWrapper) and isinstance(child.obj, Entity):
                if not child.obj.valid():
                    continue
                index = self._model.index_for_object(child.obj)
                if index.isValid() and self._tree.isExpanded(index):
                    if child.obj.uuid:
                        expanded.add(child.obj.uuid)
            self._collect_expanded_recursive(child, expanded)

    def _restore_expanded_state(self, expanded_uuids: set[str]) -> None:
        self._expand_by_uuids_recursive(self._model.root, expanded_uuids)

    def _expand_by_uuids_recursive(self, node, expanded_uuids: set[str]) -> None:
        from termin.editor.editor_tree import NodeWrapper

        for child in node.children:
            if isinstance(child, NodeWrapper) and isinstance(child.obj, Entity):
                if not child.obj.valid():
                    continue
                if child.obj.uuid and child.obj.uuid in expanded_uuids:
                    index = self._model.index_for_object(child.obj)
                    if index.isValid():
                        self._tree.setExpanded(index, True)
            self._expand_by_uuids_recursive(child, expanded_uuids)

    # ---------- инкрементальные обновления (view surface для EntityOperations) ----------

    def add_entity(self, entity: Entity) -> None:
        self._model.add_entity(entity)
        self.select_object(entity)

    def add_entity_hierarchy(self, entity: Entity) -> None:
        self._model.add_entity_hierarchy(entity)
        self.select_object(entity)

    def remove_entity(self, entity: Entity, select_parent: bool = True) -> None:
        parent_ent = None
        if select_parent:
            node = self._model._obj_to_node.get(entity)
            if node and node.parent and node.parent.obj:
                parent_ent = node.parent.obj

        self._model.remove_entity(entity)

        if select_parent and parent_ent:
            self.select_object(parent_ent)

    def move_entity(self, entity: Entity, new_parent: Entity | None) -> None:
        self._model.move_entity(entity, new_parent)
        self.select_object(entity)

    def update_entity(self, entity: Entity) -> None:
        self._model.update_entity(entity)

    def get_expanded_entity_uuids(self) -> list[str]:
        return list(self._get_expanded_entity_uuids())

    def set_expanded_entity_uuids(self, uuids: list[str]) -> None:
        self._restore_expanded_state(set(uuids))

    def select_object(self, obj: object | None) -> None:
        """Выделяет объект в дереве; раскрывает родительские узлы."""
        if obj is None:
            return
        model: SceneTreeModel = self._tree.model()
        idx = model.index_for_object(obj)
        if not idx.isValid():
            return

        parent_idx = idx.parent()
        while parent_idx.isValid():
            self._tree.setExpanded(parent_idx, True)
            parent_idx = parent_idx.parent()

        self._tree.setCurrentIndex(idx)
        self._tree.scrollTo(idx)

    # ---------- обработчики событий дерева ----------

    def _on_tree_current_changed(self, current, _previous) -> None:
        if not current.isValid():
            self._on_object_selected(None)
            return
        node = current.internalPointer()
        obj = node.obj if node is not None else None
        self._on_object_selected(obj)

    def _on_tree_context_menu(self, pos: QPoint) -> None:
        index = self._tree.indexAt(pos)
        node = index.internalPointer() if index.isValid() else None
        target_obj = node.obj if node is not None else None

        menu = QMenu(self._tree)
        action_add = menu.addAction("Add entity")

        action_rename: Optional[QAction] = None
        action_delete: Optional[QAction] = None
        action_duplicate: Optional[QAction] = None
        if isinstance(target_obj, Entity):
            action_rename = menu.addAction("Rename entity")
            action_duplicate = menu.addAction("Duplicate")
            action_delete = menu.addAction("Delete entity")

        global_pos = self._tree.viewport().mapToGlobal(pos)
        action = menu.exec(global_pos)

        parent_entity = target_obj if isinstance(target_obj, Entity) else None
        if action == action_add:
            self._ops.create_entity(parent_entity)
        elif action == action_rename and isinstance(target_obj, Entity):
            self._ops.rename_entity(target_obj)
        elif action == action_duplicate and isinstance(target_obj, Entity):
            self._ops.duplicate_entity(target_obj)
        elif action == action_delete and isinstance(target_obj, Entity):
            self._ops.delete_entity(target_obj)

    # ---------- drag-drop / model signals ----------

    def _on_entity_reparent_requested(
        self,
        entity: Entity,
        new_parent_entity: Entity | None,
    ) -> None:
        self._ops.reparent_entity(entity, new_parent_entity)

    def _on_prefab_drop_requested(
        self,
        prefab_path: str,
        parent_entity: Entity | None,
    ) -> None:
        self._ops.drop_prefab(prefab_path, parent_entity)

    def _on_fbx_drop_requested(
        self,
        fbx_path: str,
        parent_entity: Entity | None,
    ) -> None:
        self._ops.drop_fbx(fbx_path, parent_entity)

    def _on_glb_drop_requested(
        self,
        glb_path: str,
        parent_entity: Entity | None,
    ) -> None:
        self._ops.drop_glb(glb_path, parent_entity)

    def _on_entity_enabled_changed(self, entity: Entity, enabled: bool) -> None:
        if self._request_viewport_update is not None:
            self._request_viewport_update()
