"""Native projection of the shared viewport-list controller."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
import weakref

from termin.editor_core.viewport_list_model import (
    ViewportListController,
    ViewportListNode,
    ViewportListSnapshot,
    ViewportNodeKind,
)
from termin.gui_native import (
    CollectionItem,
    CommandData,
    CommandModel,
    TcDocument,
    Point,
    Rect,
    Size,
    TreeExpansionModel,
    TreeModel,
    WidgetRef,
)
from termin.editor_native.metrics import EDITOR_UI_METRICS


InputDialogHandler = Callable[[str, str, str, Callable[[str | None], None]], None]


@dataclass
class NativeViewportList:
    document: TcDocument
    controller: ViewportListController
    root: WidgetRef
    tree_widget: object
    tree_model: TreeModel
    expansion_model: TreeExpansionModel
    status_bar: object
    context_model: CommandModel
    context_menu: object
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    show_input: InputDialogHandler | None = None
    node_ids: dict[int, str] = field(default_factory=dict)
    id_nodes: dict[str, int] = field(default_factory=dict)
    context_id: str | None = None
    applying_snapshot: bool = False

    def apply_snapshot(self, snapshot: ViewportListSnapshot) -> None:
        if self.applying_snapshot:
            return
        self.applying_snapshot = True
        try:
            self.tree_model.clear()
            self.expansion_model.clear()
            self.node_ids.clear()
            self.id_nodes.clear()
            for root in snapshot.roots:
                self._append_node(root, None)
            selected = self.id_nodes.get(snapshot.selected_id or "")
            if selected is None:
                self.tree_widget.clear_selection()
            else:
                self.tree_widget.select(selected, reveal=True)
            display_count = sum(root.kind == ViewportNodeKind.DISPLAY for root in snapshot.roots)
            viewport_count = sum(len(root.children) for root in snapshot.roots if root.kind == ViewportNodeKind.DISPLAY)
            target_count = sum(
                len(root.children) for root in snapshot.roots if root.kind == ViewportNodeKind.RENDER_TARGET_GROUP
            )
            self.status_bar.text = f"Displays: {display_count} | Viewports: {viewport_count} | Targets: {target_count}"
        finally:
            self.applying_snapshot = False
        self.request_render()

    def _append_node(self, source: ViewportListNode, parent: int | None) -> None:
        item = CollectionItem(source.stable_id, source.label)
        node = self.tree_model.append_root(item) if parent is None else self.tree_model.append_child(parent, item)
        self.node_ids[node] = source.stable_id
        self.id_nodes[source.stable_id] = node
        if source.children:
            self.expansion_model.set_expanded(node, True)
        for child in source.children:
            self._append_node(child, node)

    def select_node(self, node: int) -> None:
        if not self.applying_snapshot:
            self.controller.select(self.node_ids.get(node))

    def show_context_menu(self, node: int, x: float, y: float) -> None:
        self.context_id = self.node_ids.get(node)
        source = self.controller.snapshot.find(self.context_id or "")
        commands = [
            CommandData(
                "add-display",
                "Add Display",
            )
        ]
        if source is not None:
            if source.kind == ViewportNodeKind.DISPLAY:
                commands.extend(
                    [
                        CommandData("add-viewport", "Add Viewport"),
                        CommandData("remove", "Remove Display"),
                    ]
                )
            elif source.kind == ViewportNodeKind.VIEWPORT:
                commands.extend([CommandData("rename", "Rename..."), CommandData("remove", "Remove Viewport")])
            elif source.kind == ViewportNodeKind.RENDER_TARGET:
                commands.extend(
                    [
                        CommandData("rename", "Rename..."),
                        CommandData("remove", "Remove Render Target"),
                    ]
                )
            elif source.kind == ViewportNodeKind.RENDER_TARGET_GROUP:
                commands.extend(
                    [
                        CommandData("add-rt", "Add Render Target"),
                        CommandData("add-xr-rt", "Add XR Stereo Target"),
                    ]
                )
        self.context_model.set_commands(commands)
        if not self.context_menu.show(Point(x, y), self.viewport()):
            raise RuntimeError("failed to show native viewport-list context menu")
        self.request_render()

    def execute_action(self, action: str) -> None:
        if action == "add-display":
            self.controller.request_add_display()
        elif action == "add-viewport":
            source = self.controller.snapshot.find(self.context_id or "")
            self.controller.request_add_viewport(None if source is None else source.value)
        elif action == "add-rt":
            self.controller.request_add_render_target()
        elif action == "add-xr-rt":
            self.controller.request_add_render_target("xr_stereo")
        elif action == "remove" and self.context_id is not None:
            self.controller.request_remove(self.context_id)
        elif action == "rename":
            self._show_rename()

    def _show_rename(self) -> None:
        source = self.controller.snapshot.find(self.context_id or "")
        if source is None or source.kind not in (
            ViewportNodeKind.VIEWPORT,
            ViewportNodeKind.RENDER_TARGET,
        ):
            return
        if self.show_input is None:
            raise RuntimeError("native viewport list has no input dialog service")
        stable_id = source.stable_id
        self.show_input(
            "Rename Viewport" if source.kind == ViewportNodeKind.VIEWPORT else "Rename Render Target",
            "Name:",
            source.value.name or "",
            lambda value: self.controller.rename(stable_id, value) if value is not None else None,
        )


def build_native_viewport_list(
    document: TcDocument,
    controller: ViewportListController,
    *,
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
    show_input: InputDialogHandler | None = None,
) -> NativeViewportList:
    root = document.create_vstack("native-viewport-list")
    root.stable_id = "editor.viewport-list"
    root.preferred_size = Size(420.0, 300.0)
    root.set_layout_padding(EDITOR_UI_METRICS.collection_insets)
    root.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    toolbar_model = CommandModel()
    toolbar_model.set_commands(
        [
            CommandData("add-display", "+ Display"),
            CommandData("add-viewport", "+ Viewport"),
            CommandData("add-rt", "+ RT"),
            CommandData("add-xr-rt", "+ XR RT"),
        ]
    )
    toolbar = document.create_tool_bar(toolbar_model)
    root.add_fixed_child(document.ref(toolbar.handle), EDITOR_UI_METRICS.toolbar)
    tree_model = TreeModel()
    expansion_model = TreeExpansionModel()
    tree = document.create_tree_widget(tree_model, expansion_model)
    tree.set_row_height(26.0)
    root.add_stretch_child(document.ref(tree.handle))
    status = document.create_status_bar()
    root.add_fixed_child(document.ref(status.handle), EDITOR_UI_METRICS.status_row)
    context_model = CommandModel()
    context_menu = document.create_menu(context_model)
    result = NativeViewportList(
        document,
        controller,
        root,
        tree,
        tree_model,
        expansion_model,
        status,
        context_model,
        context_menu,
        viewport,
        request_render,
        show_input,
    )
    weak_result = weakref.ref(result)

    def owner() -> NativeViewportList | None:
        return weak_result()

    def toolbar_action(_index: int, _command_id: int, command) -> None:
        current = owner()
        if current is not None:
            current.execute_action(command.stable_id)

    def selection_changed(node: int) -> None:
        current = owner()
        if current is not None:
            current.select_node(node)

    def context_requested(node: int, x: float, y: float) -> None:
        current = owner()
        if current is not None:
            current.show_context_menu(node, x, y)

    def context_action(_index: int, _command_id: int, command) -> None:
        current = owner()
        if current is not None:
            current.execute_action(command.stable_id)

    toolbar.connect_activated(toolbar_action)
    tree.connect_selection_changed(selection_changed)
    tree.connect_context_menu_requested(context_requested)
    context_menu.connect_activated(context_action)
    controller.snapshot_changed.connect(result.apply_snapshot)
    result.apply_snapshot(controller.snapshot)
    return result


__all__ = ["NativeViewportList", "build_native_viewport_list"]
