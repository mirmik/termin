"""Project settings dialog — configure render sync mode."""

from __future__ import annotations

from typing import Callable

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.combo_box import ComboBox


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

    combo.on_selection_changed = _on_changed
    row.add_child(combo)
    content.add_child(row)

    dlg = Dialog()
    dlg.title = "Project Settings"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.min_width = 350

    dlg.show(ui)
