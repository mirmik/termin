# termin/loaders/glb_instantiator.py
"""GLB instantiator - creates Entity hierarchy from GLBAsset."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

import numpy as np

from termin.geombase import Pose3
from termin.geombase import GeneralPose3
from termin.skeleton import Bone, SkeletonData, SkeletonInstance
from termin.visualization.core.entity import Entity
from termin.mesh import TcMesh
from termin.visualization.render.components.mesh_renderer import MeshRenderer
from termin.visualization.render.components.skinned_mesh_renderer import SkinnedMeshRenderer
from termin.visualization.render.components.skeleton_controller import SkeletonController
from termin.visualization.animation.player import AnimationPlayer
from termin.visualization.animation.clip import AnimationClip

if TYPE_CHECKING:
    from termin.assets.mesh_asset import MeshAsset
    from termin.visualization.core.glb_asset import GLBAsset
    from termin.visualization.core.scene import Scene
    from termin.loaders.glb_loader import GLBSceneData, GLBMeshData


def _compute_vertex_normals(vertices: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Compute per-vertex normals from vertices and triangle indices."""
    normals = np.zeros_like(vertices, dtype=np.float32)
    num_tris = len(indices) // 3
    for t in range(num_tris):
        i0, i1, i2 = indices[t * 3], indices[t * 3 + 1], indices[t * 3 + 2]
        v0, v1, v2 = vertices[i0], vertices[i1], vertices[i2]
        e1 = v1 - v0
        e2 = v2 - v0
        face_normal = np.cross(e1, e2)
        normals[i0] += face_normal
        normals[i1] += face_normal
        normals[i2] += face_normal
    # Normalize
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    lengths = np.where(lengths < 1e-8, 1.0, lengths)
    return normals / lengths


def _glb_mesh_to_tc_mesh(glb_mesh: "GLBMeshData", uuid: str = "") -> "TcMesh":
    """Convert GLBMeshData to TcMesh directly (no intermediate Mesh3).

    Args:
        glb_mesh: Mesh data from GLB file
        uuid: Optional UUID to use for TcMesh (if empty, generates new)
    """
    from termin.mesh._mesh_native import TcMesh, TcVertexLayout

    vertices = glb_mesh.vertices.astype(np.float32)
    indices = glb_mesh.indices.astype(np.uint32).ravel()
    num_verts = len(vertices)

    # Compute normals if not provided
    if glb_mesh.normals is not None:
        normals = glb_mesh.normals.astype(np.float32)
    else:
        normals = _compute_vertex_normals(vertices, indices)

    # UVs (default to zeros)
    if glb_mesh.uvs is not None:
        uvs = glb_mesh.uvs.astype(np.float32)
    else:
        uvs = np.zeros((num_verts, 2), dtype=np.float32)

    is_skinned = glb_mesh.is_skinned

    if is_skinned:
        # Skinned layout: pos(3) + normal(3) + uv(2) + joints(4) + weights(4) = 16 floats = 64 bytes
        layout = TcVertexLayout.skinned()
        stride = 64

        # Joint indices and weights
        joint_indices = glb_mesh.joint_indices.astype(np.float32)  # stored as float for GPU
        joint_weights = glb_mesh.joint_weights.astype(np.float32)

        # Build interleaved buffer
        buffer = np.zeros((num_verts, 16), dtype=np.float32)
        buffer[:, 0:3] = vertices
        buffer[:, 3:6] = normals
        buffer[:, 6:8] = uvs
        buffer[:, 8:12] = joint_indices
        buffer[:, 12:16] = joint_weights
    else:
        # Standard layout: pos(3) + normal(3) + uv(2) = 8 floats = 32 bytes
        layout = TcVertexLayout.pos_normal_uv()
        stride = 32

        # Build interleaved buffer
        buffer = np.zeros((num_verts, 8), dtype=np.float32)
        buffer[:, 0:3] = vertices
        buffer[:, 3:6] = normals
        buffer[:, 6:8] = uvs

    # Flatten buffer for TcMesh
    buffer_flat = buffer.ravel().astype(np.float32)

    return TcMesh.from_interleaved(
        buffer_flat, num_verts, indices, layout, glb_mesh.name, uuid
    )


