"""Native pipeline editor shell over the shared pipeline and nodegraph models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
import weakref

from tcnodegraph.native_view import build_native_node_graph_view
from termin.editor_core.pipeline_editor_model import PipelineEditorController
from termin.gui_native import (
    CommandData,
    CommandKind,
    CommandModel,
    DialogAction,
    Document,
    EdgeInsets,
    Point,
    Rect,
    Size,
    WidgetRef,
)

from .dialog_service import NativeDialogService


_PIPELINE_FILTER = "Scene Pipeline | *.scene_pipeline;;Pipeline | *.pipeline"


@dataclass
class NativePipelineEditor:
    document: Document
    controller: PipelineEditorController
    dialog_service: NativeDialogService
    dialog: object
    root: WidgetRef
    toolbar: object
    path_label: object
    status_bar: object
    graph_view: object
    context_model: CommandModel
    context_menu: object
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    default_directory: Path
    _context_actions: dict[str, Callable[[], None]] = field(default_factory=dict)
    _closed: bool = False

    def show(self) -> None:
        if self._closed:
            raise RuntimeError("native pipeline editor is closed")
        if not self.dialog.open and not self.dialog.show(self.viewport()):
            raise RuntimeError("failed to show native pipeline editor")
        self.request_render()

    def load(self, path: str | Path) -> None:
        graph = self.controller.load(path)
        self.graph_view.set_graph(graph)
        self._sync_labels()

    def save(self, path: str | Path | None = None) -> None:
        self.controller.save(path)
        self._sync_labels()

    def refresh(self) -> None:
        self.graph_view.rebuild()
        self._sync_labels()

    def execute_toolbar(self, stable_id: str) -> None:
        if stable_id == "open":
            self._show_open()
        elif stable_id == "save":
            if self.controller.file_path is None:
                self._show_save()
            else:
                self.save()
        elif stable_id == "save-as":
            self._show_save()

    def show_context(self, world: Point, stable_id: str | None) -> None:
        commands = []
        self._context_actions.clear()
        if stable_id is not None and stable_id.startswith("node:"):
            node_id = stable_id[5:]
            commands.extend(
                [
                    CommandData("delete-node", "Delete Node"),
                    CommandData("rename-node", "Rename..."),
                    CommandData("separator", kind=CommandKind.Separator),
                ]
            )
            self._context_actions["delete-node"] = lambda: self._delete_node(node_id)
            self._context_actions["rename-node"] = lambda: self._rename_node(node_id)
        elif stable_id is not None and stable_id.startswith("edge:"):
            edge_id = stable_id[5:]
            commands.extend(
                [
                    CommandData("delete-edge", "Delete Connection"),
                    CommandData("separator", kind=CommandKind.Separator),
                ]
            )
            self._context_actions["delete-edge"] = lambda: self._delete_edge(edge_id)
        commands.extend(self._create_commands(world))
        self.context_model.set_commands(commands)
        screen = self.graph_view.view.world_to_screen(world)
        if not self.context_menu.show(screen, self.viewport()):
            raise RuntimeError("failed to show native pipeline context menu")
        self.request_render()

    def execute_context(self, stable_id: str) -> None:
        action = self._context_actions.get(stable_id)
        if action is not None:
            action()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.context_menu.open:
            self.context_menu.dismiss()
        if self.dialog.open:
            self.dialog.activate("close")
        self.graph_view.close()
        if self.document.is_alive(self.context_menu.handle):
            self.document.destroy_widget_recursive(self.context_menu.handle)
        if self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)

    def _create_commands(self, world: Point) -> list[CommandData]:
        specs = [
            ("render-target-input", "Add Render Target Input", "render_target_input", "RenderTargetInput"),
            ("pipeline-output", "Add Pipeline Output", "pipeline_output", "PipelineOutput"),
            ("output", "Add Output Render Target", "output", "RenderTarget"),
            ("fbo", "Add FBO", "resource", "FBO"),
            ("color-texture", "Add Color Texture", "resource", "Color Texture"),
            ("depth-texture", "Add Depth Texture", "resource", "Depth Texture"),
            ("shadow-maps", "Add Shadow Maps", "resource", "Shadow Maps"),
            ("external-rt", "Add External RT", "external_rt", "External RT"),
            ("fbo-split", "Add FBO Split", "fbo_split", "FBO Split"),
            ("fbo-join", "Add FBO Join", "fbo_join", "FBO Join"),
        ]
        commands = []
        for stable_id, label, node_type, graph_type in specs:
            command_id = f"add-{stable_id}"
            commands.append(CommandData(command_id, label))
            self._context_actions[command_id] = lambda n=node_type, g=graph_type: self._create_node(
                n,
                g,
                world,
            )
        commands.append(CommandData("separator-passes", kind=CommandKind.Separator))
        for index, (class_name, node_type, label) in enumerate(self.controller.available_passes()):
            command_id = f"add-pass-{index}"
            commands.append(CommandData(command_id, label))
            self._context_actions[command_id] = lambda c=class_name, n=node_type: self._create_node(
                n,
                c,
                world,
            )
        return commands

    def _create_node(self, node_type: str, graph_type: str, world: Point) -> None:
        self.controller.create_node(node_type, graph_type, world.x, world.y)
        self.refresh()

    def _delete_node(self, node_id: str) -> None:
        if self.controller.remove_node(node_id):
            self.refresh()

    def _delete_edge(self, edge_id: str) -> None:
        if self.controller.remove_edge(edge_id):
            self.refresh()

    def _rename_node(self, node_id: str) -> None:
        node = self.controller.graph.nodes.get(node_id)
        if node is None:
            return

        def renamed(value: str | None) -> None:
            if value is not None and self.controller.rename_node(node_id, value):
                self.refresh()

        self.dialog_service.show_input(
            "Rename Pipeline Node",
            "Name:",
            str(node.data.get("instance_name", node.title)),
            renamed,
        )

    def _show_open(self) -> None:
        directory = self._current_directory()
        self.dialog_service.show_open_file(
            "Open Scene Pipeline",
            str(directory),
            _PIPELINE_FILTER,
            lambda path: self.load(path) if path else None,
        )

    def _show_save(self) -> None:
        directory = self._current_directory()
        name = "pipeline.pipeline"
        if self.controller.file_path is not None:
            name = self.controller.file_path.name
        self.dialog_service.show_save_file(
            "Save Pipeline",
            str(directory),
            _PIPELINE_FILTER,
            lambda path: self.save(path) if path else None,
            default_name=name,
        )

    def _current_directory(self) -> Path:
        if self.controller.file_path is not None:
            return self.controller.file_path.parent
        return self.default_directory

    def _sync_labels(self) -> None:
        self.path_label.text = (
            "(no file)" if self.controller.file_path is None else str(self.controller.file_path)
        )
        self.status_bar.text = self.controller.status
        self.request_render()


def build_native_pipeline_editor(
    document: Document,
    controller: PipelineEditorController,
    *,
    dialog_service: NativeDialogService,
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
    default_directory: str | Path,
) -> NativePipelineEditor:
    content = document.create_vstack("native-pipeline-editor")
    content.stable_id = "editor.pipeline-editor"
    content.preferred_size = Size(1180.0, 760.0)
    content.set_layout_spacing(4.0)
    content.set_layout_padding(EdgeInsets(4.0, 4.0, 4.0, 4.0))
    toolbar_model = CommandModel()
    toolbar_model.set_commands(
        [
            CommandData("open", "Open"),
            CommandData("save", "Save"),
            CommandData("save-as", "Save As"),
        ]
    )
    toolbar = document.create_tool_bar(toolbar_model)
    content.add_fixed_child(toolbar.widget, 36.0)
    path_label = document.create_status_bar("(no file)")
    content.add_fixed_child(path_label.widget, 24.0)
    graph_view = build_native_node_graph_view(
        document,
        controller.graph,
        request_render=request_render,
    )
    content.add_stretch_child(graph_view.root)
    status = document.create_status_bar(controller.status)
    content.add_fixed_child(status.widget, 24.0)
    dialog = document.create_dialog("Pipeline Editor")
    dialog.set_content(content)
    dialog.actions = [DialogAction("close", "Close", is_cancel=True)]
    context_model = CommandModel()
    context_menu = document.create_menu(context_model)
    result = NativePipelineEditor(
        document=document,
        controller=controller,
        dialog_service=dialog_service,
        dialog=dialog,
        root=content,
        toolbar=toolbar,
        path_label=path_label,
        status_bar=status,
        graph_view=graph_view,
        context_model=context_model,
        context_menu=context_menu,
        viewport=viewport,
        request_render=request_render,
        default_directory=Path(default_directory),
    )
    weak_result = weakref.ref(result)

    def toolbar_action(_index: int, _command_id: int, command) -> None:
        owner = weak_result()
        if owner is not None:
            owner.execute_toolbar(command.stable_id)

    def context_action(_index: int, _command_id: int, command) -> None:
        owner = weak_result()
        if owner is not None:
            owner.execute_context(command.stable_id)

    def context_requested(world: Point, stable_id: str | None) -> None:
        owner = weak_result()
        if owner is not None:
            owner.show_context(world, stable_id)

    def param_changed(node, name: str, value: object) -> None:
        owner = weak_result()
        if owner is not None:
            owner.controller.synchronize_param(node)
            owner.refresh()

    def graph_changed() -> None:
        owner = weak_result()
        if owner is not None:
            owner.controller.notify_graph_changed()

    toolbar.connect_activated(toolbar_action)
    context_menu.connect_activated(context_action)
    graph_view.on_context_requested = context_requested
    graph_view.on_param_changed = param_changed
    graph_view.on_graph_changed = graph_changed
    return result


def connect_pipeline_editor_command(menu_bar, command_id: int, editor: NativePipelineEditor) -> None:
    weak_editor = weakref.ref(editor)

    def activated(_menu_index: int, activated_id: int, _command) -> None:
        if activated_id != command_id:
            return
        owner = weak_editor()
        if owner is not None:
            owner.show()

    menu_bar.connect_activated(activated)


__all__ = [
    "NativePipelineEditor",
    "build_native_pipeline_editor",
    "connect_pipeline_editor_command",
]
