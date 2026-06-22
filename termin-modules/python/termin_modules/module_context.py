"""Import-time ownership context for project modules."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

from tcbase import log


_owner_stack: list[str] = []


@dataclass
class ModuleOwnedRegistrations:
    components: set[str] = field(default_factory=set)
    inspect_types: set[str] = field(default_factory=set)
    python_kinds: set[str] = field(default_factory=set)
    app_components: set[str] = field(default_factory=set)
    frame_passes: set[str] = field(default_factory=set)


_registrations_by_owner: dict[str, ModuleOwnedRegistrations] = {}


def current_module_owner() -> str | None:
    if not _owner_stack:
        return None
    return _owner_stack[-1]


def begin_module_import(module_id: str) -> None:
    if not module_id:
        return
    _owner_stack.append(module_id)
    _registrations_by_owner[module_id] = ModuleOwnedRegistrations()


def end_module_import(module_id: str) -> None:
    if not module_id:
        return
    if not _owner_stack:
        log.error(f"[termin_modules] module owner context underflow for {module_id}")
        return
    popped = _owner_stack.pop()
    if popped != module_id:
        log.error(
            f"[termin_modules] module owner context mismatch: expected {module_id}, got {popped}"
        )


@contextmanager
def module_import_context(module_id: str) -> Iterator[None]:
    if not module_id:
        yield
        return

    begin_module_import(module_id)
    try:
        yield
    finally:
        end_module_import(module_id)


def record_component(name: str) -> None:
    owner = current_module_owner()
    if owner is None:
        return
    _registrations_by_owner.setdefault(owner, ModuleOwnedRegistrations()).components.add(name)


def record_inspect_type(name: str) -> None:
    owner = current_module_owner()
    if owner is None:
        return
    _registrations_by_owner.setdefault(owner, ModuleOwnedRegistrations()).inspect_types.add(name)


def record_python_kind(name: str) -> None:
    owner = current_module_owner()
    if owner is None:
        return
    _registrations_by_owner.setdefault(owner, ModuleOwnedRegistrations()).python_kinds.add(name)


def record_app_component(name: str) -> None:
    owner = current_module_owner()
    if owner is None:
        return
    _registrations_by_owner.setdefault(owner, ModuleOwnedRegistrations()).app_components.add(name)


def record_frame_pass(name: str) -> None:
    owner = current_module_owner()
    if owner is None:
        return
    _registrations_by_owner.setdefault(owner, ModuleOwnedRegistrations()).frame_passes.add(name)


def registrations_for_owner(module_id: str) -> ModuleOwnedRegistrations:
    current = _registrations_by_owner.get(module_id)
    if current is None:
        return ModuleOwnedRegistrations()
    return ModuleOwnedRegistrations(
        components=set(current.components),
        inspect_types=set(current.inspect_types),
        python_kinds=set(current.python_kinds),
        app_components=set(current.app_components),
        frame_passes=set(current.frame_passes),
    )


def unregister_module_owner(module_id: str) -> None:
    registrations = _registrations_by_owner.pop(module_id, None)
    if registrations is None:
        return

    _unregister_app_resource_classes(registrations)
    _unregister_inspect_types(registrations)
    _unregister_python_kinds(registrations)
    _unregister_components(registrations)


def _unregister_components(registrations: ModuleOwnedRegistrations) -> None:
    if not registrations.components:
        return

    try:
        from termin.scene import ComponentRegistry

        registry = ComponentRegistry.instance()
        for name in sorted(registrations.components):
            try:
                try:
                    registry.unregister_python(name)
                except AttributeError:
                    registry.unregister(name)
            except Exception:
                log.error(
                    f"[termin_modules] failed to unregister Python component '{name}'",
                    exc_info=True,
                )
    except Exception:
        log.error("[termin_modules] failed to access ComponentRegistry during module cleanup", exc_info=True)


def _unregister_inspect_types(registrations: ModuleOwnedRegistrations) -> None:
    if not registrations.inspect_types:
        return

    try:
        from termin.inspect import InspectRegistry

        registry = InspectRegistry.instance()
        for name in sorted(registrations.inspect_types):
            try:
                registry.unregister_type(name)
            except Exception:
                log.error(
                    f"[termin_modules] failed to unregister inspect type '{name}'",
                    exc_info=True,
                )
    except Exception:
        log.error("[termin_modules] failed to access InspectRegistry during module cleanup", exc_info=True)


def _unregister_python_kinds(registrations: ModuleOwnedRegistrations) -> None:
    if not registrations.python_kinds:
        return

    try:
        from termin._native.kind import KindRegistry

        registry = KindRegistry.instance()
        for name in sorted(registrations.python_kinds):
            try:
                registry.unregister_python(name)
            except Exception:
                log.error(
                    f"[termin_modules] failed to unregister Python kind '{name}'",
                    exc_info=True,
                )
    except Exception:
        log.error("[termin_modules] failed to access KindRegistry during module cleanup", exc_info=True)


def _unregister_app_resource_classes(registrations: ModuleOwnedRegistrations) -> None:
    if not registrations.app_components and not registrations.frame_passes:
        return

    try:
        from termin.assets.resources import ResourceManager

        resources = ResourceManager.instance()
        for name in sorted(registrations.app_components):
            try:
                resources.component_registry.unregister(name)
            except Exception:
                log.error(
                    f"[termin_modules] failed to unregister app component class '{name}'",
                    exc_info=True,
                )
        for name in sorted(registrations.frame_passes):
            try:
                resources.frame_pass_registry.unregister(name)
            except Exception:
                log.error(
                    f"[termin_modules] failed to unregister frame pass class '{name}'",
                    exc_info=True,
                )
    except Exception:
        log.error(
            "[termin_modules] failed to clean app-side resource class registries",
            exc_info=True,
        )


__all__ = [
    "ModuleOwnedRegistrations",
    "begin_module_import",
    "current_module_owner",
    "end_module_import",
    "module_import_context",
    "record_app_component",
    "record_component",
    "record_frame_pass",
    "record_inspect_type",
    "record_python_kind",
    "registrations_for_owner",
    "unregister_module_owner",
]
