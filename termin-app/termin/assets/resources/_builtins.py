"""Builtin component and frame pass lists for auto-registration."""

from typing import List, Tuple

# Список стандартных компонентов для предрегистрации.
# Формат: (имя_модуля, имя_класса)
BUILTIN_COMPONENTS: List[Tuple[str, str]] = [
    # Рендеринг
    ("termin.render_components", "MeshRenderer"),
    ("termin.render_components.skinned_mesh_renderer", "SkinnedMeshRenderer"),
    ("termin.render_components.line_renderer", "LineRenderer"),
    ("termin.render_components", "LightComponent"),
    ("termin.render_components", "XrOriginComponent"),
    ("termin.render_components", "XrThumbstickLocomotionComponent"),
    # Камера
    ("termin.visualization.core.camera", "CameraComponent"),
    ("termin.visualization.core.camera", "CameraController"),
    # Скелет и анимация
    ("termin.skeleton_components", "SkeletonController"),
    ("termin.animation_components", "AnimationPlayer"),
    # Кинематика
    ("termin.kinematic.kinematic_components", "ActuatorComponent"),
    ("termin.kinematic.kinematic_components", "RotatorComponent"),
    # Физика
    ("termin.physics_components.physics_world_component", "PhysicsWorldComponent"),
    ("termin.physics_components.rigid_body_component", "RigidBodyComponent"),
    # FEM Физика
    ("termin.physics.fem_physics_world_component", "FEMPhysicsWorldComponent"),
    ("termin.physics.fem_rigid_body_component", "FEMRigidBodyComponent"),
    ("termin.physics.fem_fixed_joint_component", "FEMFixedJointComponent"),
    ("termin.physics.fem_revolute_joint_component", "FEMRevoluteJointComponent"),
    # Коллайдеры
    ("termin.colliders.collider_component", "ColliderComponent"),
    # Меш
    ("termin.mesh.mesh_component", "MeshComponent"),
    ("termin.mesh.script_mesh_component", "ScriptMeshComponent"),
    ("termin.mesh.procedural_mesh_component", "ProceduralMeshComponent"),
    # Воксели
    ("termin.voxels.voxelizer_component", "VoxelizerComponent"),
    ("termin.voxels.display_component", "VoxelDisplayComponent"),
    # NavMesh
    ("termin.navmesh.display_component", "NavMeshDisplayComponent"),
    ("termin.navmesh.material_component", "NavMeshMaterialComponent"),
    ("termin.navmesh.pathfinding_world_component", "PathfindingWorldComponent"),
    ("termin.navmesh.agent_component", "NavMeshAgentComponent"),
    ("termin.navmesh.builder_component", "NavMeshBuilderComponent"),
    ("termin.navmesh", "DetourPathfindingWorldComponent"),
    ("termin.navmesh", "NavMeshKeeperComponent"),
    ("termin.navmesh", "RecastNavMeshBuilderComponent"),
    # Audio
    ("termin.audio.components.audio_source", "AudioSource"),
    ("termin.audio.components.audio_listener", "AudioListener"),
    # Game components
    ("termin.components.teleport_component", "TeleportComponent"),
    # Tween
    ("termin.tween.component", "TweenManagerComponent"),
]

# Список встроенных FramePass'ов для предрегистрации.
# Формат: (имя_модуля, имя_класса)
BUILTIN_FRAME_PASSES: List[Tuple[str, str]] = [
    # Основные пассы
    ("termin.render_passes", "ColorPass"),
    ("termin.render_passes", "SkyBoxPass"),
    ("termin.render_components", "DepthPass"),
    ("termin.render_components", "DepthOnlyPass"),
    ("termin.render_components", "DepthToColorPass"),
    ("termin.render_components", "ColorToDepthPass"),
    ("termin.render_components", "NormalPass"),
    ("termin.render_passes", "ShadowPass"),
    ("termin.visualization.render.framegraph.passes.ui_widget", "UIWidgetPass"),
    ("termin.render_passes", "PresentToScreenPass"),
    ("termin.render_passes", "BlitPass"),
    ("termin.render_passes", "ResolvePass"),
    # ID/Picking
    ("termin.render_passes", "IdPass"),
    ("termin.visualization.render.framegraph.passes.gizmo", "GizmoPass"),
    # Post-effect passes
    ("termin.render_passes", "BloomPass"),
    ("termin.render_passes", "GrayscalePass"),
    ("termin.render_passes", "HighlightPass"),
    ("termin.visualization.render.framegraph.passes.material_pass", "MaterialPass"),
    ("termin.render_passes", "TonemapPass"),
    ("termin.render_framework", "GraphAliasPass"),
    # Debug
    ("termin.render_passes", "DebugTrianglePass"),
]
