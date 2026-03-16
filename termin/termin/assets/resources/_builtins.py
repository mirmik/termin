"""Builtin component, frame pass, and post effect lists for auto-registration."""

from typing import List, Tuple

# Список стандартных компонентов для предрегистрации.
# Формат: (имя_модуля, имя_класса)
BUILTIN_COMPONENTS: List[Tuple[str, str]] = [
    # Рендеринг
    ("termin.render_components", "MeshRenderer"),
    ("termin.render_components.skinned_mesh_renderer", "SkinnedMeshRenderer"),
    ("termin.render_components.line_renderer", "LineRenderer"),
    ("termin.render_components", "LightComponent"),
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
    # Воксели
    ("termin.voxels.voxelizer_component", "VoxelizerComponent"),
    ("termin.voxels.display_component", "VoxelDisplayComponent"),
    # NavMesh
    ("termin.navmesh.display_component", "NavMeshDisplayComponent"),
    ("termin.navmesh.material_component", "NavMeshMaterialComponent"),
    ("termin.navmesh.pathfinding_world_component", "PathfindingWorldComponent"),
    ("termin.navmesh.agent_component", "NavMeshAgentComponent"),
    ("termin.navmesh.builder_component", "NavMeshBuilderComponent"),
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
    ("termin.visualization.render.framegraph.passes.color", "ColorPass"),
    ("termin.visualization.render.framegraph.passes.skybox", "SkyBoxPass"),
    ("termin.visualization.render.framegraph.passes.depth", "DepthPass"),
    ("termin.visualization.render.framegraph.passes.normal_pass", "NormalPass"),
    ("termin.visualization.render.framegraph.passes.shadow", "ShadowPass"),
    ("termin.visualization.render.framegraph.passes.ui_widget", "UIWidgetPass"),
    ("termin.visualization.render.framegraph.passes.present", "PresentToScreenPass"),
    ("termin.visualization.render.framegraph.passes.present", "BlitPass"),
    ("termin.visualization.render.framegraph.passes.present", "ResolvePass"),
    # ID/Picking
    ("termin.visualization.render.framegraph.passes.id_pass", "IdPass"),
    ("termin.visualization.render.framegraph.passes.gizmo", "GizmoPass"),
    # Post-processing (legacy)
    ("termin.visualization.render.postprocess", "PostProcessPass"),
    # Post-effect passes (new architecture)
    ("termin.visualization.render.framegraph.passes.bloom_pass", "BloomPass"),
    ("termin.visualization.render.framegraph.passes.grayscale", "GrayscalePass"),
    ("termin.visualization.render.framegraph.passes.material_pass", "MaterialPass"),
    ("termin.visualization.render.framegraph.passes.tonemap", "TonemapPass"),
    # Debug
    ("termin.visualization.render.framegraph.passes.frame_debugger", "FrameDebuggerPass"),
]

# Список встроенных PostEffect'ов для предрегистрации.
# Формат: (имя_модуля, имя_класса)
BUILTIN_POST_EFFECTS: List[Tuple[str, str]] = [
    ("termin.visualization.render.posteffects.blur", "GaussianBlurPass"),
    ("termin.visualization.render.posteffects.bloom", "BloomEffect"),
    ("termin.visualization.render.posteffects.highlight", "HighlightEffect"),
    ("termin.visualization.render.posteffects.fog", "FogEffect"),
    ("termin.visualization.render.posteffects.gray", "GrayscaleEffect"),
    ("termin.visualization.render.posteffects.material_effect", "MaterialPostEffect"),
]
