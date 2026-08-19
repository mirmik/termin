"""Declarative Python GameApplication registration over the native runtime facet."""

from __future__ import annotations

import atexit
from dataclasses import dataclass
from typing import ClassVar

from tcbase import log

from ._runtime_native import (
    _game_application_type_info,
    _python_game_application_types,
    _register_game_application,
    _unregister_game_application,
)


@dataclass(frozen=True)
class _GameApplicationRegistration:
    cls: type["GameApplication"]
    owner: str
    type_name: str


_game_application_declarations: dict[tuple[str, str], _GameApplicationRegistration] = {}


def _owner_for_game_application_class(cls: type) -> str:
    try:
        from termin_modules.module_context import owner_for_python_module
    except ModuleNotFoundError as exc:
        if exc.name not in ("termin_modules", "termin_modules.module_context"):
            log.error("Failed to load module ownership context", exc_info=True)
        return "termin-runtime-python"
    except Exception:
        log.error("Failed to load module ownership context", exc_info=True)
        return "termin-runtime-python"
    return owner_for_python_module(cls.__module__) or "termin-runtime-python"


def _class_type_name(cls: type["GameApplication"]) -> str:
    declared = cls.__dict__.get("game_application_type_name")
    type_name = declared if declared is not None else cls.__name__
    if not isinstance(type_name, str) or not type_name or type_name.strip() != type_name:
        raise ValueError(f"{cls.__name__}.game_application_type_name must be a non-empty, trimmed string")
    return type_name


def _declare_game_application(
    cls: type["GameApplication"],
    *,
    owner: str,
    type_name: str | None = None,
) -> _GameApplicationRegistration:
    if not isinstance(cls, type) or not issubclass(cls, GameApplication):
        raise TypeError("Python GameApplication classes must derive from GameApplication")
    if not owner:
        raise ValueError("Python GameApplication declaration requires a non-empty owner")
    resolved_type_name = type_name or _class_type_name(cls)
    if not resolved_type_name or resolved_type_name.strip() != resolved_type_name:
        raise ValueError("Python GameApplication type name must be non-empty and trimmed")

    for key, registration in tuple(_game_application_declarations.items()):
        if registration.cls is cls and key != (owner, resolved_type_name):
            del _game_application_declarations[key]

    registration = _GameApplicationRegistration(cls, owner, resolved_type_name)
    _game_application_declarations[(owner, resolved_type_name)] = registration
    return registration


def _registration_for_class(
    cls: type["GameApplication"],
) -> _GameApplicationRegistration | None:
    for registration in _game_application_declarations.values():
        if registration.cls is cls:
            return registration
    return None


def _parent_type_name(cls: type["GameApplication"]) -> str:
    for parent in cls.__mro__[1:]:
        if parent is GameApplication:
            return "GameApplication"
        if isinstance(parent, type) and issubclass(parent, GameApplication):
            registration = _registration_for_class(parent)
            if registration is not None:
                return registration.type_name
    return "GameApplication"


def _validate_lifecycle_methods(cls: type["GameApplication"]) -> None:
    for method_name in ("start", "stop"):
        implementation = None
        for candidate in cls.__mro__:
            if method_name in candidate.__dict__:
                implementation = candidate.__dict__[method_name]
                break
        if implementation is None or not callable(implementation):
            raise TypeError(f"{cls.__name__}.{method_name} must be callable")
        if implementation is GameApplication.__dict__[method_name]:
            raise TypeError(f"{cls.__name__} must implement {method_name}()")


