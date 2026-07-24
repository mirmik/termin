"""Native projections for toolkit-neutral project resource inspectors."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Callable
import weakref

from termin.editor_core.resource_inspector_models import (
    GlbInspectorController,
    GlbInspectorSnapshot,
    MeshInspectorController,
    MeshInspectorSnapshot,
    TextureInspectorController,
    TextureInspectorSnapshot,
)
from termin.gui_native import Color, TcDocument, EdgeInsets, Size, WidgetRef
from termin.editor_native.metrics import EDITOR_UI_METRICS


_logger = logging.getLogger(__name__)
PreviewHandler = Callable[[object, object], Callable[[], None]]


def _clear(document: TcDocument, root: WidgetRef, controls: dict[str, object]) -> None:
    for child in tuple(root.children):
        if not document.destroy_widget_recursive(child.handle):
            _logger.error("Failed to destroy resource inspector row: %s", child.debug_name)
    controls.clear()


def _row(document: TcDocument, label: str, key: str) -> WidgetRef:
    row = document.create_hstack(f"native-resource-row-{key}")
    row.set_layout_spacing(4.0)
    row.set_layout_padding(EdgeInsets(0.0, 1.0, 0.0, 1.0))
    row.add_fixed_child(
        document.create_label(label, f"native-resource-label-{key}"),
        EDITOR_UI_METRICS.inspector_label,
    )
    return row


def _label_row(
    document: TcDocument,
    root: WidgetRef,
    controls: dict[str, object],
    label: str,
    value: str,
    key: str,
) -> None:
    row = _row(document, label, key)
    control = document.create_label(value or "—", f"native-resource-value-{key}")
    row.add_stretch_child(control)
    root.add_fixed_child(row, 28.0)
    controls[key] = control


def _checkbox_row(
    document: TcDocument,
    root: WidgetRef,
    controls: dict[str, object],
    label: str,
    value: bool,
    key: str,
) -> object:
    row = _row(document, label, key)
    control = document.create_checkbox(value)
    row.add_fixed_child(control.widget, 24.0)
    row.add_stretch_child(document.create_label("", f"native-resource-spacer-{key}"))
    root.add_fixed_child(row, 28.0)
    controls[key] = control
    return control


@dataclass
class NativeTextureInspector:
    document: TcDocument
    controller: TextureInspectorController
    root: WidgetRef
    request_render: Callable[[], None]
    show_preview: PreviewHandler | None = None
    controls: dict[str, object] = field(default_factory=dict)
    _release_preview: Callable[[], None] | None = None

    def set_target(self, target, *, name: str = "", file_path: str | None = None) -> None:
        self.rebuild(self.controller.set_target(target, name=name, file_path=file_path))

    def rebuild(self, snapshot: TextureInspectorSnapshot) -> None:
        if self._release_preview is not None:
            self._release_preview()
            self._release_preview = None
        _clear(self.document, self.root, self.controls)
        if not snapshot.available:
            self.root.add_fixed_child(self.document.create_label(snapshot.message), 28.0)
            self.root.preferred_size = Size(300.0, 28.0)
            self.request_render()
            return
        preview_box = self.document.create_hstack("native-texture-preview-box")
        preview_box.set_layout_background(Color(0.08, 0.09, 0.11, 1.0))
        image = self.document.create_image_widget()
        image.set_preserve_aspect(True)
        preview_box.add_stretch_child(image.widget)
        self.root.add_fixed_child(preview_box, 160.0)
        if self.show_preview is not None and snapshot.preview_pixels is not None:
            self._release_preview = self.show_preview(image, snapshot.preview_pixels)
        for label, value, key in (
            ("Name", snapshot.name, "name"),
            ("UUID", snapshot.uuid, "uuid"),
            ("Resolution", snapshot.resolution, "resolution"),
            ("Channels", snapshot.channels, "channels"),
            ("File size", snapshot.file_size, "file-size"),
            ("Path", snapshot.path, "path"),
        ):
            _label_row(self.document, self.root, self.controls, label, value, key)
        flip_x = _checkbox_row(self.document, self.root, self.controls, "Flip X", snapshot.flip_x, "flip-x")
        flip_y = _checkbox_row(self.document, self.root, self.controls, "Flip Y", snapshot.flip_y, "flip-y")
        transpose = _checkbox_row(
            self.document, self.root, self.controls, "Transpose", snapshot.transpose, "transpose"
        )
        owner = weakref.ref(self)

        def changed(_value: bool) -> None:
            current = owner()
            if current is not None:
                current.rebuild(
                    current.controller.save_import_settings(
                        flip_x=flip_x.checked,
                        flip_y=flip_y.checked,
                        transpose=transpose.checked,
                    )
                )

        flip_x.connect_changed(changed)
        flip_y.connect_changed(changed)
        transpose.connect_changed(changed)
        self.root.preferred_size = Size(300.0, 160.0 + 9.0 * 28.0)
        self.request_render()


@dataclass
class NativeMeshInspector:
    document: TcDocument
    controller: MeshInspectorController
    root: WidgetRef
    request_render: Callable[[], None]
    controls: dict[str, object] = field(default_factory=dict)

    def set_target(self, target, *, name: str = "", file_path: str | None = None) -> None:
        self.rebuild(self.controller.set_target(target, name=name, file_path=file_path))

    def rebuild(self, snapshot: MeshInspectorSnapshot) -> None:
        _clear(self.document, self.root, self.controls)
        if not snapshot.available:
            self.root.add_fixed_child(self.document.create_label(snapshot.message), 28.0)
            self.request_render()
            return
        for label, value, key in (
            ("Name", snapshot.name, "name"),
            ("UUID", snapshot.uuid, "uuid"),
            ("Vertices", snapshot.vertices, "vertices"),
            ("Triangles", snapshot.triangles, "triangles"),
            ("File size", snapshot.file_size, "file-size"),
            ("Path", snapshot.path, "path"),
        ):
            _label_row(self.document, self.root, self.controls, label, value, key)
        scale_row = _row(self.document, "Scale", "scale")
        scale = self.document.create_spin_box(snapshot.scale)
        scale.set_range(0.0001, 10000.0)
        scale.decimals = 4
        scale.step = 0.1
        scale_row.add_stretch_child(scale.widget)
        self.root.add_fixed_child(scale_row, 28.0)
        self.controls["scale"] = scale
        axes = []
        for label, value, key in (
            ("Axis X", snapshot.axis_x, "axis-x"),
            ("Axis Y", snapshot.axis_y, "axis-y"),
            ("Axis Z", snapshot.axis_z, "axis-z"),
        ):
            row = _row(self.document, label, key)
            combo = self.document.create_combo_box()
            for choice in self.controller.AXIS_CHOICES:
                combo.add_item(choice)
            combo.selected_index = self.controller.AXIS_CHOICES.index(value)
            row.add_stretch_child(combo.widget)
            self.root.add_fixed_child(row, 28.0)
            self.controls[key] = combo
            axes.append(combo)
        flip = _checkbox_row(
            self.document, self.root, self.controls, "Flip UV V", snapshot.flip_uv_v, "flip-uv-v"
        )
        actions = self.document.create_hstack("native-mesh-actions")
        actions.set_layout_spacing(4.0)
        defaults = self.document.create_button("Defaults")
        apply = self.document.create_button("Apply & Save")
        actions.add_fixed_child(defaults.widget, 84.0)
        actions.add_fixed_child(apply.widget, 112.0)
        actions.add_stretch_child(self.document.create_label(""))
        self.root.add_fixed_child(actions, 28.0)
        self.controls.update(defaults=defaults, apply=apply)
        owner = weakref.ref(self)

        def reset() -> None:
            current = owner()
            if current is not None:
                from termin.default_assets.mesh.mesh_spec import MeshSpec

                current.rebuild(
                    MeshInspectorSnapshot(
                        **{
                            **snapshot.__dict__,
                            "scale": MeshSpec().scale,
                            "axis_x": MeshSpec().axis_x,
                            "axis_y": MeshSpec().axis_y,
                            "axis_z": MeshSpec().axis_z,
                            "flip_uv_v": MeshSpec().flip_uv_v,
                        }
                    )
                )

        def save() -> None:
            current = owner()
            if current is not None:
                current.rebuild(
                    current.controller.save_import_settings(
                        scale=scale.value,
                        axis_x=axes[0].selected_text,
                        axis_y=axes[1].selected_text,
                        axis_z=axes[2].selected_text,
                        flip_uv_v=flip.checked,
                    )
                )

        defaults.connect_clicked(reset)
        apply.connect_clicked(save)
        self.root.preferred_size = Size(300.0, 12.0 * 28.0)
        self.request_render()


@dataclass
class NativeGlbInspector:
    document: TcDocument
    controller: GlbInspectorController
    root: WidgetRef
    request_render: Callable[[], None]
    controls: dict[str, object] = field(default_factory=dict)

    def set_target(self, target, *, name: str = "", file_path: str | None = None) -> None:
        self.rebuild(self.controller.set_target(target, name=name, file_path=file_path))

    def rebuild(self, snapshot: GlbInspectorSnapshot) -> None:
        _clear(self.document, self.root, self.controls)
        if not snapshot.available:
            self.root.add_fixed_child(self.document.create_label(snapshot.message), 28.0)
            self.request_render()
            return
        for label, value, key in (
            ("Name", snapshot.name, "name"),
            ("File size", snapshot.file_size, "file-size"),
            ("Path", snapshot.path, "path"),
            ("Meshes", snapshot.meshes, "meshes"),
            ("Textures", snapshot.textures, "textures"),
            ("Animations", snapshot.animations, "animations"),
        ):
            _label_row(self.document, self.root, self.controls, label, value, key)
        convert = _checkbox_row(
            self.document, self.root, self.controls, "Convert to Z-Up", snapshot.convert_to_z_up, "convert-z-up"
        )
        normalize = _checkbox_row(
            self.document, self.root, self.controls, "Normalize Scale", snapshot.normalize_scale, "normalize-scale"
        )
        blender = _checkbox_row(
            self.document, self.root, self.controls, "Blender Z-Up Fix", snapshot.blender_z_up_fix, "blender-fix"
        )
        apply = self.document.create_button("Apply & Reimport")
        self.root.add_fixed_child(apply.widget, 28.0)
        self.controls["apply"] = apply
        owner = weakref.ref(self)

        def save() -> None:
            current = owner()
            if current is not None:
                current.rebuild(
                    current.controller.save_import_settings(
                        convert_to_z_up=convert.checked,
                        normalize_scale=normalize.checked,
                        blender_z_up_fix=blender.checked,
                    )
                )

        apply.connect_clicked(save)
        self.root.preferred_size = Size(300.0, 10.0 * 28.0)
        self.request_render()


def build_native_resource_inspectors(
    document: TcDocument,
    *,
    resource_manager,
    request_render: Callable[[], None],
    changed: Callable[[], None] | None = None,
    show_texture_preview: PreviewHandler | None = None,
) -> tuple[NativeTextureInspector, NativeMeshInspector, NativeGlbInspector]:
    def root(name: str) -> WidgetRef:
        widget = document.create_vstack(name)
        widget.set_layout_spacing(2.0)
        return widget

    return (
        NativeTextureInspector(
            document,
            TextureInspectorController(resource_manager, changed=changed),
            root("native-texture-inspector"),
            request_render,
            show_texture_preview,
        ),
        NativeMeshInspector(
            document,
            MeshInspectorController(resource_manager, changed=changed),
            root("native-mesh-inspector"),
            request_render,
        ),
        NativeGlbInspector(
            document,
            GlbInspectorController(changed=changed),
            root("native-glb-inspector"),
            request_render,
        ),
    )


__all__ = [
    "NativeGlbInspector",
    "NativeMeshInspector",
    "NativeTextureInspector",
    "build_native_resource_inspectors",
]
