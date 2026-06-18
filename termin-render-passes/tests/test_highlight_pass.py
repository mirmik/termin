from termin.render_passes import HighlightPass


def test_highlight_pass_is_exported_from_render_passes() -> None:
    pass_obj = HighlightPass(selected_id_getter=lambda: 42)

    assert pass_obj.pass_name == "Highlight"
    assert pass_obj.compute_reads() == {"color", "id"}
    assert pass_obj.compute_writes() == {"color_highlight"}
    assert pass_obj._selected_id() == 42
