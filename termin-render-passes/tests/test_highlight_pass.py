from termin.inspect import InspectRegistry


def test_highlight_pass_is_exported_from_render_passes(capsys) -> None:
    from termin.render_passes import HighlightPass

    captured = capsys.readouterr()
    assert "InspectRegistry not available" not in captured.out
    assert "InspectRegistry not available" not in captured.err

    pass_obj = HighlightPass(selected_id_getter=lambda: 42)

    assert pass_obj.pass_name == "Highlight"
    assert pass_obj.compute_reads() == {"color", "id"}
    assert pass_obj.compute_writes() == {"color_highlight"}
    assert pass_obj._selected_id() == 42

    registry = InspectRegistry.instance()
    metadata = registry.get_type_metadata("HighlightPass")
    assert metadata["graph"]["node_inputs"] == [["input_res", "fbo"], ["id_res", "fbo"]]
    assert metadata["graph"]["node_outputs"] == [["output_res", "fbo"]]


def test_highlight_selected_color_is_normalized() -> None:
    from termin.render_passes._render_passes_native import tc_picking_id_to_rgb
    from termin.render_passes.highlight import _pick_id_to_rgb_float

    pick_id = 42
    expected = tuple(channel / 255.0 for channel in tc_picking_id_to_rgb(pick_id))

    assert _pick_id_to_rgb_float(pick_id) == expected
    assert all(0.0 <= channel <= 1.0 for channel in _pick_id_to_rgb_float(pick_id))


def test_ui_widget_pass_is_exported_from_render_passes() -> None:
    from termin.render_passes import UIWidgetPass
    from termin.render_framework.python_pass import PythonFramePass

    pass_obj = UIWidgetPass()

    assert not isinstance(pass_obj, PythonFramePass)
    assert pass_obj.pass_name == "UIWidgets"
    assert pass_obj.compute_reads() == {"color+ui"}
    assert pass_obj.compute_writes() == {"color+widgets"}
    assert pass_obj.get_inplace_aliases() == [("color+ui", "color+widgets")]
    assert pass_obj.include_scene_entities is True
    assert pass_obj.include_internal_entities is False


def test_color_pass_accepts_dynamic_graph_texture_inputs() -> None:
    from termin.render_passes import ColorPass

    pass_obj = ColorPass()

    assert pass_obj.set_graph_resource_input("panel_texture", "PANEL_COLOR")
    assert pass_obj.extra_textures == {"u_panel_texture": "PANEL_COLOR"}
    assert "PANEL_COLOR" in pass_obj.compute_reads()
    assert not pass_obj.set_graph_resource_input("input_res", "OTHER_COLOR")


def test_color_pass_dynamic_texture_inputs_survive_serialization() -> None:
    from termin.bootstrap import bootstrap_player
    from termin.render_passes import ColorPass

    bootstrap_player()
    original = ColorPass()
    original.set_graph_resource_input("panel_texture", "PANEL_COLOR")

    serialized = original._tc_pass.serialize_data()
    assert serialized["extra_textures"] == {
        "u_panel_texture": "PANEL_COLOR",
    }

    restored = ColorPass()
    restored._tc_pass.deserialize_data(serialized)
    assert restored.extra_textures == {
        "u_panel_texture": "PANEL_COLOR",
    }
    assert "PANEL_COLOR" in restored.compute_reads()
