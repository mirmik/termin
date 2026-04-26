"""Settings dialog — configure external text editor and font sizes."""

from __future__ import annotations

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.button import Button
from tcgui.widgets.spin_box import SpinBox


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
    from termin.editor.settings import EditorSettings
    settings = EditorSettings.instance()

    content = VStack()
    content.spacing = 8

    # Text editor
    lbl = Label()
    lbl.text = "External Text Editor:"
    content.add_child(lbl)

    row = HStack()
    row.spacing = 4

    editor_input = TextInput()
    editor_input.text = settings.get_text_editor() or ""
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

    # Font sizes
    font_row, font_spin = _make_spin_row(
        "Font Size:", settings.get_font_size(),
        8.0, 32.0, 1.0, 0)
    content.add_child(font_row)

    font_small_row, font_small_spin = _make_spin_row(
        "Font Size (small):", settings.get_font_size_small(),
        8.0, 24.0, 1.0, 0)
    content.add_child(font_small_row)

    note = Label()
    note.text = "Font changes take effect after restart."
    note.font_size = 11.0
    from tcgui.widgets.theme import current_theme as _t
    note.color = _t.text_muted
    content.add_child(note)

    dlg = Dialog()
    dlg.title = "Settings"
    dlg.content = content
    dlg.buttons = ["OK", "Cancel"]
    dlg.default_button = "OK"
    dlg.cancel_button = "Cancel"
    dlg.min_width = 450

    def _on_result(btn: str):
        if btn == "OK":
            text = editor_input.text.strip()
            settings.set_text_editor(text if text else None)
            settings.set_font_size(font_spin.value)
            settings.set_font_size_small(font_small_spin.value)
            settings.sync()

    dlg.on_result = _on_result
    dlg.show(ui, windowed=True)
