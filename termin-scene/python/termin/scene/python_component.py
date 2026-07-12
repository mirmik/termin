"""
Pure Python Component base class.

Uses tc_component (C core) directly via TcComponent wrapper,
without inheriting from C++ Component class.
"""

from __future__ import annotations

import atexit
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from termin.scene import Entity

from termin.scene._scene_native import TcComponent, ComponentRegistry
from termin.inspect import InspectField
from tcbase import log


_registered_python_component_types: list[str] = []
_registered_python_inspect_types: list[str] = []


@dataclass(frozen=True)
class _PythonComponentRegistration:
    cls: type["PythonComponent"]
    owner: str


# Definitions survive shutdown_player(): the classes remain loaded in Python
# while their native factory and inspect registrations are rebuilt on the next
# explicit bootstrap.
_python_component_registrations: dict[str, _PythonComponentRegistration] = {}


def _remember_registered_type(names: list[str], type_name: str) -> None:
    if type_name not in names:
        names.append(type_name)


def _humanize_component_name(name: str) -> str:
    if not name:
        return ""
    result = [name[0]]
    for i, ch in enumerate(name[1:], start=1):
        prev = name[i - 1]
        next_ch = name[i + 1] if i + 1 < len(name) else ""
        if (
            ch.isupper()
            and (
                prev.islower()
                or prev.isdigit()
                or (prev.isupper() and next_ch.islower())
            )
        ):
            result.append(" ")
        result.append(ch)
    return "".join(result)


def _component_category_for_class(cls: type) -> str:
    for klass in cls.__mro__:
        value = klass.__dict__.get("component_category")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Project"


def _component_display_name_for_class(cls: type) -> str:
    value = cls.__dict__.get("component_display_name")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return _humanize_component_name(cls.__name__) or cls.__name__


def shutdown_python_components() -> None:
    """Unregister Python-backed component and inspect types."""
    component_names = list(reversed(_registered_python_component_types))
    inspect_names = list(reversed(_registered_python_inspect_types))

    try:
        component_registry = ComponentRegistry.instance()
        for type_name in component_names:
            try:
                component_registry.unregister_python(type_name)
            except Exception:
                pass
    except Exception:
        pass

    try:
        from termin.inspect import InspectRegistry
        inspect_registry = InspectRegistry.instance()
        for type_name in inspect_names:
            try:
                inspect_registry.unregister_type(type_name)
            except Exception:
                pass
    except Exception:
        pass

    _registered_python_component_types.clear()
    _registered_python_inspect_types.clear()


atexit.register(shutdown_python_components)


def _ensure_python_component_inspect_type(registry, record_inspect_type) -> None:
    if registry.has_type("PythonComponent"):
        return

    registry.register_python_fields("PythonComponent", PythonComponent.inspect_fields)
    _remember_registered_type(_registered_python_inspect_types, "PythonComponent")
    if record_inspect_type is not None:
        record_inspect_type("PythonComponent")


def _find_python_component_parent(cls: type["PythonComponent"]) -> str | None:
    for klass in cls.__mro__[1:]:
        if klass is PythonComponent:
            return "PythonComponent"
        if klass.inspect_fields:
            return klass.__name__
    return None


def _register_python_component_metadata(
    cls: type["PythonComponent"],
    *,
    component_registry,
    inspect_registry,
    parent_name: str | None,
    record_component,
    record_inspect_type,
) -> None:
    _ensure_python_component_inspect_type(inspect_registry, record_inspect_type)

    own_fields = cls.__dict__.get("inspect_fields", {})
    inspect_registry.register_python_fields(cls.__name__, own_fields)
    _remember_registered_type(_registered_python_inspect_types, cls.__name__)
    if record_inspect_type is not None:
        record_inspect_type(cls.__name__)

    if parent_name:
        inspect_registry.set_type_parent(cls.__name__, parent_name)
        if record_inspect_type is not None:
            record_inspect_type(cls.__name__)

    component_registry.set_category(cls.__name__, _component_category_for_class(cls))
    component_registry.set_display_name(cls.__name__, _component_display_name_for_class(cls))
    _remember_registered_type(_registered_python_component_types, cls.__name__)
    if record_component is not None:
        record_component(cls.__name__)
    if record_inspect_type is not None:
        record_inspect_type(cls.__name__)


