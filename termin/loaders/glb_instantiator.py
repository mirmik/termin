# termin/loaders/glb_instantiator.py
"""GLB instantiator - creates Entity hierarchy from GLBAsset."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from termin.geombase import Pose3
from termin.geombase import GeneralPose3
from termin.mesh.mesh import Mesh3
from termin.mesh.skinned_mesh import SkinnedMesh3
from termin.skeleton import Bone, SkeletonData, SkeletonInstance
from termin.visualization.core.entity import Entity
from termin.visualization.core.mesh_handle import MeshHandle
from termin.visualization.render.components.mesh_renderer import MeshRenderer
from termin.visualization.render.components.skinned_mesh_renderer import SkinnedMeshRenderer
from termin.visualization.render.components.skeleton_controller import SkeletonController
from termin.visualization.animation.player import AnimationPlayer
from termin.visualization.animation.clip import AnimationClip

if TYPE_CHECKING:
    from termin.visualization.core.glb_asset import GLBAsset
    from termin.visualization.core.scene import Scene
    from termin.loaders.glb_loader import GLBSceneData, GLBMeshData


def _glb_mesh_to_mesh3(glb_mesh: "GLBMeshData") -> Mesh3 | SkinnedMesh3:
    """Convert GLBMeshData to Mesh3 or SkinnedMesh3."""
    vertices = glb_mesh.vertices
    indices = glb_mesh.indices.reshape(-1, 3)
    name = glb_mesh.name

    if glb_mesh.is_skinned:
        mesh = SkinnedMesh3(
            name=name,
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
        mesh = Mesh3(name=name, vertices=vertices, triangles=indices, uvs=glb_mesh.uvs)
        if glb_mesh.normals is not None:
            mesh.vertex_normals = glb_mesh.normals
        else:
            mesh.compute_vertex_normals()

    return mesh


class _PendingSkinnedMesh:
    """Placeholder for skinned mesh that needs skeleton instance set later."""
    def __init__(self, entity: Entity, mesh_handle: MeshHandle, material):
        self.entity = entity
        self.mesh_handle = mesh_handle
        self.material = material


def _create_entity_from_node(
    node_index: int,
    scene_data: "GLBSceneData",
    mesh_handles: Dict[int, MeshHandle],
    default_material,
    skinned_material,
    glb_name: str = "",
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

            if mesh_idx not in mesh_handles:
                mesh_name = f"{glb_name}_{glb_mesh.name}" if glb_name else glb_mesh.name
                from termin.visualization.core.resources import ResourceManager
                rm = ResourceManager.instance()
                mesh_handle = rm.get_mesh(mesh_name)

                if mesh_handle is None:
                    raise RuntimeError(f"[glb_instantiator] Mesh '{mesh_name}' not found in ResourceManager")

                mesh_handles[mesh_idx] = mesh_handle

            mesh_handle = mesh_handles[mesh_idx]

            if glb_mesh.is_skinned and pending_skinned is not None:
                pending_skinned.append(_PendingSkinnedMesh(entity, mesh_handle, skinned_material))
            else:
                renderer = MeshRenderer(mesh=mesh_handle, material=default_material)
                entity.add_component(renderer)

    # Recursively create children
    for child_index in node.children:
        child_entity = _create_entity_from_node(
            child_index, scene_data, mesh_handles, default_material, skinned_material,
            glb_name, node_to_entity, pending_skinned, scene
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

    if name is None:
        name = glb_asset.name

    rm = ResourceManager.instance()

    # Get materials
    default_material = rm.get_material("DefaultMaterial")
    skinned_material = rm.get_material("SkinnedMaterial")

    if default_material is None or skinned_material is None:
        raise RuntimeError(
            f"[glb_instantiator] Builtin materials not registered: "
            f"DefaultMaterial={default_material is not None}, SkinnedMaterial={skinned_material is not None}"
        )

    mesh_handles: Dict[int, MeshHandle] = {}
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
                mesh_handles,
                default_material,
                skinned_material,
                glb_name=name,
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
                    mesh_handles,
                    default_material,
                    skinned_material,
                    glb_name=name,
                    node_to_entity=node_to_entity,
                    pending_skinned=pending_skinned,
                    scene=scene,
                )
                root_entity.transform.add_child(child_entity.transform)
    else:
        root_entity = create_entity(name)
        for i, glb_mesh in enumerate(scene_data.meshes):
            mesh_name = f"{name}_{glb_mesh.name}"
            mesh_handle = rm.get_mesh(mesh_name)
            if mesh_handle is None:
                raise RuntimeError(f"[glb_instantiator] Mesh '{mesh_name}' not found in ResourceManager")

            mesh_handles[i] = mesh_handle
            mesh_entity = create_entity(glb_mesh.name)
            renderer = MeshRenderer(mesh=mesh_handle, material=default_material)
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
    for pending in pending_skinned:
        if skeleton_controller is not None:
            renderer = SkinnedMeshRenderer(
                mesh=pending.mesh_handle,
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