def _populate_tc_mesh_from_glb(tc_mesh: TcMesh, glb_mesh: "GLBMeshData") -> bool:
    """Populate an existing declared TcMesh with data from GLBMeshData.

    Returns True if successful, False otherwise.
    """
    from termin.mesh._mesh_native import TcVertexLayout, tc_mesh_set_data

    vertices = glb_mesh.vertices.astype(np.float32)
    indices = glb_mesh.indices.astype(np.uint32).ravel()
    num_verts = len(vertices)

    # Compute normals if not provided
    if glb_mesh.normals is not None:
        normals = glb_mesh.normals.astype(np.float32)
    else:
        normals = _compute_vertex_normals(vertices, indices)

    # UVs (default to zeros)
    if glb_mesh.uvs is not None:
        uvs = glb_mesh.uvs.astype(np.float32)
    else:
        uvs = np.zeros((num_verts, 2), dtype=np.float32)

    is_skinned = glb_mesh.is_skinned

    if is_skinned:
        layout = TcVertexLayout.skinned()

        joint_indices = glb_mesh.joint_indices.astype(np.float32)
        joint_weights = glb_mesh.joint_weights.astype(np.float32)

        buffer = np.zeros((num_verts, 16), dtype=np.float32)
        buffer[:, 0:3] = vertices
        buffer[:, 3:6] = normals
        buffer[:, 6:8] = uvs
        buffer[:, 8:12] = joint_indices
        buffer[:, 12:16] = joint_weights
    else:
        layout = TcVertexLayout.pos_normal_uv()

        buffer = np.zeros((num_verts, 8), dtype=np.float32)
        buffer[:, 0:3] = vertices
        buffer[:, 3:6] = normals
        buffer[:, 6:8] = uvs

    buffer_flat = buffer.ravel().astype(np.float32)

    return tc_mesh_set_data(tc_mesh, buffer_flat, num_verts, layout, indices, glb_mesh.name)


class _PendingSkinnedMesh:
    """Placeholder for skinned mesh that needs skeleton instance set later."""
    def __init__(self, entity: Entity, mesh: TcMesh, material):
        self.entity = entity
        self.mesh = mesh
        self.material = material


