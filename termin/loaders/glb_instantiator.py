# termin/loaders/glb_instantiator.py
"""GLB instantiator - creates Entity hierarchy from GLB files."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from termin.geombase.pose3 import Pose3
from termin.mesh.mesh import Mesh3
from termin.mesh.skinned_mesh import SkinnedMesh3
from termin.skeleton.bone import Bone
from termin.skeleton.skeleton import SkeletonData, SkeletonInstance
from termin.visualization.core.entity import Entity
from termin.visualization.core.mesh import MeshDrawable
from termin.visualization.render.components.mesh_renderer import MeshRenderer
from termin.visualization.render.components.skinned_mesh_renderer import SkinnedMeshRenderer
from termin.visualization.render.materials.default_material import DefaultMaterial
from termin.visualization.animation.player import AnimationPlayer
from termin.visualization.animation.clip import AnimationClip

from termin.loaders.glb_loader import (
    load_glb_file,
    load_glb_file_normalized,
    normalize_glb_scale,
    GLBSceneData,
    GLBNodeData,
    GLBMeshData,
    GLBSkinData,
)


def _compute_trs_matrix(
    translation: np.ndarray,
    rotation: np.ndarray,
    scale: np.ndarray,
) -> np.ndarray:
    """
    Compute 4x4 transform matrix from Translation, Rotation, Scale.

    Args:
        translation: (3,) position
        rotation: (4,) quaternion [x, y, z, w]
        scale: (3,) scale factors

    Returns:
        4x4 transformation matrix = T * R * S
    """
    # Build rotation matrix from quaternion
    x, y, z, w = rotation
    r = np.array([
        [1 - 2*(y*y + z*z),     2*(x*y - z*w),     2*(x*z + y*w), 0],
        [    2*(x*y + z*w), 1 - 2*(x*x + z*z),     2*(y*z - x*w), 0],
        [    2*(x*z - y*w),     2*(y*z + x*w), 1 - 2*(x*x + y*y), 0],
        [                0,                 0,                 0, 1],
    ], dtype=np.float32)

    # Apply scale
    r[0, :3] *= scale[0]
    r[1, :3] *= scale[1]
    r[2, :3] *= scale[2]

    # Apply translation
    r[0, 3] = translation[0]
    r[1, 3] = translation[1]
    r[2, 3] = translation[2]

    return r


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


def _create_entity_from_node(
    node_index: int,
    scene_data: GLBSceneData,
    mesh_drawables: Dict[int, MeshDrawable],
    default_material: DefaultMaterial,
    skinned_material,
    skeleton_instance: Optional[SkeletonInstance] = None,
    glb_name: str = "",
) -> Entity:
    """Recursively create Entity hierarchy from GLBNodeData."""
    node = scene_data.nodes[node_index]

    # Create pose from translation and rotation
    pose = Pose3(lin=node.translation, ang=node.rotation)
    scale = node.scale

    entity = Entity(pose=pose, name=node.name, scale=scale)

    # Determine if this node has a skin (skeleton)
    node_skeleton = skeleton_instance
    if node.skin_index is not None and node.skin_index < len(scene_data.skins):
        # This node has a skin - create skeleton if not already done
        if skeleton_instance is None:
            skin = scene_data.skins[node.skin_index]
            skeleton_data = _create_skeleton_from_skin(skin, scene_data.nodes)
            node_skeleton = SkeletonInstance(skeleton_data)

    # Add renderer for each primitive in the referenced mesh
    if node.mesh_index is not None and node.mesh_index in scene_data.mesh_index_map:
        our_mesh_indices = scene_data.mesh_index_map[node.mesh_index]

        for mesh_idx in our_mesh_indices:
            glb_mesh = scene_data.meshes[mesh_idx]

            # Get or create MeshDrawable
            if mesh_idx not in mesh_drawables:
                # Try to get from ResourceManager first (registered by GLBAsset)
                mesh_name = f"{glb_name}_{glb_mesh.name}" if glb_name else glb_mesh.name
                from termin.visualization.core.resources import ResourceManager
                rm = ResourceManager.instance()
                drawable = rm.meshes.get(mesh_name)

                if drawable is None:
                    # Fallback: create new MeshDrawable
                    mesh3 = _glb_mesh_to_mesh3(glb_mesh)
                    drawable = MeshDrawable(mesh3, name=mesh_name)
                    rm.meshes[mesh_name] = drawable

                mesh_drawables[mesh_idx] = drawable

            drawable = mesh_drawables[mesh_idx]

            # Use SkinnedMeshRenderer with SkinnedMaterial for skinned meshes
            _DEBUG_INSTANTIATE = True
            if _DEBUG_INSTANTIATE:
                print(f"[glb_instantiator] mesh={glb_mesh.name!r}, is_skinned={glb_mesh.is_skinned}, node_skeleton={node_skeleton}")
            if glb_mesh.is_skinned and node_skeleton is not None:
                if _DEBUG_INSTANTIATE:
                    print(f"  -> Creating SkinnedMeshRenderer with material={skinned_material}")
                    print(f"     material type: {type(skinned_material).__name__}")
                    if skinned_material:
                        print(f"     material phases: {len(skinned_material.phases)}")
                renderer = SkinnedMeshRenderer(
                    mesh=drawable,
                    material=skinned_material,
                    skeleton_instance=node_skeleton,
                )
                if _DEBUG_INSTANTIATE:
                    print(f"  -> renderer._material_handle._direct={renderer._material_handle._direct}")
            else:
                renderer = MeshRenderer(mesh=drawable, material=default_material)

            entity.add_component(renderer)

    # Recursively create children
    for child_index in node.children:
        child_entity = _create_entity_from_node(
            child_index, scene_data, mesh_drawables, default_material, skinned_material, node_skeleton, glb_name
        )
        entity.transform.add_child(child_entity.transform)

    return entity


class GLBInstantiateResult:
    """Result of GLB instantiation containing entity and resources."""

    def __init__(
        self,
        entity: Entity,
        skeleton_instance: Optional[SkeletonInstance] = None,
        animation_player: Optional[AnimationPlayer] = None,
    ):
        self.entity = entity
        self.skeleton_instance = skeleton_instance
        self.animation_player = animation_player


def _create_animation_clips(scene_data: GLBSceneData) -> List[AnimationClip]:
    """Convert GLB animations to AnimationClips."""
    clips = []

    for glb_anim in scene_data.animations:
        clip = AnimationClip.from_glb_clip(glb_anim)
        clips.append(clip)

    return clips


def instantiate_glb(
    path: Path,
    name: str = None,
    normalize_scale: bool | None = None,
    convert_to_z_up: bool | None = None,
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

    Returns:
        GLBInstantiateResult containing root Entity, SkeletonInstance, and AnimationPlayer.
    """
    # Read settings from spec if not explicitly provided
    from termin.editor.project_file_watcher import FilePreLoader
    spec_data = FilePreLoader.read_spec_file(str(path))

    if normalize_scale is None:
        normalize_scale = spec_data.get("normalize_scale", False) if spec_data else False

    if convert_to_z_up is None:
        convert_to_z_up = spec_data.get("convert_to_z_up", True) if spec_data else True

    scene_data = load_glb_file_normalized(
        str(path),
        normalize_scale=normalize_scale,
        convert_to_z_up=convert_to_z_up,
    )

    if name is None:
        name = path.stem

    # Get materials from ResourceManager
    from termin.visualization.core.resources import ResourceManager
    from termin.visualization.render.materials.skinned_material import SkinnedMaterial
    rm = ResourceManager.instance()
    default_material = rm.get_material("DefaultMaterial")
    if default_material is None:
        # Fallback if not registered yet
        default_material = DefaultMaterial(color=(0.8, 0.8, 0.8, 1.0))

    # Get or create skinned material for skeletal animation
    skinned_material = rm.get_material("SkinnedMaterial")
    if skinned_material is None:
        skinned_material = SkinnedMaterial(color=(0.8, 0.8, 0.8, 1.0))

    # Cache for MeshDrawables (shared between nodes referencing same mesh)
    mesh_drawables: Dict[int, MeshDrawable] = {}

    # Track skeleton instances created
    skeleton_instance: Optional[SkeletonInstance] = None

    # Create skeleton if we have skins
    if scene_data.skins:
        skin = scene_data.skins[0]  # Use first skin
        skeleton_data = _create_skeleton_from_skin(skin, scene_data.nodes)

        # Find skeleton root transform (Armature node that contains the skeleton)
        # This is the parent of the first joint, which contains the export scale
        skeleton_root_transform = None
        first_joint_idx = skin.joint_node_indices[0] if skin.joint_node_indices else None
        if first_joint_idx is not None:
            # Find parent of first joint
            for node_idx, node in enumerate(scene_data.nodes):
                if first_joint_idx in node.children:
                    # Compute root transform matrix from TRS
                    skeleton_root_transform = _compute_trs_matrix(
                        node.translation, node.rotation, node.scale
                    )
                    break

        skeleton_instance = SkeletonInstance(skeleton_data, root_transform=skeleton_root_transform)

    if scene_data.root_nodes:
        if len(scene_data.root_nodes) == 1:
            # Single root - use it directly
            root_entity = _create_entity_from_node(
                scene_data.root_nodes[0],
                scene_data,
                mesh_drawables,
                default_material,
                skinned_material,
                skeleton_instance,
                glb_name=name,
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
                    skeleton_instance,
                    glb_name=name,
                )
                root_entity.transform.add_child(child_entity.transform)
    else:
        # No hierarchy - create flat structure from meshes
        root_entity = Entity(pose=Pose3.identity(), name=name)

        for i, glb_mesh in enumerate(scene_data.meshes):
            mesh3 = _glb_mesh_to_mesh3(glb_mesh)
            mesh_name = f"{name}_{glb_mesh.name}" if name else glb_mesh.name
            drawable = MeshDrawable(mesh3, name=mesh_name)
            mesh_drawables[i] = drawable

            # Register mesh in ResourceManager
            rm.meshes[mesh_name] = drawable

            mesh_entity = Entity(pose=Pose3.identity(), name=glb_mesh.name)
            if glb_mesh.is_skinned and skeleton_instance is not None:
                renderer = SkinnedMeshRenderer(
                    mesh=drawable,
                    material=skinned_material,
                    skeleton_instance=skeleton_instance,
                )
            else:
                renderer = MeshRenderer(mesh=drawable, material=default_material)
            mesh_entity.add_component(renderer)

            root_entity.transform.add_child(mesh_entity.transform)

    # Setup animations
    animation_player: Optional[AnimationPlayer] = None
    if scene_data.animations:
        animation_player = AnimationPlayer()
        animation_player.target_skeleton = skeleton_instance

        clips = _create_animation_clips(scene_data)
        for clip in clips:
            animation_player.add_clip(clip)

        # Add player to root entity
        root_entity.add_component(animation_player)

        # Auto-play first animation
        if clips:
            animation_player.play(clips[0].name)

    return GLBInstantiateResult(
        entity=root_entity,
        skeleton_instance=skeleton_instance,
        animation_player=animation_player,
    )
