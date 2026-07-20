"""Explicit ownership routing for Python project-module registrations."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Iterable, Iterator

from tcbase import log


# Project descriptors claim package namespaces before importing them. A class
# resolves its defining ``__module__`` through this table and passes the owner
# explicitly to its native descriptor builder.
_owners_by_package: dict[str, str] = {}


@dataclass(frozen=True)
class OwnerContributionParticipant:
    """One idempotent owner cleanup step with an independent audit."""

    identity: str
    revoke: Callable[[str], Iterable[str] | None]
    audit: Callable[[str], Iterable[str]]


@dataclass
class _OwnerCleanupSession:
    completed: set[str] = field(default_factory=set)


_owner_contribution_participants: list[OwnerContributionParticipant] = []
_owner_cleanup_sessions: dict[str, _OwnerCleanupSession] = {}


def _audit_participant(
    module_id: str,
    participant: OwnerContributionParticipant,
) -> tuple[str, ...]:
    try:
        return tuple(sorted(participant.audit(module_id)))
    except Exception:
        log.error(
            f"[termin_modules] owner='{module_id}' participant="
            f"'{participant.identity}' phase='audit' failed",
            exc_info=True,
        )
        raise


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
    # A new load generation starts a new monotonic cleanup session.
    _owner_cleanup_sessions.pop(module_id, None)


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
    """Revoke and audit every registered contribution for ``module_id``."""
    if not module_id:
        return
    session = _owner_cleanup_sessions.setdefault(module_id, _OwnerCleanupSession())
    for participant in tuple(_owner_contribution_participants):
        if participant.identity in session.completed:
            continue
        try:
            removed = tuple(sorted(participant.revoke(module_id) or ()))
        except Exception:
            log.error(
                f"[termin_modules] owner='{module_id}' participant="
                f"'{participant.identity}' phase='revoke' failed",
                exc_info=True,
            )
            raise
        remaining = _audit_participant(module_id, participant)
        if remaining:
            message = (
                f"Owner contribution cleanup incomplete: owner='{module_id}' "
                f"participant='{participant.identity}' phase='audit' "
                f"remaining={list(remaining)!r}"
            )
            log.error(f"[termin_modules] {message}")
            raise RuntimeError(message)
        session.completed.add(participant.identity)
        log.info(
            f"[termin_modules] owner='{module_id}' participant="
            f"'{participant.identity}' phase='revoke' removed={list(removed)!r}"
        )

    leaked: list[str] = []
    for participant in tuple(_owner_contribution_participants):
        remaining = _audit_participant(module_id, participant)
        if remaining:
            session.completed.discard(participant.identity)
        leaked.extend(f"{participant.identity}:{identity}" for identity in remaining)
    if leaked:
        message = (
            f"Owner contribution audit failed: owner='{module_id}' "
            f"remaining={leaked!r}"
        )
        log.error(f"[termin_modules] {message}")
        raise RuntimeError(message)


def register_owner_contribution_participant(
    participant: OwnerContributionParticipant,
) -> None:
    if not participant.identity:
        raise ValueError("owner contribution participant identity must be non-empty")
    if any(
        registered.identity == participant.identity
        for registered in _owner_contribution_participants
    ):
        raise ValueError(
            f"owner contribution participant '{participant.identity}' already exists"
        )
    _owner_contribution_participants.append(participant)


def unregister_owner_contribution_participant(identity: str) -> None:
    for index, participant in enumerate(_owner_contribution_participants):
        if participant.identity == identity:
            del _owner_contribution_participants[index]
            for session in _owner_cleanup_sessions.values():
                session.completed.discard(identity)
            return


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


def _unregister_python_component_classes(module_id: str) -> list[str]:
    from termin.scene import ComponentRegistry
    from termin.scene.python_component import (
        list_python_component_owner,
        unregister_python_component_owner,
    )

    registry = ComponentRegistry.instance()
    names = sorted(_runtime_type_records_for_owner(module_id, "termin.scene.component"))
    declarations = list_python_component_owner(module_id)
    for name in names:
        if registry.get_class(name) is not None:
            registry.unregister_python(name)
    unregister_python_component_owner(module_id)
    return sorted(set(names) | set(declarations))


def _audit_python_component_classes(module_id: str) -> list[str]:
    from termin.scene.python_component import list_python_component_owner

    return list_python_component_owner(module_id)


def _unregister_python_frame_pass_classes(module_id: str) -> list[str]:
    from termin.render_framework import tc_pass_registry_unregister_python
    from termin.render_framework.python_pass import (
        list_python_pass_owner,
        unregister_python_pass_owner,
    )

    names = sorted(_runtime_type_records_for_owner(module_id, "termin.render.frame_pass"))
    declarations = list_python_pass_owner(module_id)
    for name in names:
        tc_pass_registry_unregister_python(name)
    unregister_python_pass_owner(module_id)
    return sorted(set(names) | set(declarations))


def _audit_python_frame_pass_classes(module_id: str) -> list[str]:
    from termin.render_framework.python_pass import list_python_pass_owner

    return list_python_pass_owner(module_id)


def _commit_runtime_type_records(module_id: str) -> list[str]:
    from termin.inspect import _inspect_native

    names = _audit_runtime_type_records(module_id)
    removed = _inspect_native.commit_runtime_type_owner_unload(module_id)
    if removed:
        log.info(
            f"[termin_modules] removed {removed} runtime type record(s) for module '{module_id}'"
        )
    return names


def _audit_runtime_type_records(module_id: str) -> list[str]:
    from termin.inspect import _inspect_native

    return sorted(
        record["name"]
        for record in _inspect_native.runtime_type_registry_snapshot()
        if record["owner"] == module_id
    )


def _unregister_python_kinds(module_id: str) -> list[str]:
    from termin.inspect.kind import KindRegistry

    names = KindRegistry.list_owned(module_id)
    KindRegistry.unregister_owner(module_id)
    return names


def _audit_python_kinds(module_id: str) -> list[str]:
    from termin.inspect.kind import KindRegistry

    return KindRegistry.list_owned(module_id)


def _unregister_app_resource_classes(module_id: str) -> list[str]:
    from termin_assets import get_resource_manager

    resources = get_resource_manager()
    if resources is None:
        return []
    names = _audit_app_resource_classes(module_id)
    resources.component_registry.unregister_owner(module_id)
    resources.frame_pass_registry.unregister_owner(module_id)
    return names


def _audit_app_resource_classes(module_id: str) -> list[str]:
    from termin_assets import get_resource_manager

    resources = get_resource_manager()
    if resources is None:
        return []
    return [
        *(f"component:{name}" for name in resources.component_registry.list_owned(module_id)),
        *(f"frame-pass:{name}" for name in resources.frame_pass_registry.list_owned(module_id)),
    ]


def _revoke_module_packages(module_id: str) -> list[str]:
    names = _audit_module_packages(module_id)
    unregister_module_packages(module_id)
    return names


def _audit_module_packages(module_id: str) -> list[str]:
    return sorted(
        package for package, owner in _owners_by_package.items() if owner == module_id
    )


for _participant in (
    OwnerContributionParticipant(
        "app-resource-classes",
        lambda owner: _unregister_app_resource_classes(owner),
        lambda owner: _audit_app_resource_classes(owner),
    ),
    OwnerContributionParticipant(
        "python-component-classes",
        lambda owner: _unregister_python_component_classes(owner),
        lambda owner: _audit_python_component_classes(owner),
    ),
    OwnerContributionParticipant(
        "python-frame-pass-classes",
        lambda owner: _unregister_python_frame_pass_classes(owner),
        lambda owner: _audit_python_frame_pass_classes(owner),
    ),
    OwnerContributionParticipant(
        "python-kinds",
        lambda owner: _unregister_python_kinds(owner),
        lambda owner: _audit_python_kinds(owner),
    ),
    OwnerContributionParticipant(
        "runtime-types",
        lambda owner: _commit_runtime_type_records(owner),
        lambda owner: _audit_runtime_type_records(owner),
    ),
    OwnerContributionParticipant(
        "package-claims",
        lambda owner: _revoke_module_packages(owner),
        lambda owner: _audit_module_packages(owner),
    ),
):
    register_owner_contribution_participant(_participant)


__all__ = [
    "module_registration_context",
    "OwnerContributionParticipant",
    "owner_for_python_module",
    "publish_module_owner",
    "register_module_packages",
    "register_owner_contribution_participant",
    "unregister_module_owner",
    "unregister_module_packages",
    "unregister_owner_contribution_participant",
]
