"""Default builtin component and frame-pass specs.

The asset layer owns the default composition of type providers. Application
packages may append their own specs without becoming the source of truth for
engine/domain defaults.
"""

from __future__ import annotations

from termin_assets.builtin_types import BuiltinTypeSpec, collect_builtin_type_specs

_DEFAULT_COMPONENT_PROVIDER_MODULES = (
    "termin.render_components.builtins",
)

_DEFAULT_FRAME_PASS_PROVIDER_MODULES = (
    "termin.render_components.builtins",
    "termin.render_passes.builtins",
    "termin.render_framework.builtins",
)

DEFAULT_DOMAIN_COMPONENT_SPECS: list[BuiltinTypeSpec] = [
    ("termin.skeleton_components", "SkeletonController"),
    ("termin.animation_components", "AnimationPlayer"),
    ("termin.kinematic.kinematic_components", "ActuatorComponent"),
    ("termin.kinematic.kinematic_components", "RotatorComponent"),
    ("termin.physics_components.physics_world_component", "PhysicsWorldComponent"),
    ("termin.physics_components.rigid_body_component", "RigidBodyComponent"),
    ("termin.physics.fem_physics_world_component", "FEMPhysicsWorldComponent"),
    ("termin.physics.fem_rigid_body_component", "FEMRigidBodyComponent"),
    ("termin.physics.fem_fixed_joint_component", "FEMFixedJointComponent"),
    ("termin.physics.fem_revolute_joint_component", "FEMRevoluteJointComponent"),
    ("termin.colliders.collider_component", "ColliderComponent"),
    ("termin.mesh.mesh_component", "MeshComponent"),
    ("termin.mesh.script_mesh_component", "ScriptMeshComponent"),
    ("termin.mesh.procedural_mesh_component", "ProceduralMeshComponent"),
    ("termin.voxels.voxelizer_component", "VoxelizerComponent"),
    ("termin.voxels.display_component", "VoxelDisplayComponent"),
    ("termin.navmesh.display_component", "NavMeshDisplayComponent"),
    ("termin.navmesh.material_component", "NavMeshMaterialComponent"),
    ("termin.navmesh.pathfinding_world_component", "PathfindingWorldComponent"),
    ("termin.navmesh.agent_component", "NavMeshAgentComponent"),
    ("termin.navmesh.builder_component", "NavMeshBuilderComponent"),
    ("termin.navmesh", "DetourPathfindingWorldComponent"),
    ("termin.navmesh", "NavMeshKeeperComponent"),
    ("termin.navmesh", "RecastNavMeshBuilderComponent"),
    ("termin.audio.components.audio_source", "AudioSource"),
    ("termin.audio.components.audio_listener", "AudioListener"),
    ("termin.tween.component", "TweenManagerComponent"),
]


def get_default_builtin_component_specs() -> list[BuiltinTypeSpec]:
    """Return default component specs contributed below termin-app."""
    return [
        *collect_builtin_type_specs(_DEFAULT_COMPONENT_PROVIDER_MODULES, "COMPONENT_SPECS"),
        *DEFAULT_DOMAIN_COMPONENT_SPECS,
    ]


def get_default_builtin_frame_pass_specs() -> list[BuiltinTypeSpec]:
    """Return default frame-pass specs contributed below termin-app."""
    return collect_builtin_type_specs(_DEFAULT_FRAME_PASS_PROVIDER_MODULES, "FRAME_PASS_SPECS")


__all__ = [
    "DEFAULT_DOMAIN_COMPONENT_SPECS",
    "get_default_builtin_component_specs",
    "get_default_builtin_frame_pass_specs",
]
