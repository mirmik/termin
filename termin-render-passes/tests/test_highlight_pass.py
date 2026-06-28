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

    pass_obj = UIWidgetPass()

    assert pass_obj.pass_name == "UIWidgets"
    assert pass_obj.compute_reads() == {"color+ui"}
    assert pass_obj.compute_writes() == {"color+widgets"}
    assert pass_obj.get_inplace_aliases() == [("color+ui", "color+widgets")]
