import pytest

from termin.bootstrap import bootstrap_player, shutdown_player
from termin.editor_core.pipeline_editor_model import (
    load_pipeline_graph as _load_graph_from_pipeline_dict,
    pass_list_to_pipeline_graph as _pass_list_pipeline_to_graph,
    save_pipeline_graph as _save_graph_to_pipeline_dict,
)
from tcgui.scene import GraphicsWidgetItem
from tcnodegraph import NodeGraphView


@pytest.fixture(scope="module", autouse=True)
def player_runtime():
    bootstrap_player()
    yield
    shutdown_player()


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


def test_pass_list_pipeline_to_graph_populates_pass_params():
    graph = _pass_list_pipeline_to_graph(
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
    assert node.params["phase_mark"] == "opaque"
    assert node.params["sort_mode"] == "none"
    assert node.params["clear_depth"] is False


def test_material_pass_loads_texture_inputs_from_material_shader():
    from termin.editor_core.resource_manager import ResourceManager
    from termin.materials import TcMaterial, ShaderMultyPhaseProgramm, parse_shader_text

    shader_text = """
@program TestMaterialPassDynamicInputs
@language slang
@phase main
@property Texture2D u_input_tex = "white"
@property Texture2D u_depth_texture = "depth_default"
@stage vertex
void main() {}
@endstage
@stage fragment
void main() {}
@endstage
@endphase
"""
    rm = ResourceManager.instance()
    program = ShaderMultyPhaseProgramm.from_tree(parse_shader_text(shader_text))
    rm.register_shader("TestMaterialPassDynamicInputs", program)
    mat = TcMaterial.create("TestMaterialPassDynamicInputsMaterial", "")
    mat.shader_name = "TestMaterialPassDynamicInputs"
    rm.register_material("TestMaterialPassDynamicInputsMaterial", mat)

    graph = _load_graph_from_pipeline_dict(
        {
            "nodes": [
                {
                    "type": "MaterialPass",
                    "node_type": "effect",
                    "params": {"material": "TestMaterialPassDynamicInputsMaterial"},
                },
            ],
            "connections": [],
        }
    )

    node = graph.nodes["node_0"]

    asset = rm.get_material_asset("TestMaterialPassDynamicInputsMaterial")
    assert asset is not None
    assert node.params["material"] == asset.uuid
    assert [socket.name for socket in node.inputs] == [
        "output_res_target",
        "u_input_tex",
        "u_depth_texture",
    ]
    assert node.data["dynamic_inputs"] == [
        ("u_input_tex", "fbo"),
        ("u_depth_texture", "fbo"),
    ]

    saved = _save_graph_to_pipeline_dict(graph)
    assert saved["nodes"][0]["params"]["material"] == {
        "uuid": asset.uuid,
        "name": "TestMaterialPassDynamicInputsMaterial",
        "type": "uuid",
        "kind": "tc_material",
    }


def test_pipeline_graph_loads_explicit_render_target_nodes():
    graph = _load_graph_from_pipeline_dict(
        {
            "nodes": [
                {"type": "RenderTargetInput", "node_type": "render_target_input"},
                {"type": "PipelineOutput", "node_type": "pipeline_output"},
            ],
            "connections": [
                {"from_node": 0, "from_socket": "color", "to_node": 1, "to_socket": "color"},
            ],
        }
    )

    input_node = graph.nodes["node_0"]
    output_node = graph.nodes["node_1"]

    assert input_node.title == "RenderTargetInput"
    assert output_node.title == "PipelineOutput"
    assert [socket.name for socket in input_node.outputs] == ["color"]
    assert [socket.name for socket in output_node.inputs] == ["color"]

    saved = _save_graph_to_pipeline_dict(graph)

    assert saved["nodes"][0]["node_type"] == "render_target_input"
    assert saved["nodes"][0]["type"] == "RenderTargetInput"
    assert saved["nodes"][1]["node_type"] == "pipeline_output"
    assert saved["nodes"][1]["type"] == "PipelineOutput"
    assert saved["connections"] == [
        {"from_node": 0, "from_socket": "color", "to_node": 1, "to_socket": "color"},
    ]


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
