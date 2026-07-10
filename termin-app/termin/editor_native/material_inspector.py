"""Native projection of the shared material inspector controller."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Callable
import weakref

from termin.editor_core.inspector_resources import InspectorResourceCatalog
from termin.editor_core.material_inspector_model import (
    MaterialInspectorController,
    MaterialInspectorSnapshot,
    MaterialPropertySnapshot,
    material_vector,
)
from termin.editor_core.material_texture_sources import MaterialTextureSourceCatalog
from termin.gui_native import Document, EdgeInsets, Size, WidgetRef

from .inspector_fields import ColorDialogHandler


_logger = logging.getLogger(__name__)


@dataclass
class NativeMaterialInspector:
    document: Document
    controller: MaterialInspectorController
    root: WidgetRef
    request_render: Callable[[], None]
    resource_catalog: InspectorResourceCatalog
    texture_sources: MaterialTextureSourceCatalog
    show_color_dialog: ColorDialogHandler | None = None
    controls: dict[str, object] = field(default_factory=dict)

    def set_target(self, material) -> None:
        self.rebuild(self.controller.set_target(material))

    def refresh(self) -> None:
        self.rebuild(self.controller.refresh())

    def rebuild(self, snapshot: MaterialInspectorSnapshot) -> None:
        for child in tuple(self.root.children):
            if not self.document.destroy_widget_recursive(child.handle):
                _logger.error("Failed to destroy native material inspector row: %s", child.debug_name)
        self.controls.clear()
        if not snapshot.has_material:
            self.root.add_fixed_child(self.document.create_label(snapshot.message, "native-material-empty"), 26.0)
            self.root.preferred_size = Size(300.0, 26.0)
            self.request_render()
            return

        self._append_text_row("Name", snapshot.name, self.controller.set_name, "name")
        self._append_label_row("UUID", snapshot.uuid or "—", "uuid")
        self._append_shader_row(snapshot)
        self._append_label_row("Phases", str(snapshot.phase_count), "phases")
        if snapshot.message:
            self.root.add_fixed_child(self.document.create_label(snapshot.message, "native-material-message"), 26.0)
        for prop in snapshot.properties:
            self._append_property(prop)
        row_count = 4 + len(snapshot.properties) + (1 if snapshot.message else 0)
        self.root.preferred_size = Size(300.0, float(row_count * 30))
        self.request_render()

    def _row(self, key: str, label_text: str) -> WidgetRef:
        row = self.document.create_hstack(f"native-material-row-{key}")
        row.set_layout_spacing(4.0)
        row.set_layout_padding(EdgeInsets(0.0, 1.0, 0.0, 1.0))
        label = self.document.create_label(label_text, f"native-material-label-{key}")
        row.add_fixed_child(label, 110.0)
        return row

    def _append_text_row(self, label: str, value: str, submit, key: str) -> None:
        row = self._row(key, label)
        editor = self.document.create_text_input(value)
        editor.connect_submitted(lambda text: self._mutate(lambda: submit(text)))
        row.add_stretch_child(editor.widget)
        self.root.add_fixed_child(row, 28.0)
        self.controls[key] = editor

    def _append_label_row(self, label: str, value: str, key: str) -> None:
        row = self._row(key, label)
        value_label = self.document.create_label(value, f"native-material-value-{key}")
        row.add_stretch_child(value_label)
        self.root.add_fixed_child(row, 28.0)
        self.controls[key] = value_label

    def _append_shader_row(self, snapshot: MaterialInspectorSnapshot) -> None:
        row = self._row("shader", "Shader")
        combo = self.document.create_combo_box()
        selected = -1
        for index, name in enumerate(snapshot.shader_choices):
            combo.add_item(name)
            if name == snapshot.shader_name:
                selected = index
        combo.selected_index = selected
        weak_owner = weakref.ref(self)

        def changed(index: int, _text: str) -> None:
            owner = weak_owner()
            if owner is not None and 0 <= index < len(snapshot.shader_choices):
                owner._mutate(lambda: owner.controller.set_shader(snapshot.shader_choices[index]))

        combo.connect_changed(changed)
        row.add_stretch_child(combo.widget)
        self.root.add_fixed_child(row, 28.0)
        self.controls["shader"] = combo

    def _append_property(self, prop: MaterialPropertySnapshot) -> None:
        row = self._row(prop.name, prop.label)
        control = self._property_control(prop)
        row.add_stretch_child(control)
        self.root.add_fixed_child(row, 28.0)

    def _property_control(self, prop: MaterialPropertySnapshot) -> WidgetRef:
        weak_owner = weakref.ref(self)
        if prop.kind == "Bool":
            checkbox = self.document.create_checkbox(bool(prop.value))
            checkbox.connect_changed(lambda value: self._mutate(lambda: self.controller.set_property(prop.name, value)))
            self.controls[prop.name] = checkbox
            return checkbox.widget
        if prop.kind in ("Float", "Int"):
            box = self.document.create_spin_box(float(prop.value or 0.0))
            box.set_range(
                -1.0e6 if prop.minimum is None else prop.minimum,
                1.0e6 if prop.maximum is None else prop.maximum,
            )
            box.step = 1.0 if prop.kind == "Int" else 0.1
            box.decimals = 0 if prop.kind == "Int" else 3
            box.connect_changed(lambda value: self._mutate(lambda: self.controller.set_property(prop.name, value)))
            self.controls[prop.name] = box
            return box.widget
        if prop.kind in ("Vec2", "Vec3", "Vec4"):
            size = {"Vec2": 2, "Vec3": 3, "Vec4": 4}[prop.kind]
            values = material_vector(prop.value, size)
            vector_row = self.document.create_hstack(f"native-material-vector-{prop.name}")
            vector_row.set_layout_spacing(2.0)
            boxes = []
            for component in values:
                box = self.document.create_spin_box(component)
                box.set_range(-1.0e6, 1.0e6)
                box.step = 0.05
                box.decimals = 4
                vector_row.add_stretch_child(box.widget)
                boxes.append(box)
            controls = tuple(boxes)

            def changed(_value: float) -> None:
                owner = weak_owner()
                if owner is not None:
                    owner._mutate(lambda: owner.controller.set_property(prop.name, [box.value for box in controls]))

            for box in controls:
                box.connect_changed(changed)
            self.controls[prop.name] = controls
            return vector_row
        if prop.kind == "Color":
            color = material_vector(prop.value, 4, color=True)
            button = self.document.create_button(
                ", ".join(f"{component:.2f}" for component in color),
                f"native-material-color-{prop.name}",
            )

            def clicked() -> None:
                owner = weak_owner()
                if owner is None:
                    return
                if owner.show_color_dialog is None:
                    _logger.error("No color dialog service for material property '%s'", prop.name)
                    return

                def finished(value: tuple[float, ...] | None) -> None:
                    current = weak_owner()
                    if current is not None and value is not None:
                        current._mutate(lambda: current.controller.set_property(prop.name, value))

                owner.show_color_dialog(color, finished)

            button.connect_clicked(clicked)
            self.controls[prop.name] = button
            return button.widget
        if prop.kind in ("Texture", "Texture2D") and prop.texture is not None:
            choices = self.texture_sources.choices(prop.texture.default_kind)
            combo = self.document.create_combo_box()
            selected = 0
            for index, choice in enumerate(choices):
                combo.add_item(choice.label)
                if choice.tag == prop.texture.tag and choice.name == prop.texture.name:
                    selected = index
            combo.selected_index = selected

            def changed(index: int, _text: str) -> None:
                owner = weak_owner()
                if owner is None or not (0 <= index < len(choices)):
                    return
                choice = choices[index]
                owner._mutate(
                    lambda: owner.controller.set_texture(
                        prop.name,
                        choice.tag,
                        choice.name,
                        default_kind=prop.texture.default_kind,
                    )
                )

            combo.connect_changed(changed)
            self.controls[prop.name] = combo
            return combo.widget
        label = self.document.create_label(str(prop.value), f"native-material-unsupported-{prop.name}")
        label.enabled = False
        self.controls[prop.name] = label
        return label

    def _mutate(self, mutation: Callable[[], MaterialInspectorSnapshot]) -> None:
        self.rebuild(mutation())


def build_native_material_inspector(
    document: Document,
    controller: MaterialInspectorController,
    *,
    request_render: Callable[[], None],
    resource_catalog: InspectorResourceCatalog,
    show_color_dialog: ColorDialogHandler | None = None,
    texture_sources: MaterialTextureSourceCatalog | None = None,
) -> NativeMaterialInspector:
    sources = texture_sources or MaterialTextureSourceCatalog(resource_catalog.resource_manager)
    controller.set_render_target_texture_resolver(sources.resolve_render_target)
    root = document.create_vstack("native-material-inspector")
    root.set_layout_spacing(2.0)
    return NativeMaterialInspector(
        document,
        controller,
        root,
        request_render,
        resource_catalog,
        sources,
        show_color_dialog,
    )


__all__ = ["NativeMaterialInspector", "build_native_material_inspector"]
