"""Project settings dialog — configure render sync mode."""

from __future__ import annotations

from typing import Callable

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.units import px


def show_project_settings_dialog(
    ui,
    on_changed: Callable[[], None] | None = None,
) -> None:
    """Show project settings dialog. Changes apply immediately."""
    from termin.project.settings import ProjectSettingsManager, RenderSyncMode

    manager = ProjectSettingsManager.instance()
    if manager is None or manager.project_path is None:
        from tcbase import log
        log.warn("No project open — cannot show project settings")
        return

    sync_modes = list(RenderSyncMode)
    mode_labels = [m.value.capitalize() for m in sync_modes]
    current_idx = sync_modes.index(manager.settings.render_sync_mode)

    content = VStack()
    content.spacing = 8

    row = HStack()
    row.spacing = 8
    lbl = Label()
    lbl.text = "Render Sync Mode:"
    row.add_child(lbl)

    combo = ComboBox()
    combo.items = mode_labels
    combo.selected_index = current_idx

    def _on_changed(idx: int):
        manager.set_render_sync_mode(sync_modes[idx])
        if on_changed:
            on_changed()

    combo.on_changed = lambda idx, _text: _on_changed(idx)
    row.add_child(combo)
    content.add_child(row)

    build_row = HStack()
    build_row.spacing = 8
    build_label = Label()
    build_label.text = "Build Output Dir:"
    build_label.tooltip = "Project-relative generated build directory. Asset watcher ignores this directory."
    build_row.add_child(build_label)

    build_dir_input = TextInput()
    build_dir_input.text = manager.settings.build_output_dir
    build_dir_input.preferred_width = px(180)

    def _on_build_dir_changed(text: str):
        manager.set_build_output_dir(text)
        if on_changed:
            on_changed()

    build_dir_input.on_submit = _on_build_dir_changed
    build_row.add_child(build_dir_input)
    content.add_child(build_row)

    dlg = Dialog()
    dlg.title = "Project Settings"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.min_width = 350

    dlg.show(ui, windowed=True)
