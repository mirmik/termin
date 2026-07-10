"""tcgui projection for the shared scene hierarchy controller."""

from __future__ import annotations

from collections.abc import Callable

from tcgui.widgets.events import DragEvent
from tcgui.widgets.icon_button import IconButton
from tcgui.widgets.label import Label
from tcgui.widgets.menu import Menu, MenuItem
from tcgui.widgets.tree import TreeNode, TreeWidget

from termin.editor_core.dialog_service import DialogService
from termin.editor_core.scene_hierarchy_model import (
    SceneHierarchyController,
    SceneHierarchySnapshot,
)
from termin.editor_core.undo_stack import UndoCommand
from termin.scene import Entity


class SceneTreeControllerTcgui:
    """Render shared hierarchy state into the temporary legacy frontend."""

    def __init__(
        self,
        tree_widget: TreeWidget,
        scene,
        undo_handler: Callable[[UndoCommand, bool], None],
        dialog_service: DialogService,
        on_object_selected: Callable[[object | None], None],
        request_viewport_update: Callable[[], None] | None = None,
        collapse_all_button: IconButton | None = None,
    ) -> None:
        self._tree = tree_widget
        self._entity_to_node: dict[str, TreeNode] = {}
        self._applying_snapshot = False
        self._ctx_menu = Menu()
        self._controller = SceneHierarchyController(
            scene,
            undo_handler=undo_handler,
            dialog_service=dialog_service,
            on_object_selected=on_object_selected,
            request_viewport_update=request_viewport_update,
        )

        self._tree.draggable = True
        self._tree.on_select = self._on_tree_select
        self._tree.on_delete = self._on_tree_delete
        self._tree.on_drop = self._on_drop
        self._tree.on_external_drag = self._on_external_drag
        self._tree.on_external_drop = self._on_external_drop
        self._tree.on_context_menu = self._on_tree_context_menu
        self._tree.on_expand = lambda node: self._on_expansion(node, True)
        self._tree.on_collapse = lambda node: self._on_expansion(node, False)
        if collapse_all_button is not None:
            collapse_all_button.on_click = self.collapse_all

        self._controller.set_snapshot_changed_handler(self._apply_snapshot)
        self._apply_snapshot(self._controller.snapshot(), expand_roots=True)
        self._rebuild_context_menu(None)

    @property
    def operations(self):
        return self._controller.operations

    def set_scene(self, scene) -> None:
        self._controller.set_scene(scene)

    def collapse_all(self) -> None:
        for root in self._tree.root_nodes:
            self._collapse_recursive(root)
        self._applying_snapshot = True
        try:
            self._controller.collapse_all()
        finally:
            self._applying_snapshot = False
        self._tree._dirty = True

    def _collapse_recursive(self, node: TreeNode) -> None:
        node.expanded = False
        for child in node.subnodes:
            self._collapse_recursive(child)

    def rebuild(self, select_obj: object | None = None) -> None:
        expanded = self.get_expanded_entity_uuids()
        self._controller.set_expanded_entity_uuids(expanded)
        self._controller.rebuild(select_obj=select_obj)

    def select_object(self, obj: object | None) -> None:
        self._controller.select_object(obj)

    def get_expanded_entity_uuids(self) -> list[str]:
        result: list[str] = []
        for stable_id, node in self._entity_to_node.items():
            if node.expanded:
                result.append(stable_id)
        return sorted(result)

    def set_expanded_entity_uuids(self, uuids: list[str]) -> None:
        self._controller.set_expanded_entity_uuids(uuids)

    def _apply_snapshot(
        self,
        snapshot: SceneHierarchySnapshot,
        *,
        expand_roots: bool = False,
    ) -> None:
        if self._applying_snapshot:
            return
        self._applying_snapshot = True
        try:
            self._entity_to_node.clear()
            self._tree.clear()
            for hierarchy_node in snapshot.nodes:
                label = Label()
                label.text = hierarchy_node.name
                node = TreeNode(label)
                node.data = self._controller.entity_for_id(hierarchy_node.stable_id)
                node.expanded = hierarchy_node.stable_id in snapshot.expanded_ids
                if expand_roots and hierarchy_node.parent_id is None:
                    node.expanded = True
                self._entity_to_node[hierarchy_node.stable_id] = node
                parent_node = self._entity_to_node.get(hierarchy_node.parent_id or "")
                if parent_node is None:
                    self._tree.add_root(node)
                else:
                    parent_node.add_node(node)
            selected_node = self._entity_to_node.get(snapshot.selected_id or "")
            if selected_node is not None:
                self._expand_ancestors(selected_node)
                self._tree._rebuild_visible()
                self._tree._select_node(selected_node)
                self._tree._ensure_visible(selected_node)
        finally:
            self._applying_snapshot = False
        self._tree._dirty = True

    def _expand_ancestors(self, node: TreeNode) -> None:
        parent = self._parent_node(node)
        while parent is not None:
            parent.expanded = True
            parent = self._parent_node(parent)

    def _parent_node(self, target: TreeNode) -> TreeNode | None:
        for candidate in self._entity_to_node.values():
            if target in candidate.subnodes:
                return candidate
        return None

    @staticmethod
    def _stable_id(node: TreeNode | None) -> str | None:
        if node is None or not isinstance(node.data, Entity):
            return None
        return node.data.uuid or None

    def _on_tree_select(self, node: TreeNode | None) -> None:
        entity = node.data if node is not None and isinstance(node.data, Entity) else None
        self._rebuild_context_menu(entity)
        if self._applying_snapshot:
            return
        self._applying_snapshot = True
        try:
            self._controller.select_id(self._stable_id(node))
        finally:
            self._applying_snapshot = False

    def _on_expansion(self, node: TreeNode, expanded: bool) -> None:
        if self._applying_snapshot:
            return
        stable_id = self._stable_id(node)
        if stable_id is None:
            return
        self._applying_snapshot = True
        try:
            self._controller.set_expanded(stable_id, expanded)
        finally:
            self._applying_snapshot = False

    def _on_tree_delete(self, node: TreeNode) -> None:
        stable_id = self._stable_id(node)
        if stable_id is not None:
            self._controller.execute_context_action("delete", stable_id)

    def _on_tree_context_menu(self, node: TreeNode | None, x: float, y: float) -> None:
        entity = node.data if node is not None and isinstance(node.data, Entity) else None
        self._rebuild_context_menu(entity)
        if self._tree._ui is not None:
            self._ctx_menu.show(self._tree._ui, x, y)

    def _rebuild_context_menu(self, entity: Entity | None) -> None:
        stable_id = entity.uuid if entity is not None and entity.uuid else None
        self._ctx_menu.items = [
            MenuItem(
                action.label,
                enabled=action.enabled,
                on_click=lambda action_id=action.stable_id, target_id=stable_id: (
                    self._controller.execute_context_action(action_id, target_id)
                ),
            )
            for action in self._controller.context_actions(stable_id)
        ]

    def _on_drop(self, dragged: TreeNode, target: TreeNode | None, position: str) -> None:
        dragged_id = self._stable_id(dragged)
        if dragged_id is None:
            return
        self._controller.drop_entity(dragged_id, self._stable_id(target), position)

    def _on_external_drag(self, event: DragEvent, target: TreeNode | None, position: str) -> bool:
        if event.payload.kind != "project_file" or not isinstance(event.payload.data, dict):
            return False
        extension = event.payload.data.get("extension")
        return isinstance(extension, str) and self._controller.can_drop_project_file(extension)

    def _on_external_drop(self, event: DragEvent, target: TreeNode | None, position: str) -> bool:
        if not self._on_external_drag(event, target, position):
            return False
        data = event.payload.data
        if not isinstance(data, dict):
            return False
        path = data.get("path")
        extension = data.get("extension")
        if not isinstance(path, str) or not isinstance(extension, str):
            return False
        self._controller.drop_project_file(
            path,
            extension,
            self._stable_id(target),
            position,
        )
        return True
