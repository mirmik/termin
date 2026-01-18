"""
Generic panel for editing objects with inspect_fields.

This panel can be used for any object that has an `inspect_fields` class attribute,
including Components and RenderPasses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal

from termin.editor.inspect_field import InspectField
from termin.editor.widgets.field_widgets import (
    FieldWidget,
    FieldWidgetFactory,
    ButtonFieldWidget,
    ClipSelectorWidget,
)

if TYPE_CHECKING:
    from termin.visualization.core.resources import ResourceManager


def _collect_inspect_fields(obj: Any) -> dict[str, InspectField]:
    """Collect inspect_fields from InspectRegistry."""
    result = {}
    cls = obj.__class__
    type_name = cls.__name__

    try:
        from termin._native.inspect import InspectRegistry, TypeBackend
        registry = InspectRegistry.instance()

        # For Python types, collect from full class hierarchy
        if registry.has_type(type_name):
            backend = registry.get_type_backend(type_name)
            if backend == TypeBackend.Python:
                # Collect from MRO (base classes first, then subclasses override)
                for klass in reversed(cls.__mro__):
                    fields = getattr(klass, 'inspect_fields', None)
                    if fields:
                        for name, field in fields.items():
                            # Skip non-inspectable fields
                            if not field.is_inspectable:
                                continue
                            result[name] = field
                return result

        # For C++ types (and fallback), use InspectRegistry
        cpp_fields = registry.all_fields(type_name)
        for info in cpp_fields:
            # Skip non-inspectable fields (e.g. SERIALIZABLE_FIELD)
            if not info.is_inspectable:
                continue

            # Convert C++ EnumChoice list to Python tuple list
            choices = None
            if info.choices:
                choices = [(c.value, c.label) for c in info.choices]

            # Get action for button fields (None or callable)
            action = info.action if info.action is not None else None

            def make_getter(path):
                def getter(o):
                    return registry.get(o, path)
                return getter

            def make_setter(path):
                def setter(o, v):
                    registry.set(o, path, v)
                return setter

            result[info.path] = InspectField(
                path=info.path,
                label=info.label,
                kind=info.kind,
                min=info.min,
                max=info.max,
                step=info.step,
                choices=choices,
                action=action,
                getter=make_getter(info.path),
                setter=make_setter(info.path),
            )
    except (ImportError, RuntimeError):
        pass  # C++ module not available

    return result


class InspectFieldPanel(QWidget):
    """
    Generic panel for editing objects with inspect_fields.

    Usage:
        panel = InspectFieldPanel()
        panel.set_target(my_object)
        panel.field_changed.connect(on_change)
    """

    field_changed = pyqtSignal(str, object, object)  # field_key, old_value, new_value

    def __init__(
        self,
        resources: Optional["ResourceManager"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._target: Any = None
        self._fields: dict[str, InspectField] = {}
        self._widgets: dict[str, FieldWidget] = {}
        self._updating_from_model = False

        self._factory = FieldWidgetFactory(resources)

        layout = QFormLayout(self)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)
        self._layout = layout

    def set_resources(self, resources: "ResourceManager") -> None:
        """Set resource manager for material/mesh lookups."""
        self._factory.set_resources(resources)

    def set_scene_getter(self, getter) -> None:
        """Set callback for getting current scene (for layer_mask widget)."""
        self._factory.set_scene_getter(getter)

    def set_target(self, target: Any) -> None:
        """Set the object to inspect."""
        # Clear existing widgets
        for i in reversed(range(self._layout.count())):
            item = self._layout.itemAt(i)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        self._widgets.clear()
        self._target = target

        if target is None:
            return

        fields = _collect_inspect_fields(target)
        if not fields:
            return

        self._fields = fields
        self._updating_from_model = True

        try:
            for key, field in fields.items():
                widget = self._factory.create(field)
                self._widgets[key] = widget

                # Set target for widgets that need it
                if isinstance(widget, (ButtonFieldWidget, ClipSelectorWidget)):
                    widget.set_target(target)

                # Buttons span the full row, no separate label
                if field.kind == "button":
                    self._layout.addRow(widget)
                else:
                    label = field.label or key
                    self._layout.addRow(QLabel(label), widget)
                    value = field.get_value(target)
                    widget.set_value(value)

                self._connect_widget(widget, key, field)
        finally:
            self._updating_from_model = False

    def _connect_widget(
        self, widget: FieldWidget, key: str, field: InspectField
    ) -> None:
        # Capture target in closure to avoid accessing wrong target after set_target()
        target = self._target

        def on_change() -> None:
            # Check that target is still current (avoid stale callbacks)
            if self._updating_from_model or self._target is None:
                return
            if self._target is not target:
                return  # Target changed, ignore stale callback
            old_value = field.get_value(target)
            new_value = widget.get_value()
            field.set_value(target, new_value)
            self.field_changed.emit(key, old_value, new_value)
            # Request viewport redraw after property change
            from termin.editor.rendering_controller import RenderingController
            ctrl = RenderingController.instance()
            if ctrl is not None:
                ctrl._request_update()

        widget.value_changed.connect(on_change)

    def refresh(self) -> None:
        """Refresh widget values from the target object."""
        if self._target is None:
            return

        self._updating_from_model = True
        try:
            for key, field in self._fields.items():
                widget = self._widgets.get(key)
                if widget is None:
                    continue
                value = field.get_value(self._target)
                widget.set_value(value)
        finally:
            self._updating_from_model = False

    @property
    def target(self) -> Any:
        """Current target object."""
        return self._target
