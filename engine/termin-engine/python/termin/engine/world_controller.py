"""Declarative Python WorldController registration over the native runtime facet."""

from __future__ import annotations

import atexit
from dataclasses import dataclass
from typing import ClassVar

from termin.base import log

from ._engine_native import (
    WorldContext,
    _world_controller_type_info,
    _python_world_controller_types,
    _register_world_controller,
    _unregister_world_controller,
)


@dataclass(frozen=True)
class _WorldControllerRegistration:
    cls: type["WorldController"]
    owner: str
    type_name: str


_world_controller_declarations: dict[tuple[str, str], _WorldControllerRegistration] = {}


def _owner_for_world_controller_class(cls: type) -> str:
    try:
        from termin_modules.module_context import owner_for_python_module
    except ModuleNotFoundError as exc:
        if exc.name not in ("termin_modules", "termin_modules.module_context"):
            log.error("Failed to load module ownership context", exc_info=True)
        return "termin-engine-python"
    except Exception:
        log.error("Failed to load module ownership context", exc_info=True)
        return "termin-engine-python"
    return owner_for_python_module(cls.__module__) or "termin-engine-python"


def _class_type_name(cls: type["WorldController"]) -> str:
    declared = cls.__dict__.get("world_controller_type_name")
    type_name = declared if declared is not None else cls.__name__
    if not isinstance(type_name, str) or not type_name or type_name.strip() != type_name:
        raise ValueError(f"{cls.__name__}.world_controller_type_name must be a non-empty, trimmed string")
    return type_name


def _declare_world_controller(
    cls: type["WorldController"],
    *,
    owner: str,
    type_name: str | None = None,
) -> _WorldControllerRegistration:
    if not isinstance(cls, type) or not issubclass(cls, WorldController):
        raise TypeError("Python WorldController classes must derive from WorldController")
    if not owner:
        raise ValueError("Python WorldController declaration requires a non-empty owner")
    resolved_type_name = type_name or _class_type_name(cls)
    if not resolved_type_name or resolved_type_name.strip() != resolved_type_name:
        raise ValueError("Python WorldController type name must be non-empty and trimmed")

    for key, registration in tuple(_world_controller_declarations.items()):
        if registration.cls is cls and key != (owner, resolved_type_name):
            del _world_controller_declarations[key]

    registration = _WorldControllerRegistration(cls, owner, resolved_type_name)
    _world_controller_declarations[(owner, resolved_type_name)] = registration
    return registration


def _registration_for_class(
    cls: type["WorldController"],
) -> _WorldControllerRegistration | None:
    for registration in _world_controller_declarations.values():
        if registration.cls is cls:
            return registration
    return None


def _parent_type_name(cls: type["WorldController"]) -> str:
    for parent in cls.__mro__[1:]:
        if parent is WorldController:
            return "WorldController"
        if isinstance(parent, type) and issubclass(parent, WorldController):
            registration = _registration_for_class(parent)
            if registration is not None:
                return registration.type_name
    return "WorldController"


def _validate_lifecycle_methods(cls: type["WorldController"]) -> None:
    for method_name in ("start", "stop"):
        implementation = None
        for candidate in cls.__mro__:
            if method_name in candidate.__dict__:
                implementation = candidate.__dict__[method_name]
                break
        if implementation is None or not callable(implementation):
            raise TypeError(f"{cls.__name__}.{method_name} must be callable")
        if implementation is WorldController.__dict__[method_name]:
            raise TypeError(f"{cls.__name__} must implement {method_name}()")


def _publication_order(
    registrations: list[_WorldControllerRegistration],
) -> list[_WorldControllerRegistration]:
    selected = {(registration.owner, registration.type_name): registration for registration in registrations}
    return sorted(
        selected.values(),
        key=lambda registration: (
            len(registration.cls.__mro__),
            registration.cls.__module__,
            registration.type_name,
        ),
    )