def _publication_order(
    registrations: list[_GameApplicationRegistration],
) -> list[_GameApplicationRegistration]:
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
    registrations: list[_GameApplicationRegistration],
) -> list[str]:
    ordered = _publication_order(registrations)
    if not ordered:
        return []

    names: dict[str, _GameApplicationRegistration] = {}
    for registration in ordered:
        _validate_lifecycle_methods(registration.cls)
        existing = names.get(registration.type_name)
        if existing is not None and existing.cls is not registration.cls:
            raise RuntimeError(f"duplicate Python GameApplication type name: {registration.type_name}")
        names[registration.type_name] = registration

    changed: list[_GameApplicationRegistration] = []
    replaced: list[tuple[str, type, str | None, str]] = []
    try:
        for registration in ordered:
            previous: tuple[str, type, str | None, str] | None = None
            info = _game_application_type_info(registration.type_name)
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

            if not _register_game_application(
                registration.type_name,
                registration.cls,
                registration.owner,
                _parent_type_name(registration.cls),
            ):
                raise RuntimeError(f"GameApplication descriptor rejected for {registration.type_name}")
            changed.append(registration)
            if previous is not None:
                replaced.append(previous)
    except Exception:
        for registration in reversed(changed):
            try:
                if not _unregister_game_application(registration.type_name):
                    log.error(f"[PythonGameApplication] rollback refused for {registration.type_name}")
            except Exception:
                log.error(
                    f"[PythonGameApplication] failed to roll back {registration.type_name}",
                    exc_info=True,
                )
        for type_name, previous_class, parent, owner in replaced:
            try:
                if not _register_game_application(type_name, previous_class, owner, parent):
                    log.error(f"[PythonGameApplication] failed to restore previous {type_name}")
            except Exception:
                log.error(
                    f"[PythonGameApplication] failed to restore previous {type_name}",
                    exc_info=True,
                )
        log.error(
            "[PythonGameApplication] explicit descriptor publication failed",
            exc_info=True,
        )
        raise

    return [registration.type_name for registration in changed]


def publish_game_applications(
    classes: list[type["GameApplication"]],
    *,
    owner: str,
) -> list[str]:
    """Publish selected classes as one owner-scoped descriptor batch."""
    registrations = [_declare_game_application(cls, owner=owner) for cls in classes]
    return _publish_registrations(registrations)


def publish_game_application(
    cls: type["GameApplication"],
    *,
    owner: str | None = None,
    type_name: str | None = None,
) -> list[str]:
    """Publish one Python GameApplication explicitly."""
    registration = _declare_game_application(
        cls,
        owner=owner or _owner_for_game_application_class(cls),
        type_name=type_name,
    )
    return _publish_registrations([registration])


def publish_game_application_owner(owner: str) -> list[str]:
    """Commit declarations belonging to one successfully imported project module."""
    if not owner:
        raise ValueError("Python GameApplication publication requires a non-empty owner")
    selected = [registration for registration in _game_application_declarations.values() if registration.owner == owner]
    return _publish_registrations(selected)


def list_python_game_application_owner(owner: str) -> list[str]:
    declarations = {
        registration.type_name
        for registration in _game_application_declarations.values()
        if registration.owner == owner
    }
    registered = set(_python_game_application_types(owner))
    return sorted(declarations | registered)


def unregister_python_game_application_owner(owner: str) -> list[str]:
    """Revoke native descriptors before forgetting their Python declarations."""
    names = list_python_game_application_owner(owner)
    registered = set(_python_game_application_types(owner))
    for type_name in names:
        if type_name in registered and not _unregister_game_application(type_name):
            raise RuntimeError(f"GameApplication descriptor '{type_name}' refused owner unload")
    for key, registration in tuple(_game_application_declarations.items()):
        if registration.owner == owner:
            del _game_application_declarations[key]
    return names


def shutdown_python_game_applications() -> None:
    """Release all Python-backed GameApplication descriptors before interpreter exit."""
    for type_name in reversed(list(_python_game_application_types())):
        try:
            if not _unregister_game_application(type_name):
                log.error(f"[PythonGameApplication] descriptor refused shutdown unregister {type_name}")
        except Exception:
            log.error(
                f"[PythonGameApplication] failed to unregister {type_name} during shutdown",
                exc_info=True,
            )


class GameApplication:
    """Pure-Python project composition root with explicit start/stop lifecycle."""

    game_application_type_name: ClassVar[str | None] = None

    def __init_subclass__(cls, **kwargs):
        """Record a declaration without publishing it during package import."""
        super().__init_subclass__(**kwargs)
        _declare_game_application(
            cls,
            owner=_owner_for_game_application_class(cls),
        )

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


def _install_module_owner_participant() -> None:
    from termin_modules.module_context import (
        OwnerContributionParticipant,
        register_owner_contribution_participant,
    )

    register_owner_contribution_participant(
        OwnerContributionParticipant(
            "python-game-application-classes",
            unregister_python_game_application_owner,
            list_python_game_application_owner,
            publish_game_application_owner,
        )
    )


_install_module_owner_participant()
atexit.register(shutdown_python_game_applications)


__all__ = [
    "GameApplication",
    "list_python_game_application_owner",
    "publish_game_application",
    "publish_game_application_owner",
    "publish_game_applications",
    "shutdown_python_game_applications",
    "unregister_python_game_application_owner",
]
