from pathlib import Path

from tcbase import Key
from tcnodegraph.controller import GraphController
from tcnodegraph.model import Graph
from termin.editor_core.pipeline_editor_model import PipelineEditorController
from termin.editor_native.dialog_service import NativeDialogService
from termin.editor_native.pipeline_editor import (
    build_native_pipeline_editor,
    connect_pipeline_editor_command,
)
from termin.editor_native.shell import build_native_editor_shell
from termin.gui_native import Document, DrawCommandType, DrawList, PaintContext, Point, Rect


def test_native_pipeline_editor_projects_params_and_roundtrips_file(tmp_path: Path):
    graph = Graph()
    graph_controller = GraphController(graph)
    node = graph_controller.create_node("resource", title="Probe", x=10.0, y=20.0)
    node.data.update(
        {
            "graph_type": "Probe",
            "node_type": "resource",
            "instance_name": "",
            "dynamic_inputs": [],
            "explicit_size": False,
            "param_specs": {"enabled": {"kind": "bool", "label": "Enabled"}},
        }
    )
    node.params["enabled"] = True
    graph_controller.add_output_socket(node.id, "fbo", "fbo")
    controller = PipelineEditorController(graph)
    graph_events = []
    controller.graph_changed.connect(graph_events.append)
    document = Document()
    shell = build_native_editor_shell(document)
    renders = []
    viewport = lambda: Rect(0.0, 0.0, 1280.0, 800.0)
    dialog_service = NativeDialogService(
        document,
        viewport=viewport,
        request_render=lambda: renders.append(True),
    )
    editor = build_native_pipeline_editor(
        document,
        controller,
        dialog_service=dialog_service,
        viewport=viewport,
        request_render=lambda: renders.append(True),
        default_directory=tmp_path,
    )

    connect_pipeline_editor_command(shell.menu_bar, shell.pipeline_editor_command, editor)
    assert shell.menu_bar.dispatch_shortcut(Key.F11.value, 0)
    assert editor.dialog.open
    document.layout_roots(viewport())
    draw_list = DrawList()
    document.paint(PaintContext(draw_list))
    assert DrawCommandType.Text in [command.type for command in draw_list.commands]

    checkbox = editor.graph_view.param_widgets[(node.id, "enabled")]
    checkbox.checked = False
    assert node.params["enabled"] is False
    assert graph_events == [graph]

    path = tmp_path / "probe.pipeline"
    editor.save(path)
    assert path.is_file()
    assert editor.path_label.text == str(path)

    editor.show_context(Point(400.0, 100.0), None)
    editor.execute_context("add-pipeline-output")
    assert len(editor.graph_view.node_items) == 2
    editor.load(path)
    assert len(controller.graph.nodes) == 1
    assert len(editor.graph_view.node_items) == 1
    assert renders

    editor.close()
    assert not document.is_alive(editor.dialog.handle)
    assert not document.is_alive(editor.context_menu.handle)
