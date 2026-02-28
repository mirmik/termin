"""tcgui port of InspectFieldPanel — shows inspect_fields for any object."""

from __future__ import annotations

from typing import Any, Callable, Optional

from tcbase import log
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label

from termin.editor.inspect_field import InspectField
from termin.editor_tcgui.widgets.field_widgets import FieldWidget, FieldWidgetFactory


def _collect_inspect_fields(obj: Any) -> dict[str, InspectField]:
    """Collect inspect_fields from InspectRegistry for obj."""
    result: dict[str, InspectField] = {}
    try:
        from termin._native.inspect import InspectRegistry, TypeBackend
        from termin.entity import TcComponentRef
        registry = InspectRegistry.instance()

        if isinstance(obj, TcComponentRef):
            type_name = obj.type_name
            cpp_fields = registry.all_fields(type_name)
            for info in cpp_fields:
                if not info.is_inspectable:
                    continue
                choices = [(c.value, c.label) for c in info.choices] if info.choices else None
                action = info.action if info.action is not None else None

                def make_getter(path):
                    def getter(o):
                        return o.get_field(path)
                    return getter

                def make_setter(path):
                    def setter(o, v):
                        o.set_field(path, v)
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
            return result

        cls = obj.__class__
        type_name = cls.__name__

        if registry.has_type(type_name):
            backend = registry.get_type_backend(type_name)
            if backend == TypeBackend.Python:
                for klass in reversed(cls.__mro__):
                    fields = getattr(klass, 'inspect_fields', None)
                    if fields:
                        for name, field in fields.items():
                            if not field.is_inspectable:
                                continue
                            result[name] = field
                return result

        cpp_fields = registry.all_fields(type_name)
        for info in cpp_fields:
            if not info.is_inspectable:
                continue
            choices = [(c.value, c.label) for c in info.choices] if info.choices else None
            action = info.action if info.action is not None else None

            def make_getter2(path):
                def getter(o):
                    return registry.get(o, path)
                return getter

            def make_setter2(path):
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
                getter=make_getter2(info.path),
                setter=make_setter2(info.path),
            )
    except (ImportError, RuntimeError) as e:
        log.error(f"InspectFieldPanel: failed to collect fields: {e}")

    return result


class InspectFieldPanel(VStack):
    """tcgui panel that shows inspect_fields for any object as a form."""

    def __init__(self, resources=None) -> None:
        super().__init__()
        self.spacing = 4

        self._target: Any = None
        self._fields: dict[str, InspectField] = {}
        self._widgets: dict[str, FieldWidget] = {}
        self._updating_from_model: bool = False
        self._factory = FieldWidgetFactory(resources)

        # on_field_changed(key, old_value, new_value)
        self.on_field_changed: Optional[Callable[[str, Any, Any], None]] = None

    def set_resources(self, resources) -> None:
        self._factory.set_resources(resources)

    def set_scene_getter(self, getter) -> None:
        self._factory.set_scene_getter(getter)

    def set_target(self, target: Any) -> None:
        # Remove old rows
        for child in list(self.children):
            self.remove_child(child)
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

                if field.kind == "button":
                    self.add_child(widget)
                else:
                    row = HStack()
                    row.spacing = 4
                    lbl = Label()
                    lbl.text = field.label or key
                    row.add_child(lbl)
                    row.add_child(widget)
                    self.add_child(row)

                    value = field.get_value(target)
                    widget.set_value(value)

                self._connect_widget(widget, key, field)
        finally:
            self._updating_from_model = False

    def _connect_widget(self, widget: FieldWidget, key: str, field: InspectField) -> None:
        target = self._target

        def on_change() -> None:
            if self._updating_from_model or self._target is None:
                return
            if self._target is not target:
                return
            old_value = field.get_value(target)
            new_value = widget.get_value()
            field.set_value(target, new_value)
            if self.on_field_changed is not None:
                self.on_field_changed(key, old_value, new_value)

        widget.on_value_changed = on_change

    def refresh(self) -> None:
        if self._target is None:
            return
        self._updating_from_model = True
        try:
            for key, field in self._fields.items():
                widget = self._widgets.get(key)
                if widget is not None:
                    widget.set_value(field.get_value(self._target))
        finally:
            self._updating_from_model = False

    @property
    def target(self) -> Any:
        return self._target
