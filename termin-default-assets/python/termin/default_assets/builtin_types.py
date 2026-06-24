"""Default builtin component and frame-pass specs.

The asset layer owns the default composition of type providers. Application
packages may contribute their own specs without becoming the source of truth
for engine/domain defaults.
"""

from __future__ import annotations

from termin_assets.builtin_types import BuiltinTypeSpec, collect_builtin_type_specs

_DEFAULT_COMPONENT_PROVIDER_MODULES = (
    "termin_render_component_specs",
    "termin_ui_component_specs",
    "termin_skeleton_component_specs",
    "termin_animation_component_specs",
    "termin_kinematic_component_specs",
    "termin_physics_component_specs",
    "termin_collision_component_specs",
    "termin_mesh_component_specs",
    "termin_voxel_component_specs",
    "termin_navmesh_component_specs",
    "termin_audio_component_specs",
    "termin_tween_component_specs",
)

_DEFAULT_FRAME_PASS_PROVIDER_MODULES = (
    "termin_render_component_specs",
    "termin_render_pass_specs",
    "termin_render_framework_specs",
)

def get_default_builtin_component_specs() -> list[BuiltinTypeSpec]:
    """Return default component specs contributed below termin-app."""
    return collect_builtin_type_specs(_DEFAULT_COMPONENT_PROVIDER_MODULES, "COMPONENT_SPECS")


def get_default_builtin_frame_pass_specs() -> list[BuiltinTypeSpec]:
    """Return default frame-pass specs contributed below termin-app."""
    return collect_builtin_type_specs(_DEFAULT_FRAME_PASS_PROVIDER_MODULES, "FRAME_PASS_SPECS")


__all__ = [
    "get_default_builtin_component_specs",
    "get_default_builtin_frame_pass_specs",
]
