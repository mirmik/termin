from termin.editor_tcgui.pipeline_editor_window import (
    _legacy_pipeline_to_graph,
    _load_graph_from_pipeline_dict,
)
from tcgui.scene import GraphicsWidgetItem
from tcnodegraph import NodeGraphView


def test_pipeline_graph_load_populates_node_params_and_sockets():
    graph = _load_graph_from_pipeline_dict(
        {
            "nodes": [
                {"type": "FBO", "node_type": "resource"},
                {"type": "UIWidgetPass", "node_type": "pass"},
            ],
            "connections": [],
        }
    )

    resource_node = graph.nodes["node_0"]
    pass_node = graph.nodes["node_1"]

    assert resource_node.params["format"] == "render_target"
    assert resource_node.params["samples"] == "1"
    assert resource_node.params["has_depth"] is True
    assert [socket.name for socket in resource_node.outputs] == ["fbo"]

    assert pass_node.params["include_internal_entities"] is False
    assert [socket.name for socket in pass_node.inputs] == ["input_res"]
    assert [socket.name for socket in pass_node.outputs] == ["output_res"]


def test_legacy_pipeline_to_graph_populates_pass_params():
    graph = _legacy_pipeline_to_graph(
        {
            "passes": [
                {
                    "type": "UIWidgetPass",
                    "pass_name": "UI",
                }
            ]
        }
    )

    node = graph.nodes["node_0"]

    assert node.params["include_internal_entities"] is False


def test_pipeline_graph_load_handles_native_pass_metadata_without_python_fields():
    graph = _load_graph_from_pipeline_dict(
        {
            "nodes": [
                {"type": "ColorPass", "node_type": "pass"},
            ],
            "connections": [],
        }
    )

    node = graph.nodes["node_0"]

    assert [socket.name for socket in node.inputs] == ["input_res", "shadow_res"]
    assert [socket.name for socket in node.outputs] == ["output_res"]
    assert node.params["phase_mark"] == ""
    assert node.params["sort_mode"] == "none"
    assert node.params["clear_depth"] is False


def test_node_graph_view_mounts_inline_param_widgets_when_enabled():
    graph = _load_graph_from_pipeline_dict(
        {
            "nodes": [
                {"type": "UIWidgetPass", "node_type": "pass"},
            ],
            "connections": [],
        }
    )
    view = NodeGraphView(graph)
    view.use_param_widgets = True
    view.inline_param_editing = False
    view.refresh()
    node = graph.nodes["node_0"]
    item = view.adapter.node_items["node_0"]

    widget_items = [child for child in item.children if isinstance(child, GraphicsWidgetItem)]

    assert view.inline_param_editing is False
    assert item.draw_param_values is False
    assert len(widget_items) == 1

    checkbox = widget_items[0].widget
    checkbox.on_changed(True)

    assert node.params["include_internal_entities"] is True
