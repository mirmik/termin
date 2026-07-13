"""Pipeline Editor window for tcgui based on tcnodegraph."""

from __future__ import annotations

from pathlib import Path

from tcbase import log
from tcgui.widgets.button import Button
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.menu import MenuItem
from tcgui.widgets.ui import UI
from tcgui.widgets.units import pct, px
from tcgui.widgets.vstack import VStack
from tcgui.widgets.file_dialog_overlay import show_open_file_dialog, show_save_file_dialog
from tcgui.widgets.input_dialog import show_input_dialog

from termin.editor_core.pipeline_editor_model import PipelineEditorController


def open_pipeline_editor_window(parent_ui: UI, directory: str | None = None, initial_file: str | None = None) -> None:
    """Open Pipeline Editor in a separate tcgui window.

    Args:
        parent_ui: Parent UI for window creation.
        directory: Directory for file dialogs.
        initial_file: Optional path to a .pipeline file to load immediately.
    """
    if parent_ui.create_window is None:
        log.error("[PipelineEditor] ui.create_window is not available")
        return

    child = parent_ui.create_window("Pipeline Editor", 1500, 920)
    if child is None:
        log.error("[PipelineEditor] failed to create window")
        return

    from tcnodegraph import NodeGraphView

    editor = PipelineEditorController()
    graph_view = NodeGraphView(editor.graph)
    graph_view.use_param_widgets = True
    graph_view.inline_param_editing = False
    graph_view.preferred_width = pct(100)
    graph_view.preferred_height = pct(100)
    graph_view.offset_x = 500
    graph_view.offset_y = 320

    def _on_graph_param_changed(node, name: str, _value: object) -> None:
        editor.synchronize_param(node)
        editor.notify_graph_changed()
        if name == "material":
            graph_view.refresh()

    graph_view.on_param_changed = _on_graph_param_changed

    root = VStack()
    root.preferred_width = pct(100)
    root.preferred_height = pct(100)
    root.spacing = 0

    toolbar = HStack()
    toolbar.preferred_height = px(34)
    toolbar.spacing = 6
    toolbar.padding = 6

    btn_open = Button()
    btn_open.text = "Open"

    btn_save = Button()
    btn_save.text = "Save"

    btn_save_as = Button()
    btn_save_as.text = "Save As"

    path_label = Label()
    path_label.text = "(no file)"
    path_label.stretch = True

    status_label = Label()
    status_label.text = "Ready"
    status_label.preferred_height = px(24)

    def _set_status(message: str) -> None:
        status_label.text = message

    def _sync_editor_state() -> None:
        path_label.text = str(editor.file_path) if editor.file_path else "(no file)"
        _set_status(editor.status)

    def _load_path(path: str) -> None:
        if not path:
            return
        try:
            graph_view.set_graph(editor.load(path))
            _sync_editor_state()
        except Exception as error:
            log.error(f"[PipelineEditor] load failed: {error}")
            _sync_editor_state()

    def _save_to(path: str) -> None:
        if not path:
            return
        try:
            graph_view.adapter.apply_item_positions_to_model()
            editor.save(path)
            _sync_editor_state()
        except Exception as error:
            log.error(f"[PipelineEditor] save failed: {error}")
            _sync_editor_state()

    def _create_node(node_type: str, graph_type: str, wx: float, wy: float) -> None:
        editor.create_node(node_type, graph_type, wx, wy)
        graph_view.refresh()

    def _build_context_menu(wx: float, wy: float) -> list[MenuItem]:
        from tcnodegraph.view import NodeItem, EdgeItem

        hit = graph_view.scene.hit_test(wx, wy)

        # Right-click on a node → node-specific actions
        if isinstance(hit, NodeItem):
            node_id = hit.node_id
            items: list[MenuItem] = [
                MenuItem("Delete Node", on_click=lambda: (_delete_node(node_id))),
                MenuItem("Rename", on_click=lambda: _rename_node(node_id)),
                MenuItem.sep(),
                MenuItem("Add FBO", on_click=lambda: _create_node("resource", "FBO", wx, wy)),
                MenuItem("Add Color Texture", on_click=lambda: _create_node("resource", "Color Texture", wx, wy)),
                MenuItem("Add Depth Texture", on_click=lambda: _create_node("resource", "Depth Texture", wx, wy)),
                MenuItem("Add Shadow Maps", on_click=lambda: _create_node("resource", "Shadow Maps", wx, wy)),
                MenuItem("Add Render Target Input", on_click=lambda: _create_node("render_target_input", "RenderTargetInput", wx, wy)),
                MenuItem("Add Pipeline Output", on_click=lambda: _create_node("pipeline_output", "PipelineOutput", wx, wy)),
                MenuItem("Add External RT", on_click=lambda: _create_node("external_rt", "External RT", wx, wy)),
                MenuItem("Add FBO Split", on_click=lambda: _create_node("fbo_split", "FBO Split", wx, wy)),
                MenuItem("Add FBO Join", on_click=lambda: _create_node("fbo_join", "FBO Join", wx, wy)),
                MenuItem("Add Output Render Target", on_click=lambda: _create_node("output", "RenderTarget", wx, wy)),
            ]
            return items

        # Right-click on an edge → edge-specific actions
        if isinstance(hit, EdgeItem):
            edge_id = hit.data.get("edge_id")
            if edge_id:
                return [MenuItem("Delete Connection", on_click=lambda: _delete_edge(edge_id))]
            return []

        # Empty space → create menu
        return _build_create_menu_items(wx, wy)

    def _delete_node(node_id: str) -> None:
        if editor.remove_node(node_id):
            graph_view.refresh()

    def _delete_edge(edge_id: str) -> None:
        if editor.remove_edge(edge_id):
            graph_view.refresh()

    def _build_create_menu_items(wx: float, wy: float) -> list[MenuItem]:
        items: list[MenuItem] = [
            MenuItem("Add Render Target Input", on_click=lambda: _create_node("render_target_input", "RenderTargetInput", wx, wy)),
            MenuItem("Add Pipeline Output", on_click=lambda: _create_node("pipeline_output", "PipelineOutput", wx, wy)),
            MenuItem("Add Output Render Target", on_click=lambda: _create_node("output", "RenderTarget", wx, wy)),
            MenuItem.sep(),
            MenuItem("Add FBO", on_click=lambda: _create_node("resource", "FBO", wx, wy)),
            MenuItem("Add Color Texture", on_click=lambda: _create_node("resource", "Color Texture", wx, wy)),
            MenuItem("Add Depth Texture", on_click=lambda: _create_node("resource", "Depth Texture", wx, wy)),
            MenuItem("Add Shadow Maps", on_click=lambda: _create_node("resource", "Shadow Maps", wx, wy)),
            MenuItem("Add External RT", on_click=lambda: _create_node("external_rt", "External RT", wx, wy)),
            MenuItem("Add FBO Split", on_click=lambda: _create_node("fbo_split", "FBO Split", wx, wy)),
            MenuItem("Add FBO Join", on_click=lambda: _create_node("fbo_join", "FBO Join", wx, wy)),
            MenuItem.sep(),
        ]
        try:
            for cls_name, kind, label in editor.available_passes():
                items.append(
                    MenuItem(
                        label,
                        on_click=lambda c=cls_name, k=kind: _create_node(k, c, wx, wy),
                    )
                )
        except Exception as e:
            log.warn(f"[PipelineEditor] Cannot build pass menu: {e}")
        return items

    def _rename_node(node_id: str) -> None:
        node = editor.graph.nodes.get(node_id)
        if node is None or graph_view._ui is None:
            return
        current = str(node.data.get("instance_name", node.title))

        def _apply(result: str | None) -> None:
            if result is None:
                return
            if editor.rename_node(node_id, result):
                graph_view.refresh()

        show_input_dialog(
            graph_view._ui,
            title="Rename Node",
            message="Node name:",
            default=current,
            on_result=_apply,
        )

    def _on_open_click() -> None:
        start_dir = directory or str(Path.home())
        if editor.file_path:
            start_dir = str(editor.file_path.parent)
        show_open_file_dialog(
            child,
            title="Open Pipeline",
            directory=start_dir,
            filter_str="Pipeline (*.pipeline);;All Files (*)",
            on_result=lambda p: _load_path(p) if p else None,
            windowed=True,
        )

    def _on_save_click() -> None:
        if editor.file_path:
            _save_to(str(editor.file_path))
            return
        _on_save_as_click()

    def _on_save_as_click() -> None:
        start_dir = directory or str(Path.home())
        if editor.file_path:
            start_dir = str(editor.file_path.parent)
        show_save_file_dialog(
            child,
            title="Save Pipeline",
            directory=start_dir,
            filter_str="Pipeline (*.pipeline);;All Files (*)",
            on_result=lambda p: _save_to(p) if p else None,
            windowed=True,
        )

    btn_open.on_click = _on_open_click
    btn_save.on_click = _on_save_click
    btn_save_as.on_click = _on_save_as_click
    graph_view.menu_items_provider = _build_context_menu

    toolbar.add_child(btn_open)
    toolbar.add_child(btn_save)
    toolbar.add_child(btn_save_as)
    toolbar.add_child(path_label)

    root.add_child(toolbar)
    root.add_child(graph_view)
    root.add_child(status_label)
    child.root = root

    # Auto-load file: explicit initial_file takes priority, then search project dir.
    if initial_file:
        _load_path(initial_file)
    elif directory:
        try:
            pdir = Path(directory)
            candidates = sorted(pdir.glob("*.pipeline"))
            if not candidates:
                candidates = sorted(pdir.rglob("*.pipeline"))
            if candidates:
                _load_path(str(candidates[0]))
        except Exception as e:
            log.warn(f"[PipelineEditor] auto-load skipped: {e}")
