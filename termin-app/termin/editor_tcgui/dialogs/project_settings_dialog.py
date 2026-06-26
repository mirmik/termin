"""Project settings dialog - configure project-level editor and player settings."""

from __future__ import annotations

from typing import Callable

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.units import px


def show_project_settings_dialog(
    ui,
    on_resource_settings_changed: Callable[[], None] | None = None,
    on_render_settings_changed: Callable[[], None] | None = None,
) -> None:
    """Show project settings dialog. Changes apply immediately."""
    from termin.project.settings import ProjectSettingsManager, RenderSyncMode

    manager = ProjectSettingsManager.instance()
    if manager is None or manager.project_path is None:
        from tcbase import log
        log.warn("No project open - cannot show project settings")
        return

    sync_modes = list(RenderSyncMode)
    mode_labels = [m.value.capitalize() for m in sync_modes]
    current_idx = sync_modes.index(manager.settings.render_sync_mode)

    def _resource_settings_snapshot() -> tuple[str, tuple[str, ...]]:
        return (
            manager.settings.build_output_dir,
            tuple(manager.settings.ignored_resource_paths),
        )

    def _notify_resource_settings_changed(before: tuple[str, tuple[str, ...]]) -> None:
        if _resource_settings_snapshot() != before and on_resource_settings_changed is not None:
            on_resource_settings_changed()

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

    def _on_render_sync_changed(idx: int) -> None:
        mode = sync_modes[idx]
        if manager.settings.render_sync_mode == mode:
            return
        manager.set_render_sync_mode(mode)
        if on_render_settings_changed is not None:
            on_render_settings_changed()

    combo.on_changed = lambda idx, _text: _on_render_sync_changed(idx)
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

    def _on_build_dir_changed(text: str) -> None:
        before = _resource_settings_snapshot()
        manager.set_build_output_dir(text)
        _notify_resource_settings_changed(before)

    build_dir_input.on_submit = _on_build_dir_changed
    build_row.add_child(build_dir_input)
    content.add_child(build_row)

    player_window_label = Label()
    player_window_label.text = "Player Window:"
    player_window_label.tooltip = "Default standalone player window used by Run Build and packaged desktop bundles."
    content.add_child(player_window_label)

    player_window_row = HStack()
    player_window_row.spacing = 8

    width_label = Label()
    width_label.text = "Width:"
    player_window_row.add_child(width_label)

    width_spin = SpinBox()
    width_spin.value = manager.settings.player_window.width
    width_spin.min_value = 1
    width_spin.max_value = 16384
    width_spin.step = 16
    width_spin.decimals = 0
    width_spin.preferred_width = px(96)
    player_window_row.add_child(width_spin)

    height_label = Label()
    height_label.text = "Height:"
    player_window_row.add_child(height_label)

    height_spin = SpinBox()
    height_spin.value = manager.settings.player_window.height
    height_spin.min_value = 1
    height_spin.max_value = 16384
    height_spin.step = 16
    height_spin.decimals = 0
    height_spin.preferred_width = px(96)
    player_window_row.add_child(height_spin)

    fullscreen_check = Checkbox()
    fullscreen_check.text = "Fullscreen"
    fullscreen_check.checked = manager.settings.player_window.fullscreen
    player_window_row.add_child(fullscreen_check)
    content.add_child(player_window_row)

    def _apply_player_window() -> None:
        manager.set_player_window(
            int(width_spin.value),
            int(height_spin.value),
            fullscreen_check.checked,
        )

    width_spin.on_changed = lambda _value: _apply_player_window()
    height_spin.on_changed = lambda _value: _apply_player_window()
    fullscreen_check.on_changed = lambda _checked: _apply_player_window()

    ignored_label = Label()
    ignored_label.text = "Ignored Resource Paths:"
    ignored_label.tooltip = "Project-relative files or directories excluded from resource scan, file watching, and build manifests."
    content.add_child(ignored_label)

    ignored_paths_input = TextArea()
    ignored_paths_input.text = "\n".join(manager.settings.ignored_resource_paths)
    ignored_paths_input.placeholder = "cache\nexternal/generated_assets"
    ignored_paths_input.preferred_width = px(320)
    ignored_paths_input.preferred_height = px(120)
    ignored_paths_input.word_wrap = False
    content.add_child(ignored_paths_input)

    def _ignored_paths_from_text(text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _apply_settings(_button: str) -> None:
        before = _resource_settings_snapshot()
        manager.set_build_output_dir(build_dir_input.text)
        manager.set_player_window(
            int(width_spin.value),
            int(height_spin.value),
            fullscreen_check.checked,
        )
        manager.set_ignored_resource_paths(_ignored_paths_from_text(ignored_paths_input.text))
        _notify_resource_settings_changed(before)

    dlg = Dialog()
    dlg.title = "Project Settings"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.on_result = _apply_settings
    dlg.min_width = 350

    dlg.show(ui, windowed=True)