def _create_entity_from_node(
    node_index: int,
    scene_data: "GLBSceneData",
    meshes: Dict[int, TcMesh],
    mesh_assets: Dict[str, "MeshAsset"],
    default_material,
    skinned_material,
    node_to_entity: Optional[Dict[int, Entity]] = None,
    pending_skinned: Optional[List[_PendingSkinnedMesh]] = None,
    scene: Optional["Scene"] = None,
) -> Entity:
    """Recursively create Entity hierarchy from GLBNodeData."""
    from termin.visualization.core.scene import Scene

    node = scene_data.nodes[node_index]
    pose = GeneralPose3(lin=node.translation, ang=node.rotation, scale=node.scale)

    # Create entity in scene's pool if scene provided, else standalone
    if scene is not None:
        entity = scene.create_entity(node.name)
        entity.transform.relocate(pose)
    else:
        entity = Entity(pose=pose, name=node.name)

    if node_to_entity is not None:
        node_to_entity[node_index] = entity

    # Add renderer for each primitive in the referenced mesh
    if node.mesh_index is not None and node.mesh_index in scene_data.mesh_index_map:
        our_mesh_indices = scene_data.mesh_index_map[node.mesh_index]

        for mesh_idx in our_mesh_indices:
            glb_mesh = scene_data.meshes[mesh_idx]

            if mesh_idx not in meshes:
                # Get tc_mesh from MeshAsset by mesh name
                mesh_asset = mesh_assets.get(glb_mesh.name)
                if mesh_asset is None or mesh_asset.data is None:
                    raise RuntimeError(f"[glb_instantiator] MeshAsset for '{glb_mesh.name}' not found or not loaded")

                tc_mesh = mesh_asset.data
                if not tc_mesh.is_valid:
                    raise RuntimeError(f"[glb_instantiator] TcMesh for '{glb_mesh.name}' is invalid")

                meshes[mesh_idx] = tc_mesh

            tc_mesh = meshes[mesh_idx]

            if glb_mesh.is_skinned and pending_skinned is not None:
                from termin._native import log
                log.info(f"[glb_instantiator] pending skinned mesh={glb_mesh.name} tc_mesh.is_valid={tc_mesh.is_valid} uuid={tc_mesh.uuid}")
                pending_skinned.append(_PendingSkinnedMesh(entity, tc_mesh, skinned_material))
            else:
                renderer = MeshRenderer(mesh=tc_mesh, material=default_material)
                entity.add_component(renderer)

    # Recursively create children
    for child_index in node.children:
        child_entity = _create_entity_from_node(
            child_index, scene_data, meshes, mesh_assets, default_material, skinned_material,
            node_to_entity, pending_skinned, scene
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
        # Debug: keep references to prevent premature destruction
        _bone_entities: Optional[List] = None,
        _clips: Optional[List] = None,
    ):
        self.entity = entity
        self.skeleton_controller = skeleton_controller
        self.animation_player = animation_player
        self._bone_entities = _bone_entities
        self._clips = _clips

    @property
    def skeleton_instance(self) -> Optional[SkeletonInstance]:
        """Get skeleton instance from controller (for backwards compatibility)."""
        if self.skeleton_controller is not None:
            return self.skeleton_controller.skeleton_instance
        return None