def restore_python_components() -> None:
    """Restore loaded Python component classes after native runtime bootstrap."""
    if not _python_component_registrations:
        return

    from termin.inspect import InspectRegistry

    component_registry = ComponentRegistry.instance()
    inspect_registry = InspectRegistry.instance()
    previous_component_owner = component_registry.registration_owner()
    previous_inspect_owner = inspect_registry.registration_owner()
    try:
        for registration in _python_component_registrations.values():
            cls = registration.cls
            component_registry.set_registration_owner(registration.owner)
            inspect_registry.set_registration_owner(registration.owner)
            parent_name = _find_python_component_parent(cls)
            if not component_registry.register_python(cls.__name__, cls, parent_name):
                log.error(
                    f"[PythonComponent] rebootstrap registration rejected for {cls.__name__}"
                )
                continue
            _register_python_component_metadata(
                cls,
                component_registry=component_registry,
                inspect_registry=inspect_registry,
                parent_name=parent_name,
                record_component=None,
                record_inspect_type=None,
            )
    except Exception:
        log.error("[PythonComponent] failed to restore loaded component registrations", exc_info=True)
        raise
    finally:
        component_registry.set_registration_owner(previous_component_owner)
        inspect_registry.set_registration_owner(previous_inspect_owner)


class PythonComponent:
    """
    Base class for pure Python components.

    Uses tc_component C core directly, independent of C++ Component class.
    Provides the same API as the C++ Component for compatibility.
    """

    # Class-level inspect fields - enabled is inherited by all subclasses
    component_category = "Project"
    component_display_name = ""

    inspect_fields: Dict[str, Any] = {
        "display_name": InspectField(
            path="display_name",
            label="Name",
            kind="string",
            is_serializable=False,
            is_inspectable=False,
        ),
        "enabled": InspectField(path="enabled", label="Enabled", kind="bool"),
    }

    def __init__(self, enabled: bool = True, display_name: str = ""):
        # Create TcComponent wrapper
        type_name = type(self).__name__
        self._tc = TcComponent(self, type_name)
        self._tc.enabled = enabled
        self._tc.display_name = display_name

        # Auto-detect if update/fixed_update are overridden
        cls = type(self)
        self._tc.has_update = cls.update is not PythonComponent.update
        self._tc.has_fixed_update = cls.fixed_update is not PythonComponent.fixed_update

    def __init_subclass__(cls, **kwargs):
        """Called when a class inherits from PythonComponent."""
        super().__init_subclass__(**kwargs)

        if cls.__name__ == "PythonComponent":
            return

        from termin.inspect import InspectRegistry
        registry = InspectRegistry.instance()
        try:
            from termin_modules.module_context import (
                record_component,
                record_inspect_type,
            )
        except ModuleNotFoundError as exc:
            if exc.name not in ("termin_modules", "termin_modules.module_context"):
                log.error("Failed to load module ownership context", exc_info=True)
            record_component = None
            record_inspect_type = None
        except Exception:
            log.error("Failed to load module ownership context", exc_info=True)
            record_component = None
            record_inspect_type = None

        parent_name = _find_python_component_parent(cls)

        # Register the native factory first. A conflicting registration must
        # not replace an existing class, inspect metadata, or ownership record.
        component_registry = ComponentRegistry.instance()
        if not component_registry.register_python(cls.__name__, cls, parent_name):
            log.error(
                "[PythonComponent] registration rejected for %s; preserving existing component metadata",
                cls.__name__,
            )
            return

        _register_python_component_metadata(
            cls,
            component_registry=component_registry,
            inspect_registry=registry,
            parent_name=parent_name,
            record_component=record_component,
            record_inspect_type=record_inspect_type,
        )
        _python_component_registrations[cls.__name__] = _PythonComponentRegistration(
            cls=cls,
            owner=component_registry.registration_owner(),
        )

        # capability registration moved to respective subclasses:
        # - drawable: termin.render.DrawableComponent
        # - input: termin.input.InputComponent

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
    def display_name(self) -> str:
        return self._tc.display_name

    @display_name.setter
    def display_name(self, value: str) -> None:
        self._tc.display_name = value

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
        """Check if this component handles input events."""
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
        data = InspectRegistry.instance().serialize_all(self)
        if self.display_name:
            data["display_name"] = self.display_name
        return data

    def deserialize_data(self, data: Dict[str, Any], context: Any = None) -> None:
        """Deserialize component data using InspectRegistry."""
        if not data:
            return
        display_name = data.get("display_name")
        if display_name is not None:
            self.display_name = str(display_name)
        from termin.inspect import InspectRegistry
        InspectRegistry.instance().deserialize_all(self, data)

    def serialize(self) -> Dict[str, Any]:
        """Serialize component with type info."""
        return {
            "type": self.type_name(),
            "data": self.serialize_data()
        }


__all__ = ["PythonComponent"]
