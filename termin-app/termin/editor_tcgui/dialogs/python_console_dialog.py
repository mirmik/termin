"""Windowed Python console dialog for editor diagnostics."""

from __future__ import annotations

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.units import px

from termin.editor_tcgui.python_console_panel import PythonConsolePanel


def show_python_console_dialog(
    ui,
    *,
    editor: object,
    get_scene,
    get_project_path,
    executor=None,
) -> Dialog:
    panel = PythonConsolePanel()
    panel.preferred_width = px(880)
    panel.preferred_height = px(480)
    panel.set_context(
        editor=editor,
        get_scene=get_scene,
        get_project_path=get_project_path,
        executor=executor,
    )

    dlg = Dialog()
    dlg.title = "Python Console"
    dlg.content = panel
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.preferred_width = px(920)
    dlg.preferred_height = px(560)
    dlg.show(ui, windowed=True)
    return dlg
