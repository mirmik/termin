"""App-level additions for builtin component and frame-pass registration."""

from __future__ import annotations

from termin_assets.builtin_types import BuiltinTypeSpec
from termin.default_assets.builtin_types import (
    get_default_builtin_component_specs,
    get_default_builtin_frame_pass_specs,
)

APP_BUILTIN_COMPONENTS: list[BuiltinTypeSpec] = []

APP_BUILTIN_FRAME_PASSES: list[BuiltinTypeSpec] = [
    ("termin.visualization.render.framegraph.passes.gizmo", "GizmoPass"),
]


def get_builtin_component_specs() -> list[BuiltinTypeSpec]:
    """Return default builtin components plus termin-app additions."""
    return [*get_default_builtin_component_specs(), *APP_BUILTIN_COMPONENTS]


def get_builtin_frame_pass_specs() -> list[BuiltinTypeSpec]:
    """Return default builtin frame passes plus termin-app additions."""
    return [*get_default_builtin_frame_pass_specs(), *APP_BUILTIN_FRAME_PASSES]


# Compatibility names for legacy tests/imports. New code should call the
# functions above; ResourceManager imports this module lazily at registration.
BUILTIN_COMPONENTS = get_builtin_component_specs()
BUILTIN_FRAME_PASSES = get_builtin_frame_pass_specs()

__all__ = [
    "APP_BUILTIN_COMPONENTS",
    "APP_BUILTIN_FRAME_PASSES",
    "BUILTIN_COMPONENTS",
    "BUILTIN_FRAME_PASSES",
    "get_builtin_component_specs",
    "get_builtin_frame_pass_specs",
]
