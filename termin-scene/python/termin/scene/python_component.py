"""
Pure Python Component base class.

Uses tc_component (C core) directly via TcComponent wrapper,
without inheriting from C++ Component class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from termin.scene import Entity

from termin.scene._scene_native import TcComponent, ComponentRegistry
from termin.inspect import InspectField


class PythonComponent:
    """
    Base class for pure Python components.

    Uses tc_component C core directly, independent of C++ Component class.
    Provides the same API as the C++ Component for compatibility.
    """

    # Class-level inspect fields - enabled is inherited by all subclasses
    inspect_fields: Dict[str, Any] = {
        "display_name": InspectField(
            path="display_name",
            label="Name",
            kind="string",
            is_inspectable=False,
        ),
        "enabled": InspectField(path="enabled", label="Enabled", kind="bool"),
    }

    # Override to True in drawable subclasses (that have phase_marks)
    is_drawable: bool = False

    # Override to True in input handler subclasses
    is_input_handler: bool = False

    def __init__(self, enabled: bool = True, display_name: str = ""):
        self.display_name = display_name

        # Create TcComponent wrapper
        type_name = type(self).__name__
        self._tc = TcComponent(self, type_name)
        self._tc.enabled = enabled

        # Auto-detect if update/fixed_update are overridden
        cls = type(self)
        self._tc.has_update = cls.update is not PythonComponent.update
        self._tc.has_fixed_update = cls.fixed_update is not PythonComponent.fixed_update

        # Install drawable vtable if this is a drawable component
        if cls.is_drawable:
            self._tc.install_drawable_vtable()

    def __init_subclass__(cls, **kwargs):
        """Called when a class inherits from PythonComponent."""
        super().__init_subclass__(**kwargs)

        if cls.__name__ == "PythonComponent":
            return

        from termin.inspect import InspectRegistry
        registry = InspectRegistry.instance()

        # Register only own fields (not inherited)
        own_fields = cls.__dict__.get('inspect_fields', {})
        if own_fields:
            registry.register_python_fields(cls.__name__, own_fields)

        # Find parent component type and register inheritance
        parent_name = None
        for klass in cls.__mro__[1:]:
            if klass is PythonComponent:
                parent_name = "PythonComponent"
                break
            if hasattr(klass, 'inspect_fields'):
                parent_name = klass.__name__
                break

        if parent_name:
            registry.set_type_parent(cls.__name__, parent_name)

        # Register factory in C++ ComponentRegistry
        ComponentRegistry.instance().register_python(cls.__name__, cls, parent_name)

        # Mark as drawable if class has is_drawable = True
        if cls.is_drawable:
            ComponentRegistry.set_drawable(cls.__name__, True)

        # Mark as input handler if class has is_input_handler = True
        if cls.is_input_handler:
            ComponentRegistry.set_input_handler(cls.__name__, True)

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
    def is_input_handler(self) -> bool:
        """Check if this component handles input events (has input_vtable installed)."""
        return self._tc.is_input_handler

    @property
    def entity(self) -> Optional[Entity]:
        """Get owner entity from C-level tc_component."""
        ent = self._tc.entity
        if ent is not None and ent.valid():
            return ent
        return None

    @property
    def scene(self):
        """Get scene this component belongs to."""
        ent = self.entity
        if ent is not None:
            return ent.scene
        return None

    # =========================================================================
    # Type identification
    # =========================================================================

    def type_name(self) -> str:
        return self._tc.type_name()

    def set_type_name(self, name: str) -> None:
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
        pass

    def update(self, dt: float) -> None:
        pass

    def fixed_update(self, dt: float) -> None:
        pass

    def on_destroy(self) -> None:
        pass

    def on_editor_start(self) -> None:
        pass

    def setup_editor_defaults(self) -> None:
        pass

    # =========================================================================
    # Entity relationship
    # =========================================================================

    def on_added_to_entity(self) -> None:
        pass

    def on_removed_from_entity(self) -> None:
        pass

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def on_added(self) -> None:
        pass

    def on_removed(self) -> None:
        pass

    def on_scene_inactive(self) -> None:
        pass

    def on_scene_active(self) -> None:
        pass

    def destroy(self) -> None:
        """Explicitly release all resources."""
        self.on_destroy()

    # =========================================================================
    # Serialization
    # =========================================================================

    def serialize_data(self) -> Dict[str, Any]:
        """Serialize component data using InspectRegistry."""
        from termin.inspect import InspectRegistry
        return InspectRegistry.instance().serialize_all(self)

    def deserialize_data(self, data: Dict[str, Any], context: Any = None) -> None:
        """Deserialize component data using InspectRegistry."""
        if not data:
            return
        from termin.inspect import InspectRegistry
        InspectRegistry.instance().deserialize_all(self, data)

    def serialize(self) -> Dict[str, Any]:
        """Serialize component with type info."""
        return {
            "type": self.type_name(),
            "data": self.serialize_data()
        }


class InputComponent(PythonComponent):
    """Component capable of handling input events."""

    is_input_handler: bool = True

    def __init__(self, enabled: bool = True, active_in_editor: bool = False):
        super().__init__(enabled=enabled)
        self.active_in_editor = active_in_editor
        self._tc.install_input_vtable()

    def on_mouse_button(self, event):
        pass

    def on_mouse_move(self, event):
        pass

    def on_scroll(self, event):
        pass

    def on_key(self, event):
        pass


__all__ = ["PythonComponent", "InputComponent"]
