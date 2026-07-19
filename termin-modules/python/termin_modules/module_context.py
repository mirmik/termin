"""Explicit ownership routing for Python project-module registrations."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, Iterator

from tcbase import log


# Project descriptors claim package namespaces before importing them. A class
# resolves its defining ``__module__`` through this table and passes the owner
# explicitly to its native descriptor builder.
_owners_by_package: dict[str, str] = {}


def register_module_packages(module_id: str, packages: Iterable[str]) -> None:
    if not module_id:
        raise ValueError("module_id must be non-empty")
    package_names = tuple(packages)
    if not package_names:
        raise ValueError(f"Python project module '{module_id}' must claim a package")
    for package in package_names:
        if not package:
            raise ValueError(f"Python project module '{module_id}' has an empty package claim")
        existing = _owners_by_package.get(package)
        if existing is not None and existing != module_id:
            raise RuntimeError(
                f"Python package '{package}' is already owned by module '{existing}'"
            )
    for package in package_names:
        _owners_by_package[package] = module_id


def unregister_module_packages(module_id: str) -> None:
    if not module_id:
        return
    for package, owner in tuple(_owners_by_package.items()):
        if owner == module_id:
            del _owners_by_package[package]


def owner_for_python_module(module_name: str) -> str | None:
    """Return the explicit project owner claiming ``module_name``."""
    best_package = ""
    owner = None
    for package, candidate in _owners_by_package.items():
        if module_name == package or module_name.startswith(package + "."):
            if len(package) > len(best_package):
                best_package = package
                owner = candidate
    return owner


@contextmanager
def module_registration_context(
    module_id: str,
    packages: Iterable[str],
) -> Iterator[None]:
    """Test/tool helper for a temporary explicit package ownership claim."""
    register_module_packages(module_id, packages)
    try:
        yield
    finally:
        unregister_module_packages(module_id)


def unregister_module_owner(module_id: str) -> None:
    """Release Python-side classes and committed runtime types for an owner."""
    if not module_id:
        return
    try:
        _unregister_app_resource_classes(module_id)
        _unregister_python_component_classes(module_id)
        _unregister_python_frame_pass_classes(module_id)
        _unregister_python_kinds(module_id)
        _commit_runtime_type_records(module_id)
    except Exception:
        log.error(
            f"[termin_modules] failed to commit registrations for module '{module_id}'",
            exc_info=True,
        )
        raise
    unregister_module_packages(module_id)


def publish_module_owner(module_id: str) -> None:
    """Commit component descriptors after all packages imported successfully."""
    if not module_id:
        raise ValueError("module_id must be non-empty")
    from termin.scene import publish_python_component_owner

    publish_python_component_owner(module_id)


def _runtime_type_records_for_owner(module_id: str, facet: str) -> list[str]:
    from termin.inspect import _inspect_native

    return [
        record["name"]
        for record in _inspect_native.runtime_type_registry_snapshot()
        if record["owner"] == module_id and facet in record["facets"]
    ]


def _unregister_python_component_classes(module_id: str) -> None:
    from termin.scene import ComponentRegistry
    from termin.scene.python_component import unregister_python_component_owner

    registry = ComponentRegistry.instance()
    for name in sorted(
        _runtime_type_records_for_owner(module_id, "termin.scene.component")
    ):
        if registry.get_class(name) is not None:
            registry.unregister_python(name)
    unregister_python_component_owner(module_id)


def _unregister_python_frame_pass_classes(module_id: str) -> None:
    from termin.render_framework import tc_pass_registry_unregister_python
    from termin.render_framework.python_pass import unregister_python_pass_owner

    for name in sorted(
        _runtime_type_records_for_owner(module_id, "termin.render.frame_pass")
    ):
        tc_pass_registry_unregister_python(name)
    unregister_python_pass_owner(module_id)


def _commit_runtime_type_records(module_id: str) -> None:
    from termin.inspect import _inspect_native

    removed = _inspect_native.commit_runtime_type_owner_unload(module_id)
    if removed:
        log.info(
            f"[termin_modules] removed {removed} runtime type record(s) for module '{module_id}'"
        )


def _unregister_python_kinds(module_id: str) -> None:
    from termin.inspect.kind import KindRegistry

    KindRegistry.unregister_owner(module_id)


def _unregister_app_resource_classes(module_id: str) -> None:
    from termin_assets import get_resource_manager

    resources = get_resource_manager()
    if resources is None:
        return
    resources.component_registry.unregister_owner(module_id)
    resources.frame_pass_registry.unregister_owner(module_id)


__all__ = [
    "module_registration_context",
    "owner_for_python_module",
    "publish_module_owner",
    "register_module_packages",
    "unregister_module_owner",
    "unregister_module_packages",
]
