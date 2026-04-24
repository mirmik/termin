"""Scene tree controller for tcgui editor."""

from __future__ import annotations

from typing import Callable, Optional

from tcgui.widgets.tree import TreeNode, TreeWidget
from tcgui.widgets.label import Label
from tcgui.widgets.menu import Menu, MenuItem

from termin.editor.undo_stack import UndoCommand
from termin.editor_core.dialog_service import DialogService
from termin.editor_core.entity_operations import EntityOperations
from termin.visualization.core.entity import Entity


class SceneTreeControllerTcgui:
    """Manages tcgui TreeWidget for the scene.

    Holds:
    - tree-view state (node <-> entity map, expansion, selection)
    - context menu routing into EntityOperations
    - drag-drop dispatch into EntityOperations.reparent_entity

    Business logic (create/delete/rename/reparent/duplicate/drops) lives in
    EntityOperations and is shared with the Qt editor.
    """

    def __init__(
        self,
        tree_widget: TreeWidget,
        scene,
        undo_handler: Callable[[UndoCommand, bool], None],
        dialog_service: DialogService,
        on_object_selected: Callable[[object | None], None],
        request_viewport_update: Optional[Callable[[], None]] = None,
    ) -> None:
        self._tree = tree_widget
        self._scene = scene
        self._on_object_selected = on_object_selected
        self._request_viewport_update = request_viewport_update

        self._entity_to_node: dict[int, TreeNode] = {}

        self._tree.draggable = True
        self._tree.on_select = self._on_tree_select
        self._tree.on_drop = self._on_drop
        self._tree.on_context_menu = self._on_tree_context_menu

        self._ctx_menu = Menu()
        self._rebuild_context_menu(None)

        self._ops = EntityOperations(
            scene=scene,
            undo_handler=undo_handler,
            dialog_service=dialog_service,
            view=self,
            request_viewport_update=request_viewport_update,
        )

        self.rebuild()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def operations(self) -> EntityOperations:
        return self._ops

    def set_scene(self, scene) -> None:
        self._scene = scene
        self._ops.set_scene(scene)

    def rebuild(self, select_obj: object | None = None) -> None:
        """Rebuild the full tree from the current scene."""
        expanded_uuids = set(self.get_expanded_entity_uuids())

        self._entity_to_node.clear()
        self._tree.clear()

        if self._scene is not None:
            self._build_subtree(parent_node=None, parent_entity=None)
            if expanded_uuids:
                self.set_expanded_entity_uuids(list(expanded_uuids))
            else:
                for root in self._tree.root_nodes:
                    root.expanded = True

        if select_obj is not None:
            self.select_object(select_obj)

    def _build_subtree(self, parent_node: TreeNode | None, parent_entity: Entity | None) -> None:
        """Recursively build tree nodes for entities under parent_entity."""
        if self._scene is None:
            return

        if parent_entity is None:
            entities = [
                e for e in self._scene.entities
                if e.transform is not None and e.transform.parent is None
            ]
        else:
            entities = [
                c.entity for c in parent_entity.transform.children
                if c.entity is not None
            ] if parent_entity.transform else []

        for ent in entities:
            node = self._make_node(ent)
            if parent_node is None:
                self._tree.add_root(node)
            else:
                parent_node.add_node(node)
            self._build_subtree(node, ent)

    def _make_node(self, entity: Entity) -> TreeNode:
        lbl = Label()
        lbl.text = entity.name or "(unnamed)"
        node = TreeNode(lbl)
        node.data = entity
        self._entity_to_node[id(entity)] = node
        return node

    def _rebuild_context_menu(self, entity: Entity | None) -> None:
        if entity is None:
            self._ctx_menu.items = [
                MenuItem("Add entity", on_click=lambda: self._ops.create_entity(None)),
            ]
        else:
            self._ctx_menu.items = [
                MenuItem("Add child entity", on_click=lambda e=entity: self._ops.create_entity(e)),
                MenuItem("Rename...", on_click=lambda e=entity: self._ops.rename_entity(e)),
                MenuItem("Duplicate", on_click=lambda e=entity: self._ops.duplicate_entity(e)),
                MenuItem("Delete", on_click=lambda e=entity: self._ops.delete_entity(e)),
                MenuItem.sep(),
                MenuItem("Add root entity", on_click=lambda: self._ops.create_entity(None)),
            ]

    def _get_parent_node(self, entity: Entity) -> TreeNode | None:
        if entity.transform and entity.transform.parent:
            parent_entity = entity.transform.parent.entity
            if parent_entity:
                return self._entity_to_node.get(id(parent_entity))
        return None

    # ---------- view surface consumed by EntityOperations ----------

    def add_entity(self, entity: Entity) -> None:
        node = self._make_node(entity)
        parent_node = self._get_parent_node(entity)
        if parent_node is None:
            self._tree.add_root(node)
        else:
            parent_node.add_node(node)
            parent_node.expanded = True
        self.select_object(entity)

    def add_entity_hierarchy(self, entity: Entity) -> None:
        parent_node = self._get_parent_node(entity)
        self._add_hierarchy_recursive(parent_node, entity)
        self.select_object(entity)

    def _add_hierarchy_recursive(self, parent_node: TreeNode | None, entity: Entity) -> None:
        node = self._make_node(entity)
        node.expanded = True
        if parent_node is None:
            self._tree.add_root(node)
        else:
            parent_node.add_node(node)

        if entity.transform:
            for child_t in entity.transform.children:
                child = child_t.entity
                if child is not None:
                    self._add_hierarchy_recursive(node, child)

    def remove_entity(self, entity: Entity, select_parent: bool = True) -> None:
        node = self._entity_to_node.get(id(entity))
        if node is None:
            return

        parent_node = self._get_parent_node(entity)

        if parent_node is not None:
            parent_node.remove_node(node)
        else:
            self._tree.remove_root(node)

        self._remove_from_map_recursive(node)

        if select_parent and parent_node is not None and parent_node.data is not None:
            self.select_object(parent_node.data)

    def _remove_from_map_recursive(self, node: TreeNode) -> None:
        if node.data is not None:
            self._entity_to_node.pop(id(node.data), None)
        for child in node.subnodes:
            self._remove_from_map_recursive(child)

    def move_entity(self, entity: Entity, new_parent: Entity | None) -> None:
        node = self._entity_to_node.get(id(entity))
        if node is None:
            return

        old_parent_node = self._get_parent_node_by_traversal(node)

        if old_parent_node is not None:
            old_parent_node.remove_node(node)
        else:
            self._tree.remove_root(node)

        new_parent_node = (
            self._entity_to_node.get(id(new_parent))
            if new_parent is not None else None
        )

        if new_parent_node is not None:
            new_parent_node.add_node(node)
            new_parent_node.expanded = True
        else:
            self._tree.add_root(node)

        self.select_object(entity)

    def _get_parent_node_by_traversal(self, target: TreeNode) -> TreeNode | None:
        for root in self._tree.root_nodes:
            if root is target:
                return None
            found = self._find_parent_recursive(root, target)
            if found is not None:
                return found
        return None

    def _find_parent_recursive(self, node: TreeNode, target: TreeNode) -> TreeNode | None:
        for child in node.subnodes:
            if child is target:
                return node
            found = self._find_parent_recursive(child, target)
            if found is not None:
                return found
        return None

    def update_entity(self, entity: Entity) -> None:
        node = self._entity_to_node.get(id(entity))
        if node is None:
            return
        if isinstance(node.content, Label):
            node.content.text = entity.name or "(unnamed)"
        self._tree._dirty = True

    def select_object(self, obj: object | None) -> None:
        if not isinstance(obj, Entity):
            return
        node = self._entity_to_node.get(id(obj))
        if node is not None:
            self._tree._select_node(node)

    def get_expanded_entity_uuids(self) -> list[str]:
        result: list[str] = []
        for root in self._tree.root_nodes:
            self._collect_expanded_recursive(root, result)
        return result

    def _collect_expanded_recursive(self, node: TreeNode, out: list[str]) -> None:
        if node.data is not None and isinstance(node.data, Entity):
            ent: Entity = node.data
            if node.expanded and ent.uuid:
                out.append(ent.uuid)
        for child in node.subnodes:
            self._collect_expanded_recursive(child, out)

    def set_expanded_entity_uuids(self, uuids: list[str]) -> None:
        uuid_set = set(uuids)
        for root in self._tree.root_nodes:
            self._restore_expanded_recursive(root, uuid_set)

    def _restore_expanded_recursive(self, node: TreeNode, uuids: set[str]) -> None:
        if node.data is not None and isinstance(node.data, Entity):
            ent: Entity = node.data
            if ent.uuid:
                node.expanded = ent.uuid in uuids
        for child in node.subnodes:
            self._restore_expanded_recursive(child, uuids)

    # ------------------------------------------------------------------
    # Tree events
    # ------------------------------------------------------------------

    def _on_tree_select(self, node: TreeNode | None) -> None:
        entity = node.data if node is not None else None
        entity = entity if isinstance(entity, Entity) else None
        self._rebuild_context_menu(entity)
        if node is None:
            self._on_object_selected(None)
        else:
            self._on_object_selected(node.data)

    def _on_tree_context_menu(self, node: TreeNode | None, x: float, y: float) -> None:
        entity = node.data if node is not None else None
        entity = entity if isinstance(entity, Entity) else None
        self._rebuild_context_menu(entity)
        if self._tree._ui is not None:
            self._ctx_menu.show(self._tree._ui, x, y)

    def _on_drop(self, dragged: TreeNode, target: TreeNode | None, position: str) -> None:
        """Handle drag-drop reparenting within the scene tree."""
        entity = dragged.data
        if not isinstance(entity, Entity):
            return

        if target is None or position == "root":
            new_parent_entity = None
        elif position == "inside":
            new_parent_entity = target.data if isinstance(target.data, Entity) else None
        else:
            if isinstance(target.data, Entity):
                parent_t = target.data.transform.parent if target.data.transform else None
                new_parent_entity = parent_t.entity if parent_t else None
            else:
                new_parent_entity = None

        self._ops.reparent_entity(entity, new_parent_entity)
