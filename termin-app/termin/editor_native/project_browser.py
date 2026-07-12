"""Native project directory tree and virtualized file collection surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
import weakref

from termin.editor_core.project_browser_model import (
    ProjectBrowserAction,
    ProjectBrowserController,
    ProjectBrowserSnapshot,
)
from termin.gui_native import (
    CollectionItem,
    CollectionModel,
    CommandData,
    CommandModel,
    Document,
    Point,
    Rect,
    Size,
    TreeExpansionModel,
    TreeModel,
    WidgetRef,
)
from termin.editor_native.metrics import EDITOR_UI_METRICS


def _ref(document: Document, reference) -> WidgetRef:
    return reference if isinstance(reference, WidgetRef) else document.ref(reference.handle)


@dataclass
class NativeProjectBrowser:
    document: Document
    controller: ProjectBrowserController
    root: WidgetRef
    content_splitter: object
    tree_widget: object
    file_grid: object
    breadcrumb: object
    status_bar: object
    toolbar_model: CommandModel
    tree_model: TreeModel
    expansion_model: TreeExpansionModel
    file_model: CollectionModel
    context_model: CommandModel
    context_menu: object
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    file_drop_handler: Callable[[str, float, float, int], bool] | None = None
    node_paths: dict[int, Path] = field(default_factory=dict)
    path_nodes: dict[Path, int] = field(default_factory=dict)
    placeholder_nodes: set[int] = field(default_factory=set)
    context_index: int = -1
    context_directory: Path | None = None

    def set_root(self, path: str | Path) -> None:
        snapshot = self.controller.set_root(path)
        self._rebuild_tree()
        self._apply_snapshot(snapshot)

    def refresh(self) -> None:
        snapshot = self.controller.refresh()
        self._rebuild_tree()
        self._apply_snapshot(snapshot)

    def navigate(self, path: str | Path) -> None:
        snapshot = self.controller.navigate(path)
        node = self._ensure_tree_path(Path(path).resolve())
        if node is not None:
            self.tree_widget.select(node)
        self._apply_snapshot(snapshot)

    def select_file(self, index: int) -> None:
        self.controller.select_entry(index)

    def activate_file(self, index: int) -> None:
        before = self.controller.selected_directory
        snapshot = self.controller.activate_entry(index)
        if snapshot.selected_directory != before and snapshot.selected_directory is not None:
            node = self._ensure_tree_path(snapshot.selected_directory)
            if node is not None:
                self.tree_widget.select(node)
        self._apply_snapshot(snapshot)

    def expand_directory(self, node: int, expanded: bool) -> None:
        if not expanded:
            return
        path = self.node_paths.get(node)
        if path is None:
            return
        self._load_tree_children(node, path)
        self.request_render()

    def select_directory_node(self, node: int) -> None:
        path = self.node_paths.get(node)
        if path is not None and path != self.controller.selected_directory:
            self._apply_snapshot(self.controller.navigate(path))

    def show_file_context(self, index: int, x: float, y: float) -> None:
        self.context_index = index
        self.context_directory = None
        self._show_actions(self.controller.context_actions(index), x, y)

    def show_directory_context(self, node: int, x: float, y: float) -> None:
        path = self.node_paths.get(node)
        if path is None:
            return
        self.context_index = -1
        self.context_directory = path
        self._show_actions(self.controller.directory_context_actions(path), x, y)

    def execute_context_action(self, action_id: str) -> None:
        if self.context_directory is not None:
            snapshot = self.controller.execute_directory_context_action(
                action_id,
                self.context_directory,
            )
        else:
            snapshot = self.controller.execute_context_action(action_id, self.context_index)
        if action_id == "refresh":
            self._rebuild_tree()
        if snapshot.selected_directory is not None:
            node = self._ensure_tree_path(snapshot.selected_directory)
            if node is not None:
                self.tree_widget.select(node)
        self._apply_snapshot(snapshot)

    def _show_actions(
        self,
        actions: tuple[ProjectBrowserAction, ...],
        x: float,
        y: float,
    ) -> None:
        self.context_model.set_commands(
            [CommandData(action.stable_id, action.label, enabled=action.enabled) for action in actions]
        )
        self.context_menu.show(Point(x, y), self.viewport())
        self.request_render()

    def _apply_snapshot(self, snapshot: ProjectBrowserSnapshot) -> None:
        self.file_model.set_items(
            [
                CollectionItem(
                    entry.stable_id,
                    entry.name,
                    entry.subtitle,
                )
                for entry in snapshot.entries
            ]
        )
        self.breadcrumb.text = " > ".join(label for label, _path in snapshot.breadcrumb)
        self.status_bar.text = snapshot.status
        self.request_render()

    def _rebuild_tree(self) -> None:
        self.tree_model.clear()
        self.expansion_model.clear()
        self.node_paths.clear()
        self.path_nodes.clear()
        self.placeholder_nodes.clear()
        root = self.controller.root_path
        if root is None:
            return
        root_node = self.tree_model.append_root(
            CollectionItem(str(root), root.name or str(root), "Project")
        )
        self._remember_node(root_node, root)
        self._load_tree_children(root_node, root)
        self.expansion_model.set_expanded(root_node, True)
        self.tree_widget.select(root_node)

    def _remember_node(self, node: int, path: Path) -> None:
        self.node_paths[node] = path
        self.path_nodes[path] = node

    def _load_tree_children(self, node: int, path: Path) -> None:
        children = list(self.tree_model.children(node))
        placeholders = [child for child in children if child in self.placeholder_nodes]
        for placeholder in placeholders:
            self.tree_model.erase(placeholder)
            self.placeholder_nodes.discard(placeholder)
        if any(child in self.node_paths for child in self.tree_model.children(node)):
            return
        for directory in self.controller.directory_children(path):
            child = self.tree_model.append_child(
                node,
                CollectionItem(str(directory), directory.name, "Folder"),
            )
            self._remember_node(child, directory)
            if self.controller.has_directory_children(directory):
                placeholder = self.tree_model.append_child(
                    child,
                    CollectionItem(f"{directory}::placeholder", "Loading...", enabled=False),
                )
                self.placeholder_nodes.add(placeholder)

    def _ensure_tree_path(self, path: Path) -> int | None:
        existing = self.path_nodes.get(path)
        if existing is not None:
            return existing
        parent = path.parent
        parent_node = self._ensure_tree_path(parent) if parent != path else None
        if parent_node is None:
            return None
        self._load_tree_children(parent_node, parent)
        return self.path_nodes.get(path)


def build_native_project_browser(
    document: Document,
    controller: ProjectBrowserController,
    *,
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
    file_drop_handler: Callable[[str, float, float, int], bool] | None = None,
) -> NativeProjectBrowser:
    root = document.create_vstack("native-project-browser")
    root.stable_id = "editor.project-browser"
    root.preferred_size = Size(420.0, 626.0)
    root.set_layout_padding(EDITOR_UI_METRICS.collection_insets)
    root.set_layout_spacing(EDITOR_UI_METRICS.spacing)

    toolbar_model = CommandModel()
    toolbar_model.set_commands(
        [
            CommandData("go-up", "Up"),
            CommandData("go-root", "Root"),
            CommandData("refresh", "Refresh", shortcut="F5"),
        ]
    )
    toolbar = document.create_tool_bar(toolbar_model)
    root.add_fixed_child(_ref(document, toolbar), EDITOR_UI_METRICS.toolbar)
    breadcrumb = document.create_status_bar("No project")
    root.add_fixed_child(_ref(document, breadcrumb), EDITOR_UI_METRICS.status_row)

    main = document.create_splitter(True, "project-browser-content-splitter")
    main.widget.stable_id = "editor.project-browser.content-splitter"
    # The legacy directory tree starts near 170 px in a 2048 px-wide project panel.
    main.set_split_fraction(0.085)
    main.set_min_extents(120.0, 240.0)
    tree_model = TreeModel()
    expansion_model = TreeExpansionModel()
    tree = document.create_tree_widget(tree_model, expansion_model)
    main.set_first(_ref(document, tree))
    file_model = CollectionModel()
    grid = document.create_file_grid_widget(file_model)
    main.set_second(_ref(document, grid))
    root.add_stretch_child(main.widget)
    status = document.create_status_bar("No project is open")
    root.add_fixed_child(_ref(document, status), EDITOR_UI_METRICS.status_row)

    context_model = CommandModel()
    context_menu = document.create_menu(context_model)
    browser = NativeProjectBrowser(
        document=document,
        controller=controller,
        root=root,
        content_splitter=main,
        tree_widget=tree,
        file_grid=grid,
        breadcrumb=breadcrumb,
        status_bar=status,
        toolbar_model=toolbar_model,
        tree_model=tree_model,
        expansion_model=expansion_model,
        file_model=file_model,
        context_model=context_model,
        context_menu=context_menu,
        viewport=viewport,
        request_render=request_render,
        file_drop_handler=file_drop_handler,
    )
    weak_browser = weakref.ref(browser)

    def current() -> NativeProjectBrowser | None:
        return weak_browser()

    def refresh_after_mutation() -> None:
        owner = current()
        if owner is not None:
            owner.refresh()

    def navigate_after_mutation(path: Path) -> None:
        owner = current()
        if owner is not None:
            owner.navigate(path)

    controller.set_mutation_refresh(refresh_after_mutation)
    controller.set_mutation_navigation(navigate_after_mutation)

    def on_toolbar(_index: int, _command_id: int, command) -> None:
        owner = current()
        if owner is None:
            return
        if command.stable_id == "go-up":
            selected = owner.controller.selected_directory
            root_path = owner.controller.root_path
            if selected is not None and root_path is not None and selected != root_path:
                owner.navigate(selected.parent)
        elif command.stable_id == "go-root":
            root_path = owner.controller.root_path
            if root_path is not None:
                owner.navigate(root_path)
        elif command.stable_id == "refresh":
            owner.refresh()

    def on_selection(selected: list[int]) -> None:
        owner = current()
        if owner is not None:
            owner.select_file(selected[-1] if selected else -1)

    def on_activation(index: int, _item) -> None:
        owner = current()
        if owner is not None:
            owner.activate_file(index)

    def on_context(index: int, x: float, y: float) -> None:
        owner = current()
        if owner is not None:
            owner.show_file_context(index, x, y)

    def on_delete(index: int, _item) -> None:
        owner = current()
        if owner is not None:
            owner.controller.execute_context_action("delete", index)

    def on_drag(index: int, x: float, y: float, modifiers: int) -> None:
        owner = current()
        if owner is None or owner.file_drop_handler is None:
            return
        payload = owner.controller.drag_payload(index)
        if payload is not None:
            owner.file_drop_handler(payload["path"], x, y, modifiers)

    def on_tree_selection(node: int) -> None:
        owner = current()
        if owner is not None:
            owner.select_directory_node(node)

    def on_tree_expansion(node: int, expanded: bool) -> None:
        owner = current()
        if owner is not None:
            owner.expand_directory(node, expanded)

    def on_tree_context(node: int, x: float, y: float) -> None:
        owner = current()
        if owner is not None:
            owner.show_directory_context(node, x, y)

    def on_context_action(_index: int, _command_id: int, command) -> None:
        owner = current()
        if owner is not None:
            owner.execute_context_action(command.stable_id)

    toolbar.connect_activated(on_toolbar)
    grid.connect_selection_changed(on_selection)
    grid.connect_activated(on_activation)
    grid.connect_context_menu_requested(on_context)
    grid.connect_delete_requested(on_delete)
    grid.connect_drag_requested(on_drag)
    tree.connect_selection_changed(on_tree_selection)
    tree.connect_expansion_changed(on_tree_expansion)
    tree.connect_context_menu_requested(on_tree_context)
    context_menu.connect_activated(on_context_action)
    return browser


__all__ = ["NativeProjectBrowser", "build_native_project_browser"]
