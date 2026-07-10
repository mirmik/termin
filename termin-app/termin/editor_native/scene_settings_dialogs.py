"""Native scene properties, layers and shadow settings dialogs."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable
import weakref

from termin.editor_core.scene_settings_model import (
    SHADOW_METHODS,
    SKYBOX_TYPES,
    SceneNamesController,
    SceneNamesSnapshot,
    ScenePropertiesController,
    ScenePropertiesSnapshot,
    ShadowSettingsController,
    ShadowSettingsSnapshot,
)
from termin.gui_native import DialogAction, Document, EdgeInsets, Rect, Size, WidgetRef

from .dialog_service import NativeDialogService


_logger = logging.getLogger(__name__)


def _ref(document: Document, reference) -> WidgetRef:
    return reference if isinstance(reference, WidgetRef) else document.ref(reference.handle)


def _row(document: Document, label: str, control, *, label_width: float = 130.0) -> WidgetRef:
    row = document.create_hstack(f"scene-settings-{label.lower().replace(' ', '-')}")
    row.set_layout_spacing(4.0)
    row.add_fixed_child(document.create_label(label), label_width)
    row.add_stretch_child(_ref(document, control))
    return row


def _lines(text: str) -> tuple[str, ...]:
    values = text.split("\n")[:64]
    values.extend("" for _ in range(64 - len(values)))
    return tuple(values)


def _set_combo_items(combo, items) -> None:
    combo.clear()
    for item in items:
        combo.add_item(str(item))


@dataclass
class NativeSceneNamesDialog:
    document: Document
    controller: SceneNamesController
    dialog: object
    layers: object
    flags: object
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native scene names dialog is closed")
        if self.dialog.open:
            return False
        snapshot = self.controller.load()
        self.layers.text = "\n".join(snapshot.layers)
        self.flags.text = "\n".join(snapshot.flags)
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def save(self) -> SceneNamesSnapshot:
        snapshot = self.controller.save(
            SceneNamesSnapshot(_lines(self.layers.text), _lines(self.flags.text))
        )
        self.request_render()
        return snapshot

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.dialog.open:
            self.dialog.close()
        if self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)


@dataclass
class NativeShadowSettingsDialog:
    document: Document
    controller: ShadowSettingsController
    dialog: object
    method: object
    softness: object
    bias: object
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    _updating: bool = False
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native shadow settings dialog is closed")
        if self.dialog.open:
            return False
        self.apply_snapshot(self.controller.load())
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def apply_snapshot(self, snapshot: ShadowSettingsSnapshot) -> None:
        self._updating = True
        try:
            self.method.selected_index = snapshot.method
            self.softness.value = snapshot.softness
            self.bias.value = snapshot.bias
        finally:
            self._updating = False

    def apply_controls(self) -> None:
        if self._updating:
            return
        snapshot = self.controller.apply(
            ShadowSettingsSnapshot(self.method.selected_index, self.softness.value, self.bias.value)
        )
        self.apply_snapshot(snapshot)
        self.request_render()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.dialog.open:
            self.dialog.close()
        if self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)


@dataclass
class NativeScenePropertiesDialog:
    document: Document
    controller: ScenePropertiesController
    dialog_service: NativeDialogService
    dialog: object
    background: object
    ambient: object
    intensity: object
    skybox_type: object
    skybox_color: object
    skybox_top: object
    skybox_bottom: object
    pipelines: object
    available: object
    remove_pipeline: object
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    snapshot: ScenePropertiesSnapshot | None = None
    _updating: bool = False
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native scene properties dialog is closed")
        if self.dialog.open:
            return False
        self.apply_snapshot(self.controller.load())
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def apply_snapshot(self, snapshot: ScenePropertiesSnapshot) -> None:
        self.snapshot = snapshot
        self._updating = True
        try:
            self.background.set_text(_color_text(snapshot.background_color))
            self.ambient.set_text(_color_text(snapshot.ambient_color))
            self.intensity.value = snapshot.ambient_intensity
            _set_combo_items(self.skybox_type, (item.title() for item in SKYBOX_TYPES))
            self.skybox_type.selected_index = SKYBOX_TYPES.index(snapshot.skybox_type)
            self.skybox_color.set_text(_color_text(snapshot.skybox_color))
            self.skybox_top.set_text(_color_text(snapshot.skybox_top_color))
            self.skybox_bottom.set_text(_color_text(snapshot.skybox_bottom_color))
            _set_combo_items(self.pipelines, (
                f"{item.name} ({item.uuid[:8]}...)" if item.valid else item.name
                for item in snapshot.pipelines
            ))
            self.pipelines.selected_index = 0 if snapshot.pipelines else -1
            _set_combo_items(self.available, snapshot.available_pipelines)
            self.available.selected_index = 0 if snapshot.available_pipelines else -1
            self.remove_pipeline.widget.enabled = bool(snapshot.pipelines)
        finally:
            self._updating = False
        self.request_render()

    def pick_color(self, field: str) -> None:
        if self.snapshot is None:
            return
        colors = {
            "background": self.snapshot.background_color,
            "ambient": self.snapshot.ambient_color + (1.0,),
            "skybox": self.snapshot.skybox_color + (1.0,),
            "skybox_top": self.snapshot.skybox_top_color + (1.0,),
            "skybox_bottom": self.snapshot.skybox_bottom_color + (1.0,),
        }
        initial = colors[field]
        weak_self = weakref.ref(self)

        def selected(value) -> None:
            owner = weak_self()
            if owner is None or value is None:
                return
            if field == "background":
                snapshot = owner.controller.set_background_color(value)
            elif field == "ambient":
                snapshot = owner.controller.set_ambient_color(value)
            elif field == "skybox":
                snapshot = owner.controller.set_skybox_color(value)
            elif field == "skybox_top":
                snapshot = owner.controller.set_skybox_top_color(value)
            else:
                snapshot = owner.controller.set_skybox_bottom_color(value)
            owner.apply_snapshot(snapshot)

        self.dialog_service.show_color(initial, selected, show_alpha=False)

    def set_intensity(self, value: float) -> None:
        if not self._updating:
            self.apply_snapshot(self.controller.set_ambient_intensity(value))

    def set_skybox_type(self, index: int) -> None:
        if not self._updating and 0 <= index < len(SKYBOX_TYPES):
            self.apply_snapshot(self.controller.set_skybox_type(SKYBOX_TYPES[index]))

    def add_selected_pipeline(self) -> None:
        if self.snapshot is None:
            return
        index = self.available.selected_index
        if 0 <= index < len(self.snapshot.available_pipelines):
            self.apply_snapshot(self.controller.add_pipeline(self.snapshot.available_pipelines[index]))

    def remove_selected_pipeline(self) -> None:
        if self.snapshot is None:
            return
        index = self.pipelines.selected_index
        if 0 <= index < len(self.snapshot.pipelines):
            self.apply_snapshot(self.controller.remove_pipeline(index))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.dialog.open:
            self.dialog.close()
        if self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)


def _color_text(value) -> str:
    return ", ".join(f"{float(component):.2f}" for component in value[:3])


def build_native_scene_names_dialog(document, controller, *, viewport, request_render):
    root = document.create_hstack("native-scene-names")
    root.stable_id = "editor.scene-names"
    root.preferred_size = Size(760.0, 560.0)
    root.set_layout_padding(EdgeInsets(6.0, 6.0, 6.0, 6.0))
    root.set_layout_spacing(8.0)
    columns = []
    for title in ("Layers (0-63)", "Flags (0-63)"):
        column = document.create_vstack(f"scene-names-{title[:5].lower()}")
        column.add_fixed_child(document.create_label(title), 24.0)
        area = document.create_text_area()
        column.add_stretch_child(_ref(document, area))
        root.add_stretch_child(column)
        columns.append(area)
    dialog = document.create_dialog("Layers & Flags")
    dialog.actions = [
        DialogAction("ok", "OK", is_default=True),
        DialogAction("cancel", "Cancel", is_cancel=True),
    ]
    dialog.set_content(root)
    result = NativeSceneNamesDialog(
        document, controller, dialog, columns[0], columns[1], viewport, request_render
    )
    weak_result = weakref.ref(result)

    def finished(value) -> None:
        owner = weak_result()
        if owner is not None and value.action_id == "ok":
            owner.save()

    dialog.connect_finished(finished)
    return result


def build_native_shadow_settings_dialog(document, controller, *, viewport, request_render):
    root = document.create_vstack("native-shadow-settings")
    root.stable_id = "editor.shadow-settings"
    root.preferred_size = Size(440.0, 260.0)
    root.set_layout_padding(EdgeInsets(8.0, 8.0, 8.0, 8.0))
    root.set_layout_spacing(6.0)
    method = document.create_combo_box()
    _set_combo_items(method, SHADOW_METHODS)
    root.add_fixed_child(_row(document, "Method", method), 30.0)
    softness = document.create_spin_box()
    softness.set_range(0.0, 10.0)
    softness.step = 0.1
    softness.decimals = 2
    root.add_fixed_child(_row(document, "Softness", softness), 30.0)
    bias = document.create_spin_box()
    bias.set_range(0.0, 0.05)
    bias.step = 0.0001
    bias.decimals = 5
    root.add_fixed_child(_row(document, "Receiver Bias", bias), 30.0)
    dialog = document.create_dialog("Shadow Settings")
    dialog.actions = [DialogAction("close", "Close", is_default=True, is_cancel=True)]
    dialog.set_content(root)
    result = NativeShadowSettingsDialog(
        document, controller, dialog, method, softness, bias, viewport, request_render
    )
    weak_result = weakref.ref(result)
    method.connect_changed(
        lambda _index, _text: weak_result().apply_controls() if weak_result() is not None else None
    )
    softness.connect_changed(
        lambda _value: weak_result().apply_controls() if weak_result() is not None else None
    )
    bias.connect_changed(
        lambda _value: weak_result().apply_controls() if weak_result() is not None else None
    )
    return result


def build_native_scene_properties_dialog(
    document,
    controller,
    *,
    dialog_service,
    viewport,
    request_render,
):
    root = document.create_vstack("native-scene-properties")
    root.stable_id = "editor.scene-properties"
    root.preferred_size = Size(600.0, 570.0)
    root.set_layout_padding(EdgeInsets(8.0, 8.0, 8.0, 8.0))
    root.set_layout_spacing(5.0)
    background = document.create_button("Background")
    ambient = document.create_button("Ambient")
    intensity = document.create_spin_box()
    intensity.set_range(0.0, 10.0)
    intensity.step = 0.01
    intensity.decimals = 3
    skybox_type = document.create_combo_box()
    skybox_color = document.create_button("Skybox Color")
    skybox_top = document.create_button("Skybox Top")
    skybox_bottom = document.create_button("Skybox Bottom")
    for label, control in (
        ("Background", background),
        ("Ambient", ambient),
        ("Ambient Intensity", intensity),
        ("Skybox Type", skybox_type),
        ("Skybox Color", skybox_color),
        ("Gradient Top", skybox_top),
        ("Gradient Bottom", skybox_bottom),
    ):
        root.add_fixed_child(_row(document, label, control), 30.0)
    root.add_fixed_child(document.create_label("Scene Pipelines"), 24.0)
    pipelines = document.create_combo_box()
    root.add_fixed_child(_ref(document, pipelines), 30.0)
    pipeline_row = document.create_hstack("scene-pipeline-actions")
    pipeline_row.set_layout_spacing(4.0)
    available = document.create_combo_box()
    pipeline_row.add_stretch_child(_ref(document, available))
    add_pipeline = document.create_button("Add")
    pipeline_row.add_fixed_child(_ref(document, add_pipeline), 66.0)
    remove_pipeline = document.create_button("Remove")
    pipeline_row.add_fixed_child(_ref(document, remove_pipeline), 78.0)
    root.add_fixed_child(pipeline_row, 30.0)
    dialog = document.create_dialog("Scene Properties")
    dialog.actions = [DialogAction("close", "Close", is_default=True, is_cancel=True)]
    dialog.set_content(root)
    result = NativeScenePropertiesDialog(
        document,
        controller,
        dialog_service,
        dialog,
        background,
        ambient,
        intensity,
        skybox_type,
        skybox_color,
        skybox_top,
        skybox_bottom,
        pipelines,
        available,
        remove_pipeline,
        viewport,
        request_render,
    )
    weak_result = weakref.ref(result)

    def owner() -> NativeScenePropertiesDialog | None:
        return weak_result()

    for button, field in (
        (background, "background"),
        (ambient, "ambient"),
        (skybox_color, "skybox"),
        (skybox_top, "skybox_top"),
        (skybox_bottom, "skybox_bottom"),
    ):
        button.connect_clicked(
            lambda selected=field: owner().pick_color(selected) if owner() is not None else None
        )
    intensity.connect_changed(
        lambda value: owner().set_intensity(value) if owner() is not None else None
    )
    skybox_type.connect_changed(
        lambda index, _text: owner().set_skybox_type(index) if owner() is not None else None
    )
    add_pipeline.connect_clicked(
        lambda: owner().add_selected_pipeline() if owner() is not None else None
    )
    remove_pipeline.connect_clicked(
        lambda: owner().remove_selected_pipeline() if owner() is not None else None
    )
    return result


def connect_scene_settings_command(menu_bar, command_id: int, dialog) -> None:
    weak_dialog = weakref.ref(dialog)

    def activated(_menu_index: int, activated_id: int, _command) -> None:
        owner = weak_dialog()
        if activated_id == command_id and owner is not None:
            owner.show()

    menu_bar.connect_activated(activated)


__all__ = [
    "NativeSceneNamesDialog",
    "NativeScenePropertiesDialog",
    "NativeShadowSettingsDialog",
    "build_native_scene_names_dialog",
    "build_native_scene_properties_dialog",
    "build_native_shadow_settings_dialog",
    "connect_scene_settings_command",
]
