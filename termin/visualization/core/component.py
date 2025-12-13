"""Base Component class for entity components (Unity-like architecture)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Optional

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity
    from termin.visualization.core.scene import Scene
    from termin.visualization.render.render_context import RenderContext
    from termin.visualization.render.shader import ShaderProgram

from termin.editor.inspect_field import InspectField


class Component:
    """Base class for all entity components."""

    # Если None → компонент не сериализуется
    serializable_fields = None

    # Поля, которые инспектор может редактировать.
    # Заполняется либо руками, либо через дескриптор InspectAttr.
    inspect_fields: dict[str, InspectField] = {
        "enabled": InspectField(
            path="enabled",
            label="Enabled",
            kind="bool",
        ),
    }

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Базовый класс сам себя не регистрирует
        if cls is Component:
            return
        from termin.visualization.core.resources import ResourceManager

        manager = ResourceManager.instance()
        manager.register_component(cls.__name__, cls)

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.entity: Optional["Entity"] = None
        self._started = False

    def required_shaders(self) -> Iterable["ShaderProgram"]:
        """Return shaders that must be compiled before rendering."""
        return ()

    def on_added(self, scene: "Scene"):
        """Called immediately when the component is added to an active scene."""
        pass

    def start(self, scene: "Scene"):
        """Called once before the first update, after all components are added."""
        self._started = True

    def update(self, dt: float):
        """Called every frame."""
        return

    def draw(self, context: RenderContext):
        """Issue draw calls."""
        return

    def on_removed(self):
        """Called when component is removed from its entity."""
        return

    def serialize_data(self):
        fields = self.serializable_fields
        inspect_fields = self.inspect_fields

        if fields is None and not inspect_fields:
            return None

        result = {}
        if isinstance(fields, dict):
            for key, typ in fields.items():
                value = getattr(self, key)
                result[key] = typ.serialize(value) if typ else value
        elif fields is not None:
            for key in fields:
                result[key] = getattr(self, key)

        if inspect_fields:
            for name, field in inspect_fields.items():
                if field.non_serializable:
                    continue
                key = field.path if field.path is not None else name
                if key in result:
                    continue
                result[key] = field.get_value(self)

        return result

    def serialize(self):
        data = self.serialize_data()
        return {
            "data": data,
            "type": self.__class__.__name__,
        }

    @classmethod
    def deserialize(cls, data, context):
        obj = cls.__new__(cls)
        cls.__init__(obj)

        fields = cls.serializable_fields
        if fields is None:
            pass  # Нет полей для десериализации
        elif isinstance(fields, dict):
            for key, typ in fields.items():
                value = data[key]
                setattr(obj, key, typ.deserialize(value, context) if typ else value)
        else:
            for key in fields:
                setattr(obj, key, data[key])

        return obj


class InputComponent(Component):
    """Component capable of handling input events."""

    def on_mouse_button(self, viewport, button: int, action: int, mods: int):
        return

    def on_mouse_move(self, viewport, x: float, y: float, dx: float, dy: float):
        return

    def on_scroll(self, viewport, xoffset: float, yoffset: float):
        return

    def on_key(self, viewport, key: int, scancode: int, action: int, mods: int):
        return
