"""Scene tree controller for tcgui editor."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from tcbase import log
from tcgui.widgets.tree import TreeNode, TreeWidget
from tcgui.widgets.label import Label
from tcgui.widgets.menu import Menu, MenuItem
from tcgui.widgets.message_box import MessageBox

from termin.editor.undo_stack import UndoCommand
from termin.editor.editor_commands import (
    AddEntityCommand,
    DeleteEntityCommand,
    RenameEntityCommand,
    ReparentEntityCommand,
    DuplicateEntityCommand,
)
from termin.visualization.core.entity import Entity
from termin.kinematic.transform import Transform3


class SceneTreeControllerTcgui:
    """Manages tcgui TreeWidget for the scene.

    Builds a tree from the scene hierarchy and handles:
    - Selection propagation via on_object_selected
    - Context menu (Add/Rename/Duplicate/Delete)
    - Drag-drop reparenting
    """

    def __init__(
        self,
        tree_widget: TreeWidget,
        scene,
        undo_handler: Callable[[UndoCommand, bool], None],
        on_object_selected: Callable[[object | None], None],
        request_viewport_update: Optional[Callable[[], None]] = None,
    ) -> None:
        self._tree = tree_widget
        self._scene = scene
        self._undo_handler = undo_handler
        self._on_object_selected = on_object_selected
        self._request_viewport_update = request_viewport_update

        # Map id(entity) → TreeNode for fast lookup
        self._entity_to_node: dict[int, TreeNode] = {}

        # Rename callback — set by EditorWindowTcgui to show InputDialog
        self._on_rename_requested: Callable[[Entity], None] | None = None

        self._tree.draggable = True
        self._tree.on_select = self._on_tree_select
        self._tree.on_drop = self._on_drop
        self._tree.on_context_menu = self._on_tree_context_menu

        # Reusable context menu; shown manually from right-click callback.
        self._ctx_menu = Menu()
        self._rebuild_context_menu(None)

        self.rebuild()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_scene(self, scene) -> None:
        self._scene = scene

    def rebuild(self, select_obj: object | None = None) -> None:
        """Rebuild the full tree from the current scene."""
        self._entity_to_node.clear()
        self._tree.clear()

        if self._scene is not None:
            self._build_subtree(parent_node=None, parent_entity=None)

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
            node.expanded = True
            self._build_subtree(node, ent)

    def _make_node(self, entity: Entity) -> TreeNode:
        """Create a TreeNode for an entity."""
        lbl = Label()
        lbl.text = entity.name or "(unnamed)"
        node = TreeNode(lbl)
        node.data = entity
        self._entity_to_node[id(entity)] = node
        return node

    def _rebuild_context_menu(self, entity: Entity | None) -> None:
        """Rebuild context menu items for the currently selected entity."""
        if entity is None:
            self._ctx_menu.items = [
                MenuItem("Add entity", on_click=self._create_root_entity),
            ]
        else:
            self._ctx_menu.items = [
                MenuItem("Add child entity", on_click=lambda e=entity: self._create_entity(e)),
                MenuItem("Rename...", on_click=lambda e=entity: self._rename_entity(e)),
                MenuItem("Duplicate", on_click=lambda e=entity: self._duplicate_entity(e)),
                MenuItem("Delete", on_click=lambda e=entity: self._delete_entity(e)),
                MenuItem.sep(),
                MenuItem("Add root entity", on_click=self._create_root_entity),
            ]

    def _get_parent_node(self, entity: Entity) -> TreeNode | None:
        """Get the TreeNode of entity's parent, or None if root."""
        if entity.transform and entity.transform.parent:
            parent_entity = entity.transform.parent.entity
            if parent_entity:
                return self._entity_to_node.get(id(parent_entity))
        return None

    def add_entity(self, entity: Entity) -> None:
        """Add a single entity to the tree and select it."""
        node = self._make_node(entity)
        parent_node = self._get_parent_node(entity)
        if parent_node is None:
            self._tree.add_root(node)
        else:
            parent_node.add_node(node)
            parent_node.expanded = True
        self.select_object(entity)

    def add_entity_hierarchy(self, entity: Entity) -> None:
        """Add entity and all its children to the tree."""
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
        """Remove entity node (and its subtree) from the tree."""
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
        """Move entity node to a new parent node."""
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
        """Find parent node by traversing root nodes."""
        for root in self._tree.root_nodes:
            if root is target:
                return None  # It's a root
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
        """Update display name of entity's node."""
        node = self._entity_to_node.get(id(entity))
        if node is None:
            return
        if isinstance(node.content, Label):
            node.content.text = entity.name or "(unnamed)"
        self._tree._dirty = True

    def select_object(self, obj: object | None) -> None:
        """Select the tree node for obj."""
        if not isinstance(obj, Entity):
            return
        node = self._entity_to_node.get(id(obj))
        if node is not None:
            self._tree._select_node(node)

    def get_expanded_entity_uuids(self) -> list[str]:
        """Collect UUIDs of expanded nodes."""
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
        """Restore expanded state from saved UUIDs."""
        uuid_set = set(uuids)
        for root in self._tree.root_nodes:
            self._restore_expanded_recursive(root, uuid_set)

    def _restore_expanded_recursive(self, node: TreeNode, uuids: set[str]) -> None:
        if node.data is not None and isinstance(node.data, Entity):
            ent: Entity = node.data
            if ent.uuid and ent.uuid in uuids:
                node.expanded = True
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
            # "above" or "below" — reparent to target's parent
            if isinstance(target.data, Entity):
                parent_t = target.data.transform.parent if target.data.transform else None
                new_parent_entity = parent_t.entity if parent_t else None
            else:
                new_parent_entity = None

        old_parent_t = entity.transform.parent if entity.transform else None
        new_parent_t = new_parent_entity.transform if new_parent_entity else None

        if old_parent_t is new_parent_t:
            return

        cmd = ReparentEntityCommand(entity, old_parent_t, new_parent_t)
        self._undo_handler(cmd, False)

        self.move_entity(entity, new_parent_entity)

        if self._request_viewport_update is not None:
            self._request_viewport_update()

    # ------------------------------------------------------------------
    # Context menu entity operations
    # ------------------------------------------------------------------

    def _create_root_entity(self) -> None:
        self._create_entity(None)

    def _create_entity(self, parent_entity: Entity | None) -> None:
        if self._scene is None:
            return

        parent_transform: Transform3 | None = None
        if isinstance(parent_entity, Entity):
            parent_transform = parent_entity.transform

        existing = {e.name for e in self._scene.entities}
        base = "entity"
        i = 1
        while f"{base}{i}" in existing:
            i += 1
        name = f"{base}{i}"

        ent = self._scene.create_entity(name)
        if parent_transform is not None:
            ent.transform.set_parent(parent_transform)

        cmd = AddEntityCommand(self._scene, ent, parent_transform=None)
        self._undo_handler(cmd, False)

        self.add_entity(ent)

        if self._request_viewport_update is not None:
            self._request_viewport_update()

    def _rename_entity(self, entity: Entity) -> None:
        if self._on_rename_requested is not None:
            self._on_rename_requested(entity)

    def _duplicate_entity(self, entity: Entity) -> None:
        if not isinstance(entity, Entity) or self._scene is None:
            return

        cmd = DuplicateEntityCommand(self._scene, entity)
        self._undo_handler(cmd, False)

        copy = cmd.entity
        if copy is not None:
            self.add_entity_hierarchy(copy)

        if self._request_viewport_update is not None:
            self._request_viewport_update()

    def _delete_entity(self, entity: Entity) -> None:
        if not isinstance(entity, Entity):
            return

        children = list(entity.transform.children) if entity.transform else []
        if not children:
            self._delete_entity_with_children(entity)
            return

        ui = self._tree._ui
        if ui is None:
            self._delete_entity_with_children(entity)
            return

        MessageBox.question(
            ui,
            title="Delete Entity",
            message=f"Entity '{entity.name}' has {len(children)} child(ren).",
            buttons=["Delete With Children", "Delete Only This", "Cancel"],
            on_result=lambda button, ent=entity: self._on_delete_choice(ent, button),
        )

    def _on_delete_choice(self, entity: Entity, button: str) -> None:
        if button == "Delete With Children":
            self._delete_entity_with_children(entity)
            return
        if button == "Delete Only This":
            self._delete_entity_only_this(entity)

    def _delete_entity_with_children(self, entity: Entity) -> None:
        parent_ent = None
        if entity.transform and entity.transform.parent:
            parent_ent = entity.transform.parent.entity

        self._delete_entity_recursive(entity)
        self.remove_entity(entity, select_parent=False)

        if parent_ent is not None:
            self.select_object(parent_ent)

        if self._request_viewport_update is not None:
            self._request_viewport_update()

    def _delete_entity_only_this(self, entity: Entity) -> None:
        parent_transform = entity.transform.parent if entity.transform else None
        parent_entity = parent_transform.entity if parent_transform else None

        if entity.transform is not None:
            for child_transform in list(entity.transform.children):
                child_entity = child_transform.entity
                if child_entity is None:
                    continue
                cmd = ReparentEntityCommand(child_entity, entity.transform, parent_transform)
                self._undo_handler(cmd, False)
                self.move_entity(child_entity, parent_entity)

        cmd = DeleteEntityCommand(self._scene, entity)
        self._undo_handler(cmd, False)
        self.remove_entity(entity, select_parent=False)

        if parent_entity is not None:
            self.select_object(parent_entity)

        if self._request_viewport_update is not None:
            self._request_viewport_update()

    def _delete_entity_recursive(self, entity: Entity) -> None:
        if entity.transform:
            for child_t in list(entity.transform.children):
                child = child_t.entity
                if child is not None:
                    self._delete_entity_recursive(child)
        cmd = DeleteEntityCommand(self._scene, entity)
        self._undo_handler(cmd, False)

    # ------------------------------------------------------------------
    # Prefab / GLB drops (called from project browser)
    # ------------------------------------------------------------------

    def handle_prefab_drop(self, prefab_path: str, parent_entity: Entity | None) -> None:
        from termin.visualization.core.resources import ResourceManager

        rm = ResourceManager.instance()
        prefab_name = Path(prefab_path).stem
        parent_transform = parent_entity.transform if parent_entity else None

        entity = rm.instantiate_prefab(prefab_name, parent=parent_transform)
        if entity is None:
            log.error(f"Failed to instantiate prefab: {prefab_name}")
            return

        cmd = AddEntityCommand(self._scene, entity, parent_transform=None)
        self._undo_handler(cmd, False)
        self.add_entity_hierarchy(entity)

        if self._request_viewport_update is not None:
            self._request_viewport_update()

    def handle_glb_drop(self, glb_path: str, parent_entity: Entity | None) -> None:
        from termin.loaders.glb_instantiator import instantiate_glb
        from termin.visualization.core.resources import ResourceManager

        rm = ResourceManager.instance()
        glb_name = Path(glb_path).stem
        glb_asset = rm.get_glb_asset(glb_name)

        if glb_asset is None:
            log.error(f"GLBAsset '{glb_name}' not found")
            return

        try:
            result = instantiate_glb(glb_asset, scene=self._scene)
        except Exception as e:
            log.error(f"Failed to load GLB: {e}")
            return

        entity = result.entity
        parent_transform = parent_entity.transform if parent_entity else None
        cmd = AddEntityCommand(self._scene, entity, parent_transform=parent_transform)
        self._undo_handler(cmd, False)
        self.add_entity_hierarchy(entity)

        if self._request_viewport_update is not None:
            self._request_viewport_update()
