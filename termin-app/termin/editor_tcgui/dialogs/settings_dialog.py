"""Settings dialog — configure editor tools and font sizes."""

from __future__ import annotations

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.button import Button
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.spin_box import SpinBox
from termin.editor_core.settings_model import EditorSettingsController, EditorSettingsSnapshot


def _make_spin_row(label_text: str, value: float, min_v: float, max_v: float,
                   step: float, decimals: int) -> tuple[HStack, SpinBox]:
    row = HStack()
    row.spacing = 8
    lbl = Label()
    lbl.text = label_text
    row.add_child(lbl)
    spin = SpinBox()
    spin.value = value
    spin.min_value = min_v
    spin.max_value = max_v
    spin.step = step
    spin.decimals = decimals
    row.add_child(spin)
    return row, spin


def show_settings_dialog(ui) -> None:
    """Show modal settings dialog."""
    controller = EditorSettingsController()
    snapshot = controller.load()

    content = VStack()
    content.spacing = 8

    # Text editor
    lbl = Label()
    lbl.text = "External Text Editor:"
    content.add_child(lbl)

    row = HStack()
    row.spacing = 4

    editor_input = TextInput()
    editor_input.text = snapshot.text_editor
    editor_input.stretch = True
    row.add_child(editor_input)

    browse_btn = Button()
    browse_btn.text = "Browse..."
    browse_btn.padding = 6

    def _browse():
        from tcgui.widgets.file_dialog_overlay import show_open_file_dialog
        show_open_file_dialog(
            ui,
            on_result=lambda path: _set_editor_path(path) if path else None,
            title="Select Text Editor",
            windowed=True,
        )

    def _set_editor_path(path: str):
        editor_input.text = path

    browse_btn.on_click = _browse
    row.add_child(browse_btn)
    content.add_child(row)

    # Slang compiler
    slang_lbl = Label()
    slang_lbl.text = "Slang Compiler:"
    content.add_child(slang_lbl)

    slang_row = HStack()
    slang_row.spacing = 4

    slang_input = TextInput()
    slang_input.text = snapshot.slang_compiler
    slang_input.stretch = True
    slang_row.add_child(slang_input)

    slang_browse_btn = Button()
    slang_browse_btn.text = "Browse..."
    slang_browse_btn.padding = 6

    def _browse_slang():
        from tcgui.widgets.file_dialog_overlay import show_open_file_dialog
        show_open_file_dialog(
            ui,
            on_result=lambda path: _set_slang_path(path) if path else None,
            title="Select slangc",
            windowed=True,
        )

    def _set_slang_path(path: str):
        slang_input.text = path

    slang_browse_btn.on_click = _browse_slang
    slang_row.add_child(slang_browse_btn)
    content.add_child(slang_row)

    # Font sizes
    from tcgui.widgets.theme import current_theme as _t

    font_row, font_spin = _make_spin_row(
        "Font Size:", snapshot.font_size,
        8.0, 32.0, 1.0, 0)
    content.add_child(font_row)

    font_small_row, font_small_spin = _make_spin_row(
        "Font Size (small):", snapshot.font_size_small,
        8.0, 24.0, 1.0, 0)
    content.add_child(font_small_row)

    mcp_check = Checkbox()
    mcp_check.text = "Enable local editor MCP server on startup"
    mcp_check.checked = snapshot.mcp_server_enabled
    content.add_child(mcp_check)

    # Apply button — applies font changes without closing the dialog
    apply_row = HStack()
    apply_row.spacing = 8
    apply_row.alignment = "right"
    apply_btn = Button()
    apply_btn.text = "Apply"
    apply_btn.padding = 8
    apply_row.add_child(apply_btn)
    content.add_child(apply_row)

    def _apply():
        _t.font_size = font_spin.value
        _t.font_size_small = font_small_spin.value
        if ui.root is not None:
            _t.apply_to(ui.root)
            ui.request_layout()

    apply_btn.on_click = _apply

    dlg = Dialog()
    dlg.title = "Settings"
    dlg.content = content
    dlg.buttons = ["OK", "Cancel"]
    dlg.default_button = "OK"
    dlg.cancel_button = "Cancel"
    dlg.min_width = 450

    def _on_result(btn: str):
        if btn == "OK":
            controller.save(
                EditorSettingsSnapshot(
                    text_editor=editor_input.text,
                    slang_compiler=slang_input.text,
                    font_size=font_spin.value,
                    font_size_small=font_small_spin.value,
                    mcp_server_enabled=mcp_check.checked,
                )
            )

            # Apply font changes to the live widget tree immediately.
            _t.font_size = font_spin.value
            _t.font_size_small = font_small_spin.value
            if ui.root is not None:
                _t.apply_to(ui.root)
                ui.request_layout()

    dlg.on_result = _on_result
    dlg.show(ui, windowed=True)
