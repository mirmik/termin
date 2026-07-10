"""tcgui projection of the shared Quest/OpenXR build controller."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from tcgui.widgets.button import Button
from tcgui.widgets.dialog import Dialog
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack

from termin.editor_core.quest_openxr_build_model import QuestOpenXRBuildController


def show_quest_openxr_build_dialog(
    ui,
    project_root: str | Path,
    entry_scene: str | Path,
    output_dir: str | Path | None = None,
    on_log: Callable[[str], None] | None = None,
) -> None:
    """Show the shared Quest/OpenXR workflow in the temporary tcgui frontend."""
    controller = QuestOpenXRBuildController(
        project_root,
        entry_scene,
        output_dir,
        on_log=on_log,
        defer=ui.defer,
    )
    content = VStack()
    content.spacing = 8
    content.preferred_width = px(760)
    content.preferred_height = px(430)
    project_label = Label()
    scene_label = Label()
    status_label = Label()
    content.add_child(project_label)
    content.add_child(scene_label)
    content.add_child(status_label)
    actions = HStack()
    actions.spacing = 8
    content.add_child(actions)
    log_view = TextArea()
    log_view.read_only = True
    log_view.word_wrap = False
    log_view.preferred_height = px(300)
    log_view.stretch = True
    content.add_child(log_view)

    callbacks = (
        ("Build APK", controller.build_only),
        ("Install", controller.install_only),
        ("Launch", controller.launch_only),
        ("Build + Install", controller.build_install),
        ("Build + Install + Launch", controller.build_install_launch),
    )
    buttons = []
    for text, callback in callbacks:
        button = Button()
        button.text = text
        button.on_click = callback
        buttons.append(button)
        actions.add_child(button)

    def apply_snapshot(snapshot) -> None:
        project_label.text = f"Project: {snapshot.project_name}"
        scene_label.text = f"Entry scene: {snapshot.entry_scene}"
        status_label.text = snapshot.status
        log_view.text = snapshot.log_text
        for button in buttons:
            button.enabled = not snapshot.busy
        if status_label._ui is not None:
            status_label._ui.request_layout()

    controller.changed.connect(apply_snapshot)
    apply_snapshot(controller.snapshot)
    dialog = Dialog()
    dialog.title = "Quest/OpenXR Build"
    dialog.content = content
    dialog.buttons = ["Close"]
    dialog.default_button = "Close"
    dialog.cancel_button = "Close"
    dialog.min_width = 800
    dialog.show(ui, windowed=True)


__all__ = ["show_quest_openxr_build_dialog"]
