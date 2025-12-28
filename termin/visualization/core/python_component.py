"""
Pure Python Component base class.

Uses tc_component (C core) directly via TcComponent wrapper,
without inheriting from C++ Component class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from termin.entity import Entity
    from termin.visualization.core.scene import Scene

from termin._native.component import TcComponent
from termin.editor.inspect_field import InspectField


class PythonComponent:
    """
    Base class for pure Python components.

    Uses tc_component C core directly, independent of C++ Component class.
    Provides the same API as the C++ Component for compatibility.
    """

    # Class-level inspect fields - enabled is inherited by all subclasses
    inspect_fields: Dict[str, Any] = {
        "enabled": InspectField(path="enabled", label="Enabled", kind="bool"),
    }

    def __init__(self, enabled: bool = True):
        # Create TcComponent wrapper
        type_name = type(self).__name__
        self._tc = TcComponent(self, type_name)
        self._tc.enabled = enabled

        # Entity reference (set by Entity.add_component)
        self._entity: Optional[Entity] = None

        # Scene reference (set by on_added)
        self._scene: Optional[Scene] = None

    def __init_subclass__(cls, **kwargs):
        """Called when a class inherits from PythonComponent."""
        super().__init_subclass__(**kwargs)

        # Don't register the base class itself
        if cls.__name__ == "PythonComponent":
            return

        from termin._native.inspect import InspectRegistry
        registry = InspectRegistry.instance()

        # Register only own fields (not inherited)
        own_fields = cls.__dict__.get('inspect_fields', {})
        if own_fields:
            registry.register_python_fields(cls.__name__, own_fields)

        # Find parent component type and register inheritance
        for klass in cls.__mro__[1:]:
            if klass is PythonComponent:
                registry.set_type_parent(cls.__name__, "PythonComponent")
                break
            if hasattr(klass, 'inspect_fields'):
                registry.set_type_parent(cls.__name__, klass.__name__)
                break

        # Register in Python ResourceManager
        try:
            from termin.visualization.core.resources import ResourceManager
            manager = ResourceManager.instance()
            manager.register_component(cls.__name__, cls)
        except ImportError:
            pass

        # Register factory in C++ ComponentRegistry
        from termin.entity import ComponentRegistry
        ComponentRegistry.instance().register_python(cls.__name__, cls)

    # =========================================================================
    # Properties (delegate to TcComponent)
    # =========================================================================

    @property
    def enabled(self) -> bool:
        return self._tc.enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._tc.enabled = value

    @property
    def active_in_editor(self) -> bool:
        return self._tc.active_in_editor

    @active_in_editor.setter
    def active_in_editor(self, value: bool) -> None:
        self._tc.active_in_editor = value

    @property
    def is_python_component(self) -> bool:
        return True

    @property
    def is_cxx_component(self) -> bool:
        return False

    @property
    def _started(self) -> bool:
        return self._tc._started

    @_started.setter
    def _started(self, value: bool) -> None:
        self._tc._started = value

    @property
    def has_update(self) -> bool:
        return self._tc.has_update

    @has_update.setter
    def has_update(self, value: bool) -> None:
        self._tc.has_update = value

    @property
    def has_fixed_update(self) -> bool:
        return self._tc.has_fixed_update

    @has_fixed_update.setter
    def has_fixed_update(self, value: bool) -> None:
        self._tc.has_fixed_update = value

    @property
    def entity(self) -> Optional[Entity]:
        return self._entity

    @entity.setter
    def entity(self, value: Optional[Entity]) -> None:
        self._entity = value

    # =========================================================================
    # Type identification
    # =========================================================================

    def type_name(self) -> str:
        return self._tc.type_name()

    def set_type_name(self, name: str) -> None:
        # Type name is set at construction, but allow override
        pass

    # =========================================================================
    # C component access
    # =========================================================================

    def c_component_ptr(self) -> int:
        """Return tc_component* as integer for C interop."""
        return self._tc.c_ptr_int()

    def sync_to_c(self) -> None:
        """Sync Python state to C (no-op for pure Python components)."""
        pass

    def sync_from_c(self) -> None:
        """Sync C state to Python (no-op for pure Python components)."""
        pass

    # =========================================================================
    # Lifecycle methods (override in subclasses)
    # =========================================================================

    def start(self) -> None:
        """Called once when component starts (after being added to scene)."""
        pass

    def update(self, dt: float) -> None:
        """Called every frame."""
        pass

    def fixed_update(self, dt: float) -> None:
        """Called at fixed timestep intervals."""
        pass

    def on_destroy(self) -> None:
        """Called when component is destroyed."""
        pass

    def on_editor_start(self) -> None:
        """Called when editor mode starts."""
        pass

    def setup_editor_defaults(self) -> None:
        """Called when component is created via editor UI."""
        pass

    # =========================================================================
    # Entity relationship
    # =========================================================================

    def on_added_to_entity(self) -> None:
        """Called when added to an entity."""
        pass

    def on_removed_from_entity(self) -> None:
        """Called when removed from an entity."""
        pass

    # =========================================================================
    # Scene relationship
    # =========================================================================

    def on_added(self, scene: Scene) -> None:
        """Called when entity is added to scene."""
        self._scene = scene

    def on_removed(self) -> None:
        """Called when entity is removed from scene."""
        self._scene = None

    # =========================================================================
    # Serialization
    # =========================================================================

    def serialize_data(self) -> Dict[str, Any]:
        """Serialize component data using InspectRegistry.

        Uses the same mechanism as CxxComponent - kind handlers are applied
        for enum, handles, etc.
        """
        from termin._native.inspect import InspectRegistry
        return InspectRegistry.instance().serialize_all(self)

    def deserialize_data(self, data: Dict[str, Any], context: Any = None) -> None:
        """Deserialize component data using InspectRegistry.

        Uses the same mechanism as CxxComponent - kind handlers are applied
        for enum, handles, etc.
        """
        if not data:
            return
        from termin._native.inspect import InspectRegistry
        InspectRegistry.instance().deserialize_all(self, data)

    def serialize(self) -> Dict[str, Any]:
        """Serialize component with type info."""
        return {
            "type": self.type_name(),
            "data": self.serialize_data()
        }


class InputComponent(PythonComponent):
    """Component capable of handling input events."""

    def __init__(self, enabled: bool = True, active_in_editor: bool = False):
        super().__init__(enabled=enabled)
        self.active_in_editor = active_in_editor

    def on_mouse_button(self, event):
        pass

    def on_mouse_move(self, event):
        pass

    def on_scroll(self, event):
        pass

    def on_key(self, event):
        pass


__all__ = ["PythonComponent", "InputComponent"]


def _register_base_type():
    """Register PythonComponent as base type with enabled field."""
    from termin._native.inspect import InspectRegistry
    registry = InspectRegistry.instance()
    registry.register_python_fields("PythonComponent", PythonComponent.inspect_fields)


_register_base_type()
