"""Shared helpers for builtin component/frame-pass spec providers."""

from __future__ import annotations

import importlib
from collections.abc import Iterable

from tcbase import log

BuiltinTypeSpec = tuple[str, str]


def collect_builtin_type_specs(
    provider_modules: Iterable[str],
    attribute_name: str,
) -> list[BuiltinTypeSpec]:
    """Collect builtin type specs from provider modules.

    Provider modules expose simple lists of ``(module_name, class_name)`` specs.
    The helper is intentionally type-agnostic so asset/resource managers can
    compose component and frame-pass tables without owning package-specific
    class imports.
    """
    specs: list[BuiltinTypeSpec] = []
    for module_name in provider_modules:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            log.warning(f"Failed to import builtin type provider {module_name}: {exc}")
            continue

        try:
            provider_specs = getattr(module, attribute_name)
        except AttributeError:
            log.error(
                f"Builtin type provider {module_name} does not expose {attribute_name}",
                exc_info=True,
            )
            raise
        specs.extend(provider_specs)
    return specs


__all__ = ["BuiltinTypeSpec", "collect_builtin_type_specs"]
