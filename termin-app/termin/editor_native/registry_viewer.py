"""Native registry viewer dialog backed by a toolkit-neutral collection controller."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable
import weakref

from termin.editor_core.registry_viewer_model import (
    RegistryCatalogController,
    RegistryCollectionController,
    RegistryColumn,
    RegistrySnapshot,
)
from termin.gui_native import (
    CollectionItem,
    CommandData,
    CommandModel,
    DialogAction,
    TcDocument,
    EdgeInsets,
    Point,
    Rect,
    RichTextModel,
    Size,
    TableColumn,
    TableColumnModel,
    TableColumnPolicy,
    TableModel,
    TableRowData,
    TreeExpansionModel,
    TreeModel,
    WidgetRef,
)


_logger = logging.getLogger(__name__)


def _ref(document: TcDocument, reference) -> WidgetRef:
    return reference if isinstance(reference, WidgetRef) else document.ref(reference.handle)


@dataclass
class NativeRegistryViewer:
    document: TcDocument
    controller: RegistryCollectionController | RegistryCatalogController
    dialog: object
    root: WidgetRef
    filter_input: object
    table_widget: object
    table_root: WidgetRef
    tree_widget: object
    tree_root: WidgetRef
    details: object
    details_model: RichTextModel
    status_bar: object
    table_model: TableModel
    column_model: TableColumnModel
    tree_model: TreeModel
    tree_expansion_model: TreeExpansionModel
    toolbar_model: CommandModel
    context_model: CommandModel
    context_menu: object
    page_selector: object | None
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    context_index: int = -1
    tree_node_indices: dict[int, int] | None = None

    def show(self) -> bool:
        if self.dialog.open:
            return False
        if not self.refresh():
            return False
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def refresh(self) -> bool:
        try:
            snapshot = self.controller.refresh()
        except Exception as error:
            self.status_bar.text = f"Registry refresh failed: {error}"
            self.request_render()
            return False
        self._apply_snapshot(snapshot)
        return True

    def set_filter(self, text: str) -> None:
        self._apply_snapshot(self.controller.set_filter(text))

    def select_page(self, index: int) -> None:
        if not isinstance(self.controller, RegistryCatalogController):
            return
        try:
            snapshot = self.controller.select_page(index)
        except Exception as error:
            self.status_bar.text = f"Registry page refresh failed: {error}"
            _logger.exception("Native registry page refresh failed")
            self.request_render()
            return
        self._set_columns(self.controller.current_page.columns)
        if self.filter_input.text != snapshot.filter_text:
            self.filter_input.text = snapshot.filter_text
        self._apply_snapshot(snapshot)

    def select(self, index: int) -> None:
        self._apply_details(self.controller.select_index(index))

    def activate(self, index: int) -> None:
        self._apply_details(self.controller.activate_index(index))

    def show_context_menu(self, index: int, x: float, y: float) -> bool:
        actions = self.controller.context_actions(index)
        commands = []
        for action in actions:
            commands.append(CommandData(action.stable_id, action.label, enabled=action.enabled))
        self.context_model.set_commands(commands)
        self.context_index = index
        return self.context_menu.show(Point(x, y), self.viewport())

    def execute_context_action(self, action_id: str) -> None:
        try:
            snapshot = self.controller.execute_context_action(action_id, self.context_index)
        except Exception:
            _logger.exception("Native registry context action failed: %s", action_id)
            raise
        self._apply_snapshot(snapshot)

    def _apply_snapshot(self, snapshot: RegistrySnapshot) -> None:
        self.table_model.set_rows([TableRowData(row.stable_id, list(row.cells)) for row in snapshot.rows])
        hierarchical = (
            isinstance(self.controller, RegistryCatalogController) and self.controller.current_page.hierarchical
        )
        self.table_root.visible = not hierarchical
        self.tree_root.visible = hierarchical
        if hierarchical:
            self._apply_tree(snapshot)
        self._apply_details(snapshot)

    def _apply_tree(self, snapshot: RegistrySnapshot) -> None:
        self.tree_model.clear()
        self.tree_expansion_model.clear()
        self.tree_node_indices = {}
        nodes_by_id: dict[str, int] = {}
        pending = list(enumerate(snapshot.rows))
        while pending:
            remaining = []
            for index, row in pending:
                if row.parent_id is None:
                    node = self.tree_model.append_root(
                        CollectionItem(
                            row.stable_id,
                            row.cells[0] if row.cells else row.stable_id,
                            row.cells[1] if len(row.cells) > 1 else "",
                        )
                    )
                else:
                    parent = nodes_by_id.get(row.parent_id)
                    if parent is None:
                        remaining.append((index, row))
                        continue
                    node = self.tree_model.append_child(
                        parent,
                        CollectionItem(
                            row.stable_id,
                            row.cells[0] if row.cells else row.stable_id,
                            row.cells[1] if len(row.cells) > 1 else "",
                        ),
                    )
                nodes_by_id[row.stable_id] = node
                self.tree_node_indices[node] = index
                if row.parent_id is None or snapshot.filter_text:
                    self.tree_expansion_model.set_expanded(node, True)
            if len(remaining) == len(pending):
                _logger.error("Native registry tree could not resolve %d parent links", len(remaining))
                break
            pending = remaining
        self.tree_expansion_model.reconcile(self.tree_model)

    def _apply_details(self, snapshot: RegistrySnapshot) -> None:
        self.details_model.set_text(snapshot.selected_details)
        if isinstance(self.controller, RegistryCatalogController):
            self.status_bar.text = f"{self.controller.current_page.label} | {snapshot.status}"
        else:
            self.status_bar.text = snapshot.status
        self.request_render()

    def _set_columns(self, columns: tuple[RegistryColumn, ...]) -> None:
        native_columns = []
        for column in columns:
            if column.width is not None:
                native_columns.append(
                    TableColumn(
                        column.stable_id,
                        column.label,
                        TableColumnPolicy.Fixed,
                        width=column.width,
                    )
                )
            else:
                native_columns.append(
                    TableColumn(
                        column.stable_id,
                        column.label,
                        min_width=100.0,
                        stretch=column.stretch,
                    )
                )
        self.column_model.set_columns(native_columns)


def build_native_registry_viewer(
    document: TcDocument,
    controller: RegistryCollectionController,
    *,
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
) -> NativeRegistryViewer:
    columns = (
        RegistryColumn("type", "Type", stretch=2.0),
        RegistryColumn("backend", "Backend", 92.0),
        RegistryColumn("parent", "Parent"),
        RegistryColumn("fields", "Fields", 70.0),
    )
    return _build_native_registry_viewer(
        document,
        controller,
        title="Inspect Registry",
        columns=columns,
        viewport=viewport,
        request_render=request_render,
    )


def build_native_registry_catalog_viewer(
    document: TcDocument,
    controller: RegistryCatalogController,
    *,
    title: str,
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
) -> NativeRegistryViewer:
    return _build_native_registry_viewer(
        document,
        controller,
        title=title,
        columns=controller.current_page.columns,
        viewport=viewport,
        request_render=request_render,
    )


def _build_native_registry_viewer(
    document: TcDocument,
    controller: RegistryCollectionController | RegistryCatalogController,
    *,
    title: str,
    columns: tuple[RegistryColumn, ...],
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
) -> NativeRegistryViewer:
    root = document.create_vstack("native-registry-viewer")
    root.stable_id = "editor.registry-viewer"
    root.preferred_size = Size(1040.0, 560.0)
    root.set_layout_padding(EdgeInsets(4.0, 4.0, 4.0, 4.0))
    root.set_layout_spacing(6.0)

    filter_row = document.create_hstack("registry-filter-row")
    filter_row.set_layout_spacing(6.0)
    page_selector = None
    if isinstance(controller, RegistryCatalogController):
        page_selector = document.create_combo_box()
        for page in controller.pages:
            page_selector.add_item(page.label)
        page_selector.selected_index = controller.current_index
        filter_row.add_fixed_child(_ref(document, page_selector), 150.0)
    filter_label = document.create_label("Filter:", "registry-filter-label")
    filter_row.add_fixed_child(_ref(document, filter_label), 52.0)
    filter_input = document.create_text_input()
    filter_row.add_stretch_child(_ref(document, filter_input))

    toolbar_model = CommandModel()
    toolbar_model.set_commands(
        [
            CommandData("refresh", "Refresh", shortcut="F5"),
            CommandData("clear-filter", "Clear"),
        ]
    )
    toolbar = document.create_tool_bar(toolbar_model)
    filter_row.add_fixed_child(_ref(document, toolbar), 150.0)
    root.add_fixed_child(filter_row, 36.0)

    main = document.create_hstack("registry-main")
    main.set_layout_spacing(8.0)
    table_model = TableModel()
    column_model = TableColumnModel()
    table = document.create_table_widget(table_model, column_model)
    table_root = _ref(document, table)
    main.add_stretch_child(table_root)
    tree_model = TreeModel()
    tree_expansion_model = TreeExpansionModel()
    tree = document.create_tree_widget(tree_model, tree_expansion_model)
    tree_root = _ref(document, tree)
    tree_root.visible = False
    main.add_stretch_child(tree_root)
    details_model = RichTextModel()
    details = document.create_rich_text_view(details_model)
    details.placeholder = "Select a registry entry to inspect details"
    details.word_wrap = False
    main.add_fixed_child(_ref(document, details), 420.0)
    root.add_stretch_child(main)

    status = document.create_status_bar("Registry entries: 0")
    root.add_fixed_child(_ref(document, status), 24.0)

    dialog = document.create_dialog(title)
    dialog.actions = [DialogAction("close", "Close", is_default=True, is_cancel=True)]
    dialog.set_content(root)

    context_model = CommandModel()
    context_menu = document.create_menu(context_model)
    viewer = NativeRegistryViewer(
        document=document,
        controller=controller,
        dialog=dialog,
        root=root,
        filter_input=filter_input,
        table_widget=table,
        table_root=table_root,
        tree_widget=tree,
        tree_root=tree_root,
        details=details,
        details_model=details_model,
        status_bar=status,
        table_model=table_model,
        column_model=column_model,
        tree_model=tree_model,
        tree_expansion_model=tree_expansion_model,
        toolbar_model=toolbar_model,
        context_model=context_model,
        context_menu=context_menu,
        page_selector=page_selector,
        viewport=viewport,
        request_render=request_render,
        tree_node_indices={},
    )
    viewer._set_columns(columns)
    weak_viewer = weakref.ref(viewer)

    def on_filter_changed(text: str) -> None:
        current = weak_viewer()
        if current is not None:
            current.set_filter(text)

    def on_filter_submitted(_text: str) -> None:
        current = weak_viewer()
        if current is not None:
            current.refresh()

    def on_selection_changed(selected: list[int]) -> None:
        current = weak_viewer()
        if current is not None:
            current.select(selected[-1] if selected else -1)

    def on_activated(index: int, _row, _data) -> None:
        current = weak_viewer()
        if current is not None:
            current.activate(index)

    def on_context_menu(index: int, x: float, y: float) -> None:
        current = weak_viewer()
        if current is not None:
            current.show_context_menu(index, x, y)

    def on_tree_selection(node: int) -> None:
        current = weak_viewer()
        if current is not None and current.tree_node_indices is not None:
            current.select(current.tree_node_indices.get(node, -1))

    def on_tree_activated(node: int, _item) -> None:
        current = weak_viewer()
        if current is not None and current.tree_node_indices is not None:
            current.activate(current.tree_node_indices.get(node, -1))

    def on_tree_context(node: int, x: float, y: float) -> None:
        current = weak_viewer()
        if current is not None and current.tree_node_indices is not None:
            current.show_context_menu(current.tree_node_indices.get(node, -1), x, y)

    filter_input.connect_changed(on_filter_changed)
    filter_input.connect_submitted(on_filter_submitted)
    table.connect_selection_changed(on_selection_changed)
    table.connect_activated(on_activated)
    table.connect_context_menu_requested(on_context_menu)
    tree.connect_selection_changed(on_tree_selection)
    tree.connect_activated(on_tree_activated)
    tree.connect_context_menu_requested(on_tree_context)
    if page_selector is not None:

        def on_page_changed(index: int, _text: str) -> None:
            current = weak_viewer()
            if current is not None:
                current.select_page(index)

        page_selector.connect_changed(on_page_changed)

    def on_toolbar(_index: int, _command_id: int, command) -> None:
        current = weak_viewer()
        if current is None:
            return
        if command.stable_id == "refresh":
            current.refresh()
        elif command.stable_id == "clear-filter":
            current.filter_input.text = ""

    def on_context_action(_index: int, _command_id: int, command) -> None:
        current = weak_viewer()
        if current is not None:
            current.execute_context_action(command.stable_id)

    toolbar.connect_activated(on_toolbar)
    context_menu.connect_activated(on_context_action)
    return viewer


def connect_registry_viewer_command(
    menu_bar,
    command_id: int,
    viewer: NativeRegistryViewer,
) -> None:
    weak_viewer = weakref.ref(viewer)

    def on_menu_activated(_menu_index: int, activated_id: int, _command) -> None:
        if activated_id == command_id:
            current = weak_viewer()
            if current is not None:
                current.show()

    menu_bar.connect_activated(on_menu_activated)


__all__ = [
    "NativeRegistryViewer",
    "build_native_registry_catalog_viewer",
    "build_native_registry_viewer",
    "connect_registry_viewer_command",
]
