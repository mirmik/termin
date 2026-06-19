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
