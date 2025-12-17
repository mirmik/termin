# termin/loaders/glb_instantiator.py
"""GLB instantiator - creates Entity hierarchy from GLB files."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from termin.geombase.pose3 import Pose3
from termin.geombase.general_pose3 import GeneralPose3
from termin.mesh.mesh import Mesh3
from termin.mesh.skinned_mesh import SkinnedMesh3
from termin.skeleton.bone import Bone
from termin.skeleton.skeleton import SkeletonData, SkeletonInstance
from termin.visualization.core.entity import Entity
from termin.visualization.core.mesh import MeshDrawable
from termin.visualization.render.components.mesh_renderer import MeshRenderer
from termin.visualization.render.components.skinned_mesh_renderer import SkinnedMeshRenderer
from termin.visualization.render.components.skeleton_controller import SkeletonController
from termin.visualization.render.materials.default_material import DefaultMaterial
from termin.visualization.animation.player import AnimationPlayer
from termin.visualization.animation.clip import AnimationClip

from termin.loaders.glb_loader import (
    load_glb_file_normalized,
    GLBSceneData,
    GLBNodeData,
    GLBMeshData,
    GLBSkinData,
)


def _glb_mesh_to_mesh3(glb_mesh: GLBMeshData) -> Mesh3 | SkinnedMesh3:
    """Convert GLBMeshData to Mesh3 or SkinnedMesh3."""
    vertices = glb_mesh.vertices
    indices = glb_mesh.indices.reshape(-1, 3)

    if glb_mesh.is_skinned:
        # Create skinned mesh
        mesh = SkinnedMesh3(
            vertices=vertices,
            triangles=indices,
            uvs=glb_mesh.uvs,
            vertex_normals=glb_mesh.normals,
            joint_indices=glb_mesh.joint_indices,
            joint_weights=glb_mesh.joint_weights,
        )
        if glb_mesh.normals is None:
            mesh.compute_vertex_normals()
    else:
        # Create regular mesh
        mesh = Mesh3(vertices=vertices, triangles=indices, uvs=glb_mesh.uvs)
        if glb_mesh.normals is not None:
            mesh.vertex_normals = glb_mesh.normals
        else:
            mesh.compute_vertex_normals()

    return mesh


def _create_skeleton_from_skin(
    skin: GLBSkinData,
    nodes: List[GLBNodeData],
) -> SkeletonData:
    """
    Create SkeletonData from GLB skin data.

    Args:
        skin: GLB skin data containing joint indices and inverse bind matrices
        nodes: List of all nodes in the scene

    Returns:
        SkeletonData with bones properly ordered
    """
    bones = []

    # Map from node index to bone index
    node_to_bone: Dict[int, int] = {}

    for bone_idx, node_idx in enumerate(skin.joint_node_indices):
        node = nodes[node_idx]

        # Find parent bone index
        parent_bone_idx = -1
        for child_idx in nodes[node_idx].children:
            pass  # Not used for parent lookup

        # Look for parent by checking which bone contains this node as child
        for other_bone_idx, other_node_idx in enumerate(skin.joint_node_indices):
            if node_idx in nodes[other_node_idx].children:
                parent_bone_idx = other_bone_idx
                break

        bone = Bone(
            name=node.name,
            index=bone_idx,
            parent_index=parent_bone_idx,
            inverse_bind_matrix=skin.inverse_bind_matrices[bone_idx],
            bind_translation=node.translation.copy(),
            bind_rotation=node.rotation.copy(),
            bind_scale=node.scale.copy(),
        )
        bones.append(bone)
        node_to_bone[node_idx] = bone_idx

    return SkeletonData(bones=bones)


_DEBUG_ENTITY_CREATION = False
_debug_entity_count = 0


class _PendingSkinnedMesh:
    """Placeholder for skinned mesh that needs skeleton instance set later."""
    def __init__(self, entity: Entity, drawable: MeshDrawable, material):
        self.entity = entity
        self.drawable = drawable
        self.material = material


def _create_entity_from_node(
    node_index: int,
    scene_data: GLBSceneData,
    mesh_drawables: Dict[int, MeshDrawable],
    default_material: DefaultMaterial,
    skinned_material,
    glb_name: str = "",
    node_to_entity: Optional[Dict[int, Entity]] = None,
    pending_skinned: Optional[List[_PendingSkinnedMesh]] = None,
) -> Entity:
    """Recursively create Entity hierarchy from GLBNodeData.

    Args:
        node_to_entity: Dict to collect node_index -> Entity mapping
        pending_skinned: List to collect skinned meshes that need skeleton set later
    """
    global _debug_entity_count
    node = scene_data.nodes[node_index]

    # Create pose from translation, rotation, and scale
    pose = GeneralPose3(lin=node.translation, ang=node.rotation, scale=node.scale)

    if _DEBUG_ENTITY_CREATION and ("Hips" in node.name or _debug_entity_count < 3):
        _debug_entity_count += 1
        print(f"[GLB] Creating entity {node.name!r}:")
        print(f"  node.translation: {node.translation}")
        print(f"  node.rotation: {node.rotation}")
        print(f"  node.scale: {node.scale}")
        print(f"  pose.ang (quaternion): {pose.ang}")
        print(f"  pose.lin: {pose.lin}")

    entity = Entity(pose=pose, name=node.name)

    # Track node -> entity mapping
    if node_to_entity is not None:
        node_to_entity[node_index] = entity

    # Add renderer for each primitive in the referenced mesh
    if node.mesh_index is not None and node.mesh_index in scene_data.mesh_index_map:
        our_mesh_indices = scene_data.mesh_index_map[node.mesh_index]

        for mesh_idx in our_mesh_indices:
            glb_mesh = scene_data.meshes[mesh_idx]

            # Get MeshDrawable from cache or ResourceManager
            if mesh_idx not in mesh_drawables:
                mesh_name = f"{glb_name}_{glb_mesh.name}" if glb_name else glb_mesh.name
                from termin.visualization.core.resources import ResourceManager
                rm = ResourceManager.instance()
                drawable = rm.meshes.get(mesh_name)

                if drawable is None:
                    raise RuntimeError(f"[glb_instantiator] Mesh '{mesh_name}' not found in ResourceManager")

                mesh_drawables[mesh_idx] = drawable

            drawable = mesh_drawables[mesh_idx]

            # Defer skinned mesh setup - skeleton not ready yet
            if glb_mesh.is_skinned and pending_skinned is not None:
                pending_skinned.append(_PendingSkinnedMesh(entity, drawable, skinned_material))
            else:
                renderer = MeshRenderer(mesh=drawable, material=default_material)
                entity.add_component(renderer)

    # Recursively create children
    for child_index in node.children:
        child_entity = _create_entity_from_node(
            child_index, scene_data, mesh_drawables, default_material, skinned_material,
            glb_name, node_to_entity, pending_skinned
        )
        entity.transform.add_child(child_entity.transform)

    return entity


class GLBInstantiateResult:
    """Result of GLB instantiation containing entity and resources."""

    def __init__(
        self,
        entity: Entity,
        skeleton_controller: Optional[SkeletonController] = None,
        animation_player: Optional[AnimationPlayer] = None,
    ):
        self.entity = entity
        self.skeleton_controller = skeleton_controller
        self.animation_player = animation_player

    @property
    def skeleton_instance(self) -> Optional[SkeletonInstance]:
        """Get skeleton instance from controller (for backwards compatibility)."""
        if self.skeleton_controller is not None:
            return self.skeleton_controller.skeleton_instance
        return None


def instantiate_glb(
    path: Path,
    name: str = None,
    normalize_scale: bool | None = None,
    convert_to_z_up: bool | None = None,
    blender_z_up_fix: bool | None = None,
) -> GLBInstantiateResult:
    """
    Load GLB file and create Entity hierarchy.

    Args:
        path: Path to the GLB file.
        name: Optional name for the root entity. Defaults to filename without extension.
        normalize_scale: If True, normalize root scale to 1.0.
                        If None, reads from .glb.spec file.
        convert_to_z_up: If True, convert from glTF Y-up to engine Z-up.
                        If None, reads from .glb.spec file (default True).
        blender_z_up_fix: If True, compensate for Blender's -90°X rotation on Armature.
                         If None, reads from .glb.spec file (default False).

    Returns:
        GLBInstantiateResult containing root Entity, SkeletonInstance, and AnimationPlayer.
    """
    # Read settings from spec if not explicitly provided
    from termin.editor.project_file_watcher import FilePreLoader
    from termin.visualization.core.resources import ResourceManager

    spec_data = FilePreLoader.read_spec_file(str(path))

    if name is None:
        name = path.stem

    rm = ResourceManager.instance()

    # Try to get GLBAsset from ResourceManager by UUID (already loaded by GLBPreLoader)
    glb_asset = None
    glb_uuid = spec_data.get("uuid") if spec_data else None
    if glb_uuid:
        from termin.visualization.core.glb_asset import GLBAsset
        asset = rm.get_asset_by_uuid(glb_uuid)
        if isinstance(asset, GLBAsset):
            glb_asset = asset

    if glb_asset is not None and glb_asset.scene_data is not None:
        print(f"[GLB] Using cached GLBAsset: {name} (uuid={glb_uuid})")
        scene_data = glb_asset.scene_data
    else:
        # Fallback: load directly (for programmatic use without PreLoader)
        if normalize_scale is None:
            normalize_scale = spec_data.get("normalize_scale", False) if spec_data else False
        if convert_to_z_up is None:
            convert_to_z_up = spec_data.get("convert_to_z_up", True) if spec_data else True
        if blender_z_up_fix is None:
            blender_z_up_fix = spec_data.get("blender_z_up_fix", False) if spec_data else False

        print(f"[GLB] Loading: {path.name}, normalize_scale={normalize_scale}, convert_to_z_up={convert_to_z_up}, blender_z_up_fix={blender_z_up_fix}")

        scene_data = load_glb_file_normalized(
            str(path),
            normalize_scale=normalize_scale,
            convert_to_z_up=convert_to_z_up,
            blender_z_up_fix=blender_z_up_fix,
        )

    # Get materials from ResourceManager (must be registered as builtins)
    default_material = rm.get_material("DefaultMaterial")
    skinned_material = rm.get_material("SkinnedMaterial")

    if default_material is None or skinned_material is None:
        raise RuntimeError(
            f"[glb_instantiator] Builtin materials not registered: "
            f"DefaultMaterial={default_material is not None}, SkinnedMaterial={skinned_material is not None}"
        )

    # Cache for MeshDrawables (shared between nodes referencing same mesh)
    mesh_drawables: Dict[int, MeshDrawable] = {}

    # Collect node_index -> Entity mapping for bone lookup
    node_to_entity: Dict[int, Entity] = {}

    # Collect skinned meshes that need skeleton set later
    pending_skinned: List[_PendingSkinnedMesh] = []

    # Step 1: Create Entity hierarchy first (before skeleton)
    root_entity = None
    if scene_data.root_nodes:
        if len(scene_data.root_nodes) == 1:
            # Single root - use it directly
            root_entity = _create_entity_from_node(
                scene_data.root_nodes[0],
                scene_data,
                mesh_drawables,
                default_material,
                skinned_material,
                glb_name=name,
                node_to_entity=node_to_entity,
                pending_skinned=pending_skinned,
            )
            root_entity.name = name
        else:
            # Multiple roots - create wrapper entity
            root_entity = Entity(pose=Pose3.identity(), name=name)
            for root_index in scene_data.root_nodes:
                child_entity = _create_entity_from_node(
                    root_index,
                    scene_data,
                    mesh_drawables,
                    default_material,
                    skinned_material,
                    glb_name=name,
                    node_to_entity=node_to_entity,
                    pending_skinned=pending_skinned,
                )
                root_entity.transform.add_child(child_entity.transform)
    else:
        # No hierarchy - create flat structure from meshes
        root_entity = Entity(pose=Pose3.identity(), name=name)

        for i, glb_mesh in enumerate(scene_data.meshes):
            mesh_name = f"{name}_{glb_mesh.name}" if name else glb_mesh.name

            drawable = rm.meshes.get(mesh_name)
            if drawable is None:
                raise RuntimeError(f"[glb_instantiator] Mesh '{mesh_name}' not found in ResourceManager")

            mesh_drawables[i] = drawable

            mesh_entity = Entity(pose=Pose3.identity(), name=glb_mesh.name)
            renderer = MeshRenderer(mesh=drawable, material=default_material)
            mesh_entity.add_component(renderer)
            root_entity.transform.add_child(mesh_entity.transform)

    # Step 2: Create skeleton controller with bone entities
    skeleton_controller: Optional[SkeletonController] = None
    if scene_data.skins:
        skin = scene_data.skins[0]  # Use first skin

        # Get skeleton from ResourceManager (registered by GLBAsset)
        skeleton_name = f"{name}_skeleton"
        skeleton_data = rm.get_skeleton(skeleton_name)

        if skeleton_data is None:
            raise RuntimeError(f"[glb_instantiator] Skeleton '{skeleton_name}' not found in ResourceManager")

        # Debug: print first few bones
        print(f"[GLB] Skeleton: {len(skeleton_data.bones)} bones")
        for i, bone in enumerate(skeleton_data.bones[:3]):
            print(f"  Bone[{i}] {bone.name}:")
            print(f"    bind_translation: {bone.bind_translation}")
            print(f"    bind_rotation: {bone.bind_rotation}")

        # Collect bone entities from node_to_entity mapping
        bone_entities: List[Entity] = []
        for node_idx in skin.joint_node_indices:
            entity = node_to_entity.get(node_idx)
            if entity is None:
                print(f"[GLB] WARNING: No entity for bone node {node_idx}")
                # Create dummy entity as fallback
                entity = Entity(pose=Pose3.identity(), name=f"missing_bone_{node_idx}")
            bone_entities.append(entity)

        print(f"[GLB] Collected {len(bone_entities)} bone entities")

        # Create SkeletonController and add to root entity
        skeleton_controller = SkeletonController(
            skeleton_data=skeleton_data,
            bone_entities=bone_entities,
        )
        root_entity.add_component(skeleton_controller)

    # Step 3: Setup SkinnedMeshRenderers now that skeleton is ready
    for pending in pending_skinned:
        if skeleton_controller is not None:
            renderer = SkinnedMeshRenderer(
                mesh=pending.drawable,
                material=pending.material,
                skeleton_controller=skeleton_controller,
            )
            pending.entity.add_component(renderer)

    # Setup animations - get clips from ResourceManager (registered by GLBAsset)
    animation_player: Optional[AnimationPlayer] = None
    clips: List[AnimationClip] = []

    if scene_data.animations:
        animation_player = AnimationPlayer()

        for glb_anim in scene_data.animations:
            clip_name = f"{name}_{glb_anim.name}"
            asset = rm.get_animation_clip_asset(clip_name)

            if asset is None or asset.clip is None:
                raise RuntimeError(f"[glb_instantiator] Animation clip '{clip_name}' not found in ResourceManager")

            clips.append(asset.clip)
            animation_player.add_clip(asset.clip)

        if clips:
            # Add player to root entity
            root_entity.add_component(animation_player)

            # Auto-play longest animation (skip short T-pose clips)
            best_clip = max(clips, key=lambda c: c.duration)
            print(f"[GLB] Available animations: {[(c.name, f'{c.duration:.2f}s') for c in clips]}")
            print(f"[GLB] Auto-playing: {best_clip.name!r} (duration={best_clip.duration:.2f}s)")
            animation_player.play(best_clip.name)

    return GLBInstantiateResult(
        entity=root_entity,
        skeleton_controller=skeleton_controller,
        animation_player=animation_player,
    )
