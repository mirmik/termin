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


class PythonComponent:
    """
    Base class for pure Python components.

    Uses tc_component C core directly, independent of C++ Component class.
    Provides the same API as the C++ Component for compatibility.
    """

    # Class-level inspect fields (populated by subclasses)
    inspect_fields: Dict[str, Any] = {}

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

        # Collect all inspect_fields from class hierarchy
        all_fields = {}
        for klass in reversed(cls.__mro__):
            if hasattr(klass, 'inspect_fields') and klass.inspect_fields:
                all_fields.update(klass.inspect_fields)

        # Register fields in C++ InspectRegistry
        if all_fields:
            from termin._native.inspect import InspectRegistry
            InspectRegistry.instance().register_python_fields(cls.__name__, all_fields)

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
    def is_native(self) -> bool:
        return self._tc.is_native

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
        """Serialize component data (override in subclasses)."""
        from termin._native.inspect import InspectRegistry
        return InspectRegistry.instance().serialize_python(self, self.type_name())

    def deserialize_data(self, data: Dict[str, Any], context: Any = None) -> None:
        """Deserialize component data (override in subclasses)."""
        from termin._native.inspect import InspectRegistry
        InspectRegistry.instance().deserialize_python(self, self.type_name(), data)

    def serialize(self) -> Dict[str, Any]:
        """Serialize component with type info."""
        return {
            "type": self.type_name(),
            "data": self.serialize_data()
        }


__all__ = ["PythonComponent"]
