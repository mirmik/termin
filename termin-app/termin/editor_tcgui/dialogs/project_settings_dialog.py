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

from termin.editor_core.project_settings_model import (
    ProjectSettingsController,
    ProjectSettingsSnapshot,
    RENDER_SYNC_MODES,
)


def show_project_settings_dialog(
    ui,
    on_resource_settings_changed: Callable[[], None] | None = None,
    on_render_settings_changed: Callable[[], None] | None = None,
) -> None:
    """Show project settings dialog. Changes apply immediately."""
    from termin.project.settings import ProjectSettingsManager

    manager = ProjectSettingsManager.instance()
    if manager is None or manager.project_path is None:
        from tcbase import log
        log.warn("No project open - cannot show project settings")
        return

    controller = ProjectSettingsController(
        manager,
        on_resource_settings_changed=on_resource_settings_changed,
        on_render_settings_changed=on_render_settings_changed,
    )
    snapshot = controller.load()
    sync_modes = list(RENDER_SYNC_MODES)
    mode_labels = [m.value.capitalize() for m in sync_modes]
    current_idx = sync_modes.index(snapshot.render_sync_mode)

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
        controller.set_render_sync_mode(mode)

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
    build_dir_input.text = snapshot.build_output_dir
    build_dir_input.preferred_width = px(180)

    def _on_build_dir_changed(text: str) -> None:
        build_dir_input.text = text
        controller.save(_snapshot_from_controls())

    build_dir_input.on_submit = _on_build_dir_changed
    build_row.add_child(build_dir_input)
    content.add_child(build_row)

    application_id_input = TextInput()
    application_id_input.text = snapshot.application_id
    application_label_input = TextInput()
    application_label_input.text = snapshot.application_label
    version_code_spin = SpinBox()
    version_code_spin.value = snapshot.version_code
    version_code_spin.min_value = 1
    version_code_spin.max_value = 2_100_000_000
    version_code_spin.decimals = 0
    version_name_input = TextInput()
    version_name_input.text = snapshot.version_name
    for label_text, control in (
        ("Application ID:", application_id_input),
        ("Application Label:", application_label_input),
        ("Version Code:", version_code_spin),
        ("Version Name:", version_name_input),
    ):
        application_row = HStack()
        application_row.spacing = 8
        application_label = Label()
        application_label.text = label_text
        application_row.add_child(application_label)
        application_row.add_child(control)
        content.add_child(application_row)

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
    width_spin.value = snapshot.player_width
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
    height_spin.value = snapshot.player_height
    height_spin.min_value = 1
    height_spin.max_value = 16384
    height_spin.step = 16
    height_spin.decimals = 0
    height_spin.preferred_width = px(96)
    player_window_row.add_child(height_spin)

    fullscreen_check = Checkbox()
    fullscreen_check.text = "Fullscreen"
    fullscreen_check.checked = snapshot.player_fullscreen
    player_window_row.add_child(fullscreen_check)

    vsync_check = Checkbox()
    vsync_check.text = "VSync"
    vsync_check.checked = snapshot.player_vsync
    player_window_row.add_child(vsync_check)
    content.add_child(player_window_row)

    def _apply_player_window() -> None:
        controller.set_player_window(
            int(width_spin.value),
            int(height_spin.value),
            fullscreen_check.checked,
            vsync_check.checked,
        )

    width_spin.on_changed = lambda _value: _apply_player_window()
    height_spin.on_changed = lambda _value: _apply_player_window()
    fullscreen_check.on_changed = lambda _checked: _apply_player_window()
    vsync_check.on_changed = lambda _checked: _apply_player_window()

    ignored_label = Label()
    ignored_label.text = "Ignored Resource Paths:"
    ignored_label.tooltip = "Project-relative files or directories excluded from resource scan, file watching, and build manifests."
    content.add_child(ignored_label)

    ignored_paths_input = TextArea()
    ignored_paths_input.text = "\n".join(snapshot.ignored_resource_paths)
    ignored_paths_input.placeholder = "cache\nexternal/generated_assets"
    ignored_paths_input.preferred_width = px(320)
    ignored_paths_input.preferred_height = px(120)
    ignored_paths_input.word_wrap = False
    content.add_child(ignored_paths_input)

    phases_label = Label()
    phases_label.text = "Project Render Phases (bits 16-63):"
    phases_label.tooltip = "Exactly 48 indexed entries; blank lines reserve unused phase bits."
    content.add_child(phases_label)

    phases_input = TextArea()
    phases_input.text = "\n".join(snapshot.render_phase_names)
    phases_input.preferred_width = px(320)
    phases_input.preferred_height = px(160)
    phases_input.word_wrap = False
    content.add_child(phases_input)

    def _ignored_paths_from_text(text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _snapshot_from_controls() -> ProjectSettingsSnapshot:
        return ProjectSettingsSnapshot(
            render_sync_mode=sync_modes[combo.selected_index],
            build_output_dir=build_dir_input.text,
            application_id=application_id_input.text,
            application_label=application_label_input.text,
            version_code=int(version_code_spin.value),
            version_name=version_name_input.text,
            player_width=int(width_spin.value),
            player_height=int(height_spin.value),
            player_fullscreen=fullscreen_check.checked,
            player_vsync=vsync_check.checked,
            ignored_resource_paths=tuple(_ignored_paths_from_text(ignored_paths_input.text)),
            render_phase_names=tuple(phases_input.text.split("\n")),
        )

    def _apply_settings(_button: str) -> None:
        controller.save(_snapshot_from_controls())

    dlg = Dialog()
    dlg.title = "Project Settings"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.on_result = _apply_settings
    dlg.min_width = 350

    dlg.show(ui, windowed=True)
