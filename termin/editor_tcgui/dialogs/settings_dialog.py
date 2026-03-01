"""Settings dialog — configure external text editor path."""

from __future__ import annotations

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.button import Button
from tcgui.widgets.units import px


def show_settings_dialog(ui) -> None:
    """Show modal settings dialog."""
    from termin.editor.settings import EditorSettings
    settings = EditorSettings.instance()

    content = VStack()
    content.spacing = 8

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
        )

    def _set_editor_path(path: str):
        editor_input.text = path

    browse_btn.on_click = _browse
    row.add_child(browse_btn)
    content.add_child(row)

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
            settings.sync()

    dlg.on_result = _on_result
    dlg.show(ui, windowed=True)
