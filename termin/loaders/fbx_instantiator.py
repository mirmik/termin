"""FBX instantiator - creates Entity hierarchy from FBX files."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np

from termin.geombase import Pose3
from termin.geombase import GeneralPose3
from termin.mesh.mesh import Mesh3
from termin.visualization.core.entity import Entity
from termin.visualization.core.mesh_handle import MeshHandle
from termin.visualization.render.components.mesh_renderer import MeshRenderer
from termin.visualization.render.materials.default_material import DefaultMaterial

try:
    from termin.loaders.fbx_loader import (
        load_fbx_file,
        FBXSceneData,
        FBXNodeData,
        FBXMeshData,
    )
    FBX_AVAILABLE = True
except ImportError:
    FBX_AVAILABLE = False


def _matrix_to_pose(matrix: np.ndarray) -> Pose3:
    """Convert 4x4 transformation matrix to Pose3."""
    from scipy.spatial.transform import Rotation

    translation = matrix[:3, 3].copy()
    rotation_matrix = matrix[:3, :3].copy()

    # Extract scale from rotation matrix
    scale_x = np.linalg.norm(rotation_matrix[:, 0])
    scale_y = np.linalg.norm(rotation_matrix[:, 1])
    scale_z = np.linalg.norm(rotation_matrix[:, 2])

    # Normalize to get pure rotation
    if scale_x > 1e-6:
        rotation_matrix[:, 0] /= scale_x
    if scale_y > 1e-6:
        rotation_matrix[:, 1] /= scale_y
    if scale_z > 1e-6:
        rotation_matrix[:, 2] /= scale_z

    # Convert rotation matrix to quaternion
    rot = Rotation.from_matrix(rotation_matrix)
    quat = rot.as_quat()  # [x, y, z, w]

    return Pose3(lin=translation, ang=quat)


def _extract_scale(matrix: np.ndarray) -> np.ndarray:
    """Extract scale from 4x4 transformation matrix."""
    scale_x = np.linalg.norm(matrix[:3, 0])
    scale_y = np.linalg.norm(matrix[:3, 1])
    scale_z = np.linalg.norm(matrix[:3, 2])
    return np.array([scale_x, scale_y, scale_z], dtype=np.float32)


def _fbx_mesh_to_mesh3(fbx_mesh: FBXMeshData) -> Mesh3:
    """Convert FBXMeshData to Mesh3."""
    vertices = fbx_mesh.vertices
    indices = fbx_mesh.indices.reshape(-1, 3)

    mesh = Mesh3(name=fbx_mesh.name, vertices=vertices, triangles=indices, uvs=fbx_mesh.uvs)

    if fbx_mesh.normals is not None:
        mesh.vertex_normals = fbx_mesh.normals
    else:
        mesh.compute_vertex_normals()

    return mesh


def _create_entity_from_node(
    node: FBXNodeData,
    meshes: List[FBXMeshData],
    mesh_handles: Dict[int, MeshHandle],
    default_material: DefaultMaterial,
) -> Entity:
    """Recursively create Entity hierarchy from FBXNodeData."""
    # Extract pose and scale from transform matrix
    pose = _matrix_to_pose(node.transform) if node.transform is not None else Pose3.identity()
    scale = _extract_scale(node.transform) if node.transform is not None else np.array([1.0, 1.0, 1.0])

    # Create GeneralPose3 with scale
    general_pose = GeneralPose3(lin=pose.lin, ang=pose.ang, scale=scale)
    entity = Entity(pose=general_pose, name=node.name)

    # Add MeshRenderer for each mesh attached to this node
    for mesh_idx in node.mesh_indices:
        if mesh_idx < len(meshes):
            # Get or create MeshHandle
            if mesh_idx not in mesh_handles:
                mesh3 = _fbx_mesh_to_mesh3(meshes[mesh_idx])
                mesh_handles[mesh_idx] = MeshHandle.from_mesh3(mesh3, name=meshes[mesh_idx].name)

            mesh_handle = mesh_handles[mesh_idx]
            renderer = MeshRenderer(mesh=mesh_handle, material=default_material)
            entity.add_component(renderer)

    # Recursively create children
    for child_node in node.children:
        child_entity = _create_entity_from_node(
            child_node, meshes, mesh_handles, default_material
        )
        entity.transform.add_child(child_entity.transform)

    return entity


def instantiate_fbx(path: Path, name: str = None) -> Entity:
    """
    Load FBX file and create Entity hierarchy.

    Args:
        path: Path to the FBX file.
        name: Optional name for the root entity. Defaults to filename without extension.

    Returns:
        Root Entity containing the FBX hierarchy with MeshRenderers.

    Raises:
        ImportError: If ufbx library is not installed.
    """
    if not FBX_AVAILABLE:
        raise ImportError(
            "FBX loading requires 'ufbx' library.\n"
            "Install with: pip install ufbx\n"
            "Note: ufbx requires Python 3.10-3.12 and C compiler for building."
        )

    scene_data = load_fbx_file(str(path))

    if name is None:
        name = path.stem

    # Shared material for all meshes
    default_material = DefaultMaterial(color=(0.8, 0.8, 0.8, 1.0))

    # Cache for MeshHandles (shared between nodes referencing same mesh)
    mesh_handles: Dict[int, MeshHandle] = {}

    if scene_data.root is not None:
        # Create hierarchy from FBX node tree
        root_entity = _create_entity_from_node(
            scene_data.root,
            scene_data.meshes,
            mesh_handles,
            default_material,
        )
        root_entity.name = name
    else:
        # No hierarchy - create flat structure
        root_entity = Entity(pose=Pose3.identity(), name=name)

        for i, fbx_mesh in enumerate(scene_data.meshes):
            mesh3 = _fbx_mesh_to_mesh3(fbx_mesh)
            mesh_handle = MeshHandle.from_mesh3(mesh3, name=fbx_mesh.name)
            mesh_handles[i] = mesh_handle

            mesh_entity = Entity(pose=Pose3.identity(), name=fbx_mesh.name)
            renderer = MeshRenderer(mesh=mesh_handle, material=default_material)
            mesh_entity.add_component(renderer)

            root_entity.transform.add_child(mesh_entity.transform)

    return root_entity
