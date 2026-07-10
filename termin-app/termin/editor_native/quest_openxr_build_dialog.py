"""Native Quest/OpenXR build and deploy dialog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import weakref

from termin.editor_core.quest_openxr_build_model import QuestOpenXRBuildController
from termin.gui_native import DialogAction, Document, EdgeInsets, Rect, Size


@dataclass
class NativeQuestOpenXRBuildDialog:
    document: Document
    dialog: object
    project_label: object
    scene_label: object
    status: object
    log_view: object
    action_buttons: tuple[object, ...]
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    controller: QuestOpenXRBuildController | None = None
    _closed: bool = False

    def show_entry(self, entry, *, on_log: Callable[[str], None] | None = None) -> bool:
        if self._closed:
            raise RuntimeError("native Quest/OpenXR build dialog is closed")
        if self.dialog.open:
            return False
        if self.controller is not None:
            self.controller.changed.disconnect(self.apply_snapshot)
        self.controller = QuestOpenXRBuildController(
            entry.project_root,
            entry.scene_rel_path,
            entry.output_dir,
            on_log=on_log,
        )
        self.controller.changed.connect(self.apply_snapshot)
        self.apply_snapshot(self.controller.snapshot)
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def apply_snapshot(self, snapshot) -> None:
        self.project_label.text = f"Project: {snapshot.project_name}"
        self.scene_label.text = f"Entry scene: {snapshot.entry_scene}"
        self.status.text = snapshot.status
        self.log_view.text = snapshot.log_text
        for button in self.action_buttons:
            button.widget.enabled = not snapshot.busy
        self.request_render()

    def poll(self) -> int:
        if self.controller is None:
            return 0
        return self.controller.process_pending()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.controller is not None:
            self.controller.changed.disconnect(self.apply_snapshot)
        if self.dialog.open:
            self.dialog.close()
        if self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)


def build_native_quest_openxr_build_dialog(
    document: Document,
    *,
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
) -> NativeQuestOpenXRBuildDialog:
    root = document.create_vstack("native-quest-openxr-build")
    root.preferred_size = Size(780.0, 470.0)
    root.set_layout_padding(EdgeInsets(8.0, 8.0, 8.0, 8.0))
    root.set_layout_spacing(6.0)
    project_label = document.create_status_bar("Project:")
    scene_label = document.create_status_bar("Entry scene:")
    status = document.create_status_bar("Idle")
    root.add_fixed_child(project_label.widget, 24.0)
    root.add_fixed_child(scene_label.widget, 24.0)
    root.add_fixed_child(status.widget, 24.0)

    actions = document.create_hstack("native-quest-openxr-actions")
    actions.set_layout_spacing(4.0)
    button_labels = (
        "Build APK",
        "Install",
        "Launch",
        "Build + Install",
        "Build + Install + Launch",
    )
    buttons = []
    for label in button_labels:
        button = document.create_button(label)
        actions.add_stretch_child(button.widget)
        buttons.append(button)
    root.add_fixed_child(actions, 34.0)
    log_view = document.create_text_area()
    log_view.widget.enabled = False
    root.add_stretch_child(log_view.widget)

    dialog = document.create_dialog("Quest/OpenXR Build")
    dialog.actions = [DialogAction("close", "Close", is_default=True, is_cancel=True)]
    dialog.set_content(root)
    result = NativeQuestOpenXRBuildDialog(
        document,
        dialog,
        project_label,
        scene_label,
        status,
        log_view,
        tuple(buttons),
        viewport,
        request_render,
    )
    weak_result = weakref.ref(result)

    actions_callbacks = (
        lambda controller: controller.build_only(),
        lambda controller: controller.install_only(),
        lambda controller: controller.launch_only(),
        lambda controller: controller.build_install(),
        lambda controller: controller.build_install_launch(),
    )
    for button, callback in zip(buttons, actions_callbacks, strict=True):
        def clicked(callback=callback) -> None:
            owner = weak_result()
            if owner is None or owner.controller is None:
                return
            callback(owner.controller)

        button.connect_clicked(clicked)
    return result


__all__ = ["NativeQuestOpenXRBuildDialog", "build_native_quest_openxr_build_dialog"]
