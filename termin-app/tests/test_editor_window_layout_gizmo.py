from termin.editor_tcgui.editor_window_layout import (
    EditorWindowLayoutCallbacks,
    build_editor_window_layout,
)


def test_editor_window_layout_wires_gizmo_orientation_button() -> None:
    clicks: list[str] = []
    widgets = build_editor_window_layout(
        EditorWindowLayoutCallbacks(
            toggle_game_mode=lambda: None,
            toggle_pause=lambda: None,
            save_prefab=lambda: None,
            exit_prefab_editing=lambda: None,
            toggle_gizmo_orientation=lambda: clicks.append("gizmo"),
            viewport_external_drag=lambda _event: False,
            viewport_external_drop=lambda _event: False,
        )
    )

    assert widgets.gizmo_orientation_button.text == "Local"

    widgets.gizmo_orientation_button.on_click()

    assert clicks == ["gizmo"]