def _publish_registrations(
    registrations: list[_WorldControllerRegistration],
) -> list[str]:
    ordered = _publication_order(registrations)
    if not ordered:
        return []

    names: dict[str, _WorldControllerRegistration] = {}
    for registration in ordered:
        _validate_lifecycle_methods(registration.cls)
        existing = names.get(registration.type_name)
        if existing is not None and existing.cls is not registration.cls:
            raise RuntimeError(f"duplicate Python WorldController type name: {registration.type_name}")
        names[registration.type_name] = registration

    changed: list[_WorldControllerRegistration] = []
    replaced: list[tuple[str, type, str | None, str]] = []
    try:
        for registration in ordered:
            previous: tuple[str, type, str | None, str] | None = None
            info = _world_controller_type_info(registration.type_name)
            if info is not None:
                if info["owner"] != registration.owner:
                    raise RuntimeError(f"cannot publish {registration.type_name}: type is owned by {info['owner']!r}")
                previous_class = info["python_class"]
                if previous_class is None:
                    raise RuntimeError(f"cannot publish {registration.type_name}: existing type is not Python-backed")
                if previous_class is registration.cls:
                    continue
                previous = (
                    registration.type_name,
                    previous_class,
                    info["parent"],
                    registration.owner,
                )

            if not _register_world_controller(
                registration.type_name,
                registration.cls,
                registration.owner,
                _parent_type_name(registration.cls),
            ):
                raise RuntimeError(f"WorldController descriptor rejected for {registration.type_name}")
            changed.append(registration)
            if previous is not None:
                replaced.append(previous)
    except Exception:
        for registration in reversed(changed):
            try:
                if not _unregister_world_controller(registration.type_name):
                    log.error(f"[PythonWorldController] rollback refused for {registration.type_name}")
            except Exception:
                log.error(
                    f"[PythonWorldController] failed to roll back {registration.type_name}",
                    exc_info=True,
                )
        for type_name, previous_class, parent, owner in replaced:
            try:
                if not _register_world_controller(type_name, previous_class, owner, parent):
                    log.error(f"[PythonWorldController] failed to restore previous {type_name}")
            except Exception:
                log.error(
                    f"[PythonWorldController] failed to restore previous {type_name}",
                    exc_info=True,
                )
        log.error(
            "[PythonWorldController] explicit descriptor publication failed",
            exc_info=True,
        )
        raise

    return [registration.type_name for registration in changed]


def publish_world_controllers(
    classes: list[type["WorldController"]],
    *,
    owner: str,
) -> list[str]:
    """Publish selected classes as one owner-scoped descriptor batch."""
    registrations = [_declare_world_controller(cls, owner=owner) for cls in classes]
    return _publish_registrations(registrations)


def publish_world_controller(
    cls: type["WorldController"],
    *,
    owner: str | None = None,
    type_name: str | None = None,
) -> list[str]:
    """Publish one Python WorldController explicitly."""
    registration = _declare_world_controller(
        cls,
        owner=owner or _owner_for_world_controller_class(cls),
        type_name=type_name,
    )
    return _publish_registrations([registration])


def publish_world_controller_owner(owner: str) -> list[str]:
    """Commit declarations belonging to one successfully imported project module."""
    if not owner:
        raise ValueError("Python WorldController publication requires a non-empty owner")
    selected = [registration for registration in _world_controller_declarations.values() if registration.owner == owner]
    return _publish_registrations(selected)


def list_python_world_controller_owner(owner: str) -> list[str]:
    declarations = {
        registration.type_name
        for registration in _world_controller_declarations.values()
        if registration.owner == owner
    }
    registered = set(_python_world_controller_types(owner))
    return sorted(declarations | registered)


def unregister_python_world_controller_owner(owner: str) -> list[str]:
    """Revoke native descriptors before forgetting their Python declarations."""
    names = list_python_world_controller_owner(owner)
    registered = set(_python_world_controller_types(owner))
    for type_name in names:
        if type_name in registered and not _unregister_world_controller(type_name):
            raise RuntimeError(f"WorldController descriptor '{type_name}' refused owner unload")
    for key, registration in tuple(_world_controller_declarations.items()):
        if registration.owner == owner:
            del _world_controller_declarations[key]
    return names


def shutdown_python_world_controllers() -> None:
    """Release all Python-backed WorldController descriptors before interpreter exit."""
    for type_name in reversed(list(_python_world_controller_types())):
        try:
            if not _unregister_world_controller(type_name):
                log.error(f"[PythonWorldController] descriptor refused shutdown unregister {type_name}")
        except Exception:
            log.error(
                f"[PythonWorldController] failed to unregister {type_name} during shutdown",
                exc_info=True,
            )


class WorldController:
    """Pure-Python project composition root with explicit start/stop lifecycle."""

    world_controller_type_name: ClassVar[str | None] = None

    def __init_subclass__(cls, **kwargs):
        """Record a declaration without publishing it during package import."""
        super().__init_subclass__(**kwargs)
        _declare_world_controller(
            cls,
            owner=_owner_for_world_controller_class(cls),
        )

    def start(self, context: WorldContext) -> None:
        raise NotImplementedError

    def stop(self, context: WorldContext) -> None:
        raise NotImplementedError


def _install_module_owner_participant() -> None:
    from termin_modules.module_context import (
        OwnerContributionParticipant,
        register_owner_contribution_participant,
    )

    register_owner_contribution_participant(
        OwnerContributionParticipant(
            "python-world-controller-classes",
            unregister_python_world_controller_owner,
            list_python_world_controller_owner,
            publish_world_controller_owner,
        )
    )


_install_module_owner_participant()
atexit.register(shutdown_python_world_controllers)


__all__ = [
    "WorldContext",
    "WorldController",
    "list_python_world_controller_owner",
    "publish_world_controller",
    "publish_world_controller_owner",
    "publish_world_controllers",
    "shutdown_python_world_controllers",
    "unregister_python_world_controller_owner",
]