def instantiate_glb(
    glb_asset: "GLBAsset",
    name: str | None = None,
    scene: Optional["Scene"] = None,
) -> GLBInstantiateResult:
    """
    Create Entity hierarchy from GLBAsset.

    Args:
        glb_asset: GLBAsset to instantiate (will be loaded if not already).
        name: Optional name for the root entity. Defaults to asset name.
        scene: Optional Scene - if provided, entities are created directly in
               scene's pool (recommended). Otherwise entities are created in
               standalone pool and migrated when added to scene.

    Returns:
        GLBInstantiateResult containing root Entity, SkeletonController, and AnimationPlayer.
    """
    from termin.visualization.core.resources import ResourceManager
    from termin.visualization.core.scene import Scene

    # Access scene_data triggers lazy loading and populates child assets
    scene_data = glb_asset.scene_data
    if scene_data is None:
        raise RuntimeError(f"[glb_instantiator] Failed to load GLBAsset '{glb_asset.name}'")

    # Get mesh assets from GLBAsset
    mesh_assets = glb_asset.get_mesh_assets()

    if name is None:
        name = glb_asset.name

    rm = ResourceManager.instance()

    # Get materials (as assets for proper serialization)
    default_material_asset = rm.get_material_asset("DefaultMaterial")
    # Use StandartMaterial for skinned meshes - SkinnedMeshRenderer will inject skinning
    skinned_material_asset = rm.get_material_asset("StandartMaterial")

    if default_material_asset is None or skinned_material_asset is None:
        raise RuntimeError(
            f"[glb_instantiator] Builtin materials not registered: "
            f"DefaultMaterial={default_material_asset is not None}, StandartMaterial={skinned_material_asset is not None}"
        )

    meshes: Dict[int, TcMesh] = {}
    node_to_entity: Dict[int, Entity] = {}
    pending_skinned: List[_PendingSkinnedMesh] = []

    # Helper to create entity in scene's pool or standalone
    def create_entity(entity_name: str) -> Entity:
        if scene is not None:
            ent = scene.create_entity(entity_name)
            ent.transform.relocate(Pose3.identity())
            return ent
        return Entity(pose=Pose3.identity(), name=entity_name)

    # Step 1: Create Entity hierarchy
    root_entity = None
    if scene_data.root_nodes:
        if len(scene_data.root_nodes) == 1:
            root_entity = _create_entity_from_node(
                scene_data.root_nodes[0],
                scene_data,
                meshes,
                mesh_assets,
                default_material_asset,
                skinned_material_asset,
                node_to_entity=node_to_entity,
                pending_skinned=pending_skinned,
                scene=scene,
            )
            root_entity.name = name
        else:
            root_entity = create_entity(name)
            for root_index in scene_data.root_nodes:
                child_entity = _create_entity_from_node(
                    root_index,
                    scene_data,
                    meshes,
                    mesh_assets,
                    default_material_asset,
                    skinned_material_asset,
                    node_to_entity=node_to_entity,
                    pending_skinned=pending_skinned,
                    scene=scene,
                )
                root_entity.transform.add_child(child_entity.transform)
    else:
        # Fallback: no node hierarchy, create entities for each mesh directly
        root_entity = create_entity(name)
        for i, glb_mesh in enumerate(scene_data.meshes):
            mesh_asset = mesh_assets.get(glb_mesh.name)
            if mesh_asset is None or mesh_asset.data is None:
                raise RuntimeError(f"[glb_instantiator] MeshAsset for '{glb_mesh.name}' not found or not loaded")

            tc_mesh = mesh_asset.data
            if not tc_mesh.is_valid:
                raise RuntimeError(f"[glb_instantiator] TcMesh for '{glb_mesh.name}' is invalid")

            meshes[i] = tc_mesh
            mesh_entity = create_entity(glb_mesh.name)
            renderer = MeshRenderer(mesh=tc_mesh, material=default_material_asset)
            mesh_entity.add_component(renderer)
            root_entity.transform.add_child(mesh_entity.transform)

    # Step 2: Create skeleton controller
    skeleton_controller: Optional[SkeletonController] = None
    bone_entities: List[Entity] = []  # keep reference for debug
    if scene_data.skins:
        skin = scene_data.skins[0]

        # Get skeleton from GLBAsset's child assets
        skeleton_assets = glb_asset.get_skeleton_assets()
        skeleton_key = "skeleton"
        skeleton_asset = skeleton_assets.get(skeleton_key)

        if skeleton_asset is None or skeleton_asset.skeleton_data is None:
            raise RuntimeError(f"[glb_instantiator] Skeleton not found in GLBAsset '{glb_asset.name}'")

        # Collect bone entities
        for node_idx in skin.joint_node_indices:
            entity = node_to_entity.get(node_idx)
            if entity is None:
                entity = create_entity(f"missing_bone_{node_idx}")
            bone_entities.append(entity)

        skeleton_controller = SkeletonController(
            skeleton=skeleton_asset,
            bone_entities=bone_entities,
        )
        root_entity.add_component(skeleton_controller)

    # Step 3: Setup SkinnedMeshRenderers
    from termin._native import log
    for pending in pending_skinned:
        if skeleton_controller is not None:
            log.info(f"[glb_instantiator] creating SkinnedMeshRenderer mesh.is_valid={pending.mesh.is_valid} uuid={pending.mesh.uuid} name={pending.mesh.name}")
            renderer = SkinnedMeshRenderer(
                mesh=pending.mesh,
                material=pending.material,
                skeleton_controller=skeleton_controller,
            )
            pending.entity.add_component(renderer)

    # Step 4: Setup animations from GLBAsset's child assets
    animation_player: Optional[AnimationPlayer] = None
    clips: List[AnimationClip] = []  # keep reference for debug
    animation_assets = glb_asset.get_animation_assets()

    if animation_assets:
        animation_player = AnimationPlayer()

        for anim_name, anim_asset in animation_assets.items():
            clip = anim_asset.clip
            if clip is not None:
                clips.append(clip)
                animation_player.add_clip(clip, asset=anim_asset)

        if clips:
            root_entity.add_component(animation_player)

    return GLBInstantiateResult(
        entity=root_entity,
        skeleton_controller=skeleton_controller,
        animation_player=animation_player,
        _bone_entities=bone_entities,
        _clips=clips,
    )
