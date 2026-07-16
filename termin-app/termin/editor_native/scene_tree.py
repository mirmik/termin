"""Native production scene hierarchy surface."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Callable
import weakref

from termin.editor_core.scene_hierarchy_model import (
    SceneHierarchyAction,
    SceneHierarchyController,
    SceneHierarchySnapshot,
)
from termin.gui_native import (
    CollectionItem,
    CommandData,
    CommandModel,
    Document,
    Point,
    Rect,
    Size,
    TreeDropPosition,
    TreeExpansionModel,
    TreeModel,
    WidgetRef,
)
from termin.editor_native.metrics import EDITOR_UI_METRICS


_logger = logging.getLogger(__name__)
_ROW_HEIGHT = 28.0


def _ref(document: Document, reference) -> WidgetRef:
    return reference if isinstance(reference, WidgetRef) else document.ref(reference.handle)


@dataclass
class NativeSceneTree:
    document: Document
    controller: SceneHierarchyController
    root: WidgetRef
    tree_root: WidgetRef
    tree_widget: object
    status_bar: object
    toolbar_model: CommandModel
    tree_model: TreeModel
    expansion_model: TreeExpansionModel
    context_model: CommandModel
    context_menu: object
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    node_ids: dict[int, str] = field(default_factory=dict)
    id_nodes: dict[str, int] = field(default_factory=dict)
    context_stable_id: str | None = None
    _applying_snapshot: bool = False

    def refresh(self) -> None:
        self._apply_snapshot(self.controller.rebuild())

    def select_object(self, obj: object | None) -> None:
        self._apply_snapshot(self.controller.select_object(obj))

    def collapse_all(self) -> None:
        self._apply_snapshot(self.controller.collapse_all())

    def select_node(self, node: int) -> None:
        if self._applying_snapshot:
            return
        self._applying_snapshot = True
        try:
            self.controller.select_id(self.node_ids.get(node))
        finally:
            self._applying_snapshot = False
        self.request_render()

    def set_node_expanded(self, node: int, expanded: bool) -> None:
        if self._applying_snapshot:
            return
        stable_id = self.node_ids.get(node)
        if stable_id is not None:
            self._applying_snapshot = True
            try:
                self.controller.set_expanded(stable_id, expanded)
            finally:
                self._applying_snapshot = False
            self.request_render()

    def show_context_menu(self, node: int, x: float, y: float) -> None:
        self.context_stable_id = self.node_ids.get(node)
        self._show_actions(self.controller.context_actions(self.context_stable_id), x, y)

    def execute_context_action(self, action_id: str) -> None:
        try:
            self.controller.execute_context_action(action_id, self.context_stable_id)
        except Exception:
            _logger.exception("Native scene tree action failed: %s", action_id)
            raise

    def activate_node(self, node: int) -> None:
        stable_id = self.node_ids.get(node)
        if stable_id is not None:
            self.context_stable_id = stable_id
            self.execute_context_action("rename")

    def delete_node(self, node: int) -> None:
        stable_id = self.node_ids.get(node)
        if stable_id is not None:
            self.context_stable_id = stable_id
            self.execute_context_action("delete")

    def drop_node(
        self,
        dragged_node: int,
        target_node: int,
        position: TreeDropPosition,
    ) -> None:
        dragged_id = self.node_ids.get(dragged_node)
        if dragged_id is None:
            _logger.error("Native scene tree drop references unknown dragged node: %s", dragged_node)
            return
        target_id = self.node_ids.get(target_node)
        try:
            self.controller.drop_entity(
                dragged_id,
                target_id,
                self._position_name(position),
            )
        except ValueError as error:
            _logger.warning("Native scene tree rejected drop: %s", error)

    def drop_file(self, path: str, x: float, y: float, _modifiers: int = 0) -> bool:
        extension = Path(path).suffix.casefold()
        if not self.controller.can_drop_project_file(extension):
            return False
        bounds = self.tree_root.bounds
        if not (
            bounds.x <= x < bounds.x + bounds.width
            and bounds.y <= y < bounds.y + bounds.height
        ):
            return False
        target_id, position = self._drop_target(y)
        try:
            self.controller.drop_project_file(path, extension, target_id, position)
        except Exception:
            _logger.exception("Native scene tree external drop failed: %s", path)
            raise
        return True

    def _drop_target(self, y: float) -> tuple[str | None, str]:
        bounds = self.tree_root.bounds
        local_y = y - bounds.y + float(self.tree_widget.scroll_y)
        index = int(local_y // _ROW_HEIGHT)
        if index < 0 or index >= int(self.tree_widget.visible_count):
            return None, "root"
        row = self.tree_widget.visible_row(index)
        stable_id = self.node_ids.get(row.node)
        fraction = (local_y - index * _ROW_HEIGHT) / _ROW_HEIGHT
        if fraction < 0.25:
            return stable_id, "before"
        if fraction > 0.75:
            return stable_id, "after"
        return stable_id, "inside"

    @staticmethod
    def _position_name(position: TreeDropPosition) -> str:
        if position == TreeDropPosition.Before:
            return "before"
        if position == TreeDropPosition.Inside:
            return "inside"
        if position == TreeDropPosition.After:
            return "after"
        return "root"

    def _show_actions(
        self,
        actions: tuple[SceneHierarchyAction, ...],
        x: float,
        y: float,
    ) -> None:
        self.context_model.set_commands(
            [CommandData(action.stable_id, action.label, enabled=action.enabled) for action in actions]
        )
        if not self.context_menu.show(Point(x, y), self.viewport()):
            _logger.error("Native scene tree failed to show context menu")
            return
        self.request_render()

    def _apply_snapshot(self, snapshot: SceneHierarchySnapshot) -> None:
        if self._applying_snapshot:
            return
        self._applying_snapshot = True
        try:
            self.tree_model.clear()
            self.expansion_model.clear()
            self.node_ids.clear()
            self.id_nodes.clear()
            for hierarchy_node in snapshot.nodes:
                item = CollectionItem(
                    hierarchy_node.stable_id,
                    hierarchy_node.name,
                    hierarchy_node.subtitle,
                )
                parent_node = self.id_nodes.get(hierarchy_node.parent_id or "")
                if parent_node is None:
                    tree_node = self.tree_model.append_root(item)
                else:
                    tree_node = self.tree_model.append_child(parent_node, item)
                self.node_ids[tree_node] = hierarchy_node.stable_id
                self.id_nodes[hierarchy_node.stable_id] = tree_node
            for stable_id in snapshot.expanded_ids:
                tree_node = self.id_nodes.get(stable_id)
                if tree_node is not None:
                    self.expansion_model.set_expanded(tree_node, True)
            selected_node = self.id_nodes.get(snapshot.selected_id or "")
            if selected_node is None:
                self.tree_widget.clear_selection()
            else:
                self.tree_widget.select(selected_node, reveal=False)
            self.status_bar.text = snapshot.status
        finally:
            self._applying_snapshot = False
        self.request_render()


def build_native_scene_tree(
    document: Document,
    controller: SceneHierarchyController,
    *,
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
) -> NativeSceneTree:
    root = document.create_vstack("native-scene-tree")
    root.stable_id = "editor.scene-tree"
    root.preferred_size = Size(420.0, 300.0)
    root.set_layout_padding(EDITOR_UI_METRICS.collection_insets)
    root.set_layout_spacing(EDITOR_UI_METRICS.spacing)

    toolbar_model = CommandModel()
    toolbar_model.set_commands(
        [
            CommandData("add-root", "Add"),
            CommandData("collapse-all", "Collapse"),
            CommandData("refresh", "Refresh", shortcut="F5"),
        ]
    )
    toolbar = document.create_tool_bar(toolbar_model)
    root.add_fixed_child(_ref(document, toolbar), EDITOR_UI_METRICS.toolbar)

    tree_model = TreeModel()
    expansion_model = TreeExpansionModel()
    tree = document.create_tree_widget(tree_model, expansion_model)
    tree.draggable = True
    tree.set_row_height(_ROW_HEIGHT)
    tree_root = _ref(document, tree)
    root.add_stretch_child(tree_root)

    status = document.create_status_bar("Scene entities: 0")
    root.add_fixed_child(_ref(document, status), EDITOR_UI_METRICS.status_row)
    context_model = CommandModel()
    context_menu = document.create_menu(context_model)

    scene_tree = NativeSceneTree(
        document=document,
        controller=controller,
        root=root,
        tree_root=tree_root,
        tree_widget=tree,
        status_bar=status,
        toolbar_model=toolbar_model,
        tree_model=tree_model,
        expansion_model=expansion_model,
        context_model=context_model,
        context_menu=context_menu,
        viewport=viewport,
        request_render=request_render,
    )
    weak_tree = weakref.ref(scene_tree)

    def current() -> NativeSceneTree | None:
        return weak_tree()

    def on_toolbar(_index: int, _command_id: int, command) -> None:
        owner = current()
        if owner is None:
            return
        if command.stable_id == "add-root":
            owner.controller.execute_context_action("create-root", None)
        elif command.stable_id == "collapse-all":
            owner.collapse_all()
        elif command.stable_id == "refresh":
            owner.refresh()

    def on_selection(node: int) -> None:
        owner = current()
        if owner is not None:
            owner.select_node(node)

    def on_expansion(node: int, expanded: bool) -> None:
        owner = current()
        if owner is not None:
            owner.set_node_expanded(node, expanded)

    def on_activated(node: int, _item) -> None:
        owner = current()
        if owner is not None:
            owner.activate_node(node)

    def on_delete(node: int, _item) -> None:
        owner = current()
        if owner is not None:
            owner.delete_node(node)

    def on_context(node: int, x: float, y: float) -> None:
        owner = current()
        if owner is not None:
            owner.show_context_menu(node, x, y)

    def on_drop(dragged: int, target: int, position: TreeDropPosition) -> None:
        owner = current()
        if owner is not None:
            owner.drop_node(dragged, target, position)

    def on_context_action(_index: int, _command_id: int, command) -> None:
        owner = current()
        if owner is not None:
            owner.execute_context_action(command.stable_id)

    toolbar.connect_activated(on_toolbar)
    tree.connect_selection_changed(on_selection)
    tree.connect_expansion_changed(on_expansion)
    tree.connect_activated(on_activated)
    tree.connect_delete_requested(on_delete)
    tree.connect_context_menu_requested(on_context)
    tree.connect_drop_requested(on_drop)
    context_menu.connect_activated(on_context_action)
    def on_snapshot_changed(snapshot: SceneHierarchySnapshot) -> None:
        owner = current()
        if owner is not None:
            owner._apply_snapshot(snapshot)

    controller.set_snapshot_changed_handler(on_snapshot_changed)
    scene_tree._apply_snapshot(controller.snapshot())
    return scene_tree


__all__ = ["NativeSceneTree", "build_native_scene_tree"]
