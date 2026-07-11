"""Import-time ownership context for project modules."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

from tcbase import log


_owner_stack: list[str] = []


@dataclass
class NativeTypeOwnerScope:
    component_owner: str | None = None
    inspect_owner: str | None = None


_native_type_owner_stack: list[NativeTypeOwnerScope] = []


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
    _native_type_owner_stack.append(_begin_native_type_owner_scope(module_id))
    _registrations_by_owner[module_id] = ModuleOwnedRegistrations()


def end_module_import(module_id: str) -> None:
    if not module_id:
        return
    if not _owner_stack:
        log.error(f"[termin_modules] module owner context underflow for {module_id}")
        return
    popped = _owner_stack.pop()
    previous_native_scope = NativeTypeOwnerScope()
    if _native_type_owner_stack:
        previous_native_scope = _native_type_owner_stack.pop()
    else:
        log.error(f"[termin_modules] native type owner context underflow for {module_id}")
    if popped != module_id:
        log.error(
            f"[termin_modules] module owner context mismatch: expected {module_id}, got {popped}"
        )
    _end_native_type_owner_scope(module_id, previous_native_scope)


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


def _begin_native_type_owner_scope(module_id: str) -> NativeTypeOwnerScope:
    scope = NativeTypeOwnerScope()
    try:
        from termin.scene import ComponentRegistry

        registry = ComponentRegistry.instance()
        scope.component_owner = registry.registration_owner()
        registry.set_registration_owner(module_id)
    except Exception:
        log.error(
            f"[termin_modules] failed to begin native component owner scope for '{module_id}'",
            exc_info=True,
        )

    try:
        from termin.inspect import InspectRegistry

        registry = InspectRegistry.instance()
        scope.inspect_owner = registry.registration_owner()
        registry.set_registration_owner(module_id)
    except Exception:
        log.error(
            f"[termin_modules] failed to begin native inspect owner scope for '{module_id}'",
            exc_info=True,
        )

    return scope


def _end_native_type_owner_scope(module_id: str, scope: NativeTypeOwnerScope) -> None:
    try:
        from termin.scene import ComponentRegistry

        registry = ComponentRegistry.instance()
        current_owner = registry.registration_owner()
        if current_owner and current_owner != module_id:
            log.error(
                f"[termin_modules] native component owner context mismatch: "
                f"expected {module_id}, got {current_owner}"
            )
        if scope.component_owner is not None:
            registry.set_registration_owner(scope.component_owner)
    except Exception:
        log.error(
            f"[termin_modules] failed to end native component owner scope for '{module_id}'",
            exc_info=True,
        )

    try:
        from termin.inspect import InspectRegistry

        registry = InspectRegistry.instance()
        current_owner = registry.registration_owner()
        if current_owner and current_owner != module_id:
            log.error(
                f"[termin_modules] native inspect owner context mismatch: "
                f"expected {module_id}, got {current_owner}"
            )
        if scope.inspect_owner is not None:
            registry.set_registration_owner(scope.inspect_owner)
    except Exception:
        log.error(
            f"[termin_modules] failed to end native inspect owner scope for '{module_id}'",
            exc_info=True,
        )


def unregister_module_owner(module_id: str) -> None:
    registrations = _registrations_by_owner.get(module_id)
    if registrations is None:
        return

    try:
        _unregister_app_resource_classes(registrations)
        _unregister_python_component_classes(registrations)
        _unregister_python_frame_pass_classes(module_id)
        _unregister_python_kinds(registrations)
        _commit_runtime_type_records(module_id)
    except Exception:
        log.error(
            f"[termin_modules] failed to commit registrations for module '{module_id}'",
            exc_info=True,
        )
        raise
    _registrations_by_owner.pop(module_id, None)


def _unregister_python_component_classes(registrations: ModuleOwnedRegistrations) -> None:
    if not registrations.components:
        return

    from termin.scene import ComponentRegistry

    registry = ComponentRegistry.instance()
    for name in sorted(registrations.components):
        registry.unregister_python(name)


def _unregister_python_frame_pass_classes(module_id: str) -> None:
    from termin.inspect import _inspect_native
    from termin.render_framework import tc_pass_registry_unregister_python

    records = _inspect_native.runtime_type_registry_snapshot()
    for record in records:
        if record["owner"] != module_id:
            continue
        if "termin.render.frame_pass" not in record["facets"]:
            continue
        tc_pass_registry_unregister_python(record["name"])


def _commit_runtime_type_records(module_id: str) -> None:
    from termin.inspect import _inspect_native

    removed = _inspect_native.commit_runtime_type_owner_unload(module_id)
    if removed:
        log.info(
            f"[termin_modules] removed {removed} runtime type record(s) for module '{module_id}'"
        )


def _unregister_python_kinds(registrations: ModuleOwnedRegistrations) -> None:
    if not registrations.python_kinds:
        return

    from termin.inspect.kind import KindRegistry

    registry = KindRegistry.instance()
    for name in sorted(registrations.python_kinds):
        registry.unregister_python(name)


def _unregister_app_resource_classes(registrations: ModuleOwnedRegistrations) -> None:
    if not registrations.app_components and not registrations.frame_passes:
        return

    from termin_assets import get_resource_manager

    resources = get_resource_manager()
    if resources is None:
        log.warn(
            "[termin_modules] no ResourceManager configured; "
            "skipping dynamic component/frame-pass cleanup"
        )
        return
    for name in sorted(registrations.app_components):
        resources.component_registry.unregister(name)
    for name in sorted(registrations.frame_passes):
        resources.frame_pass_registry.unregister(name)


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
