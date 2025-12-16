# termin/loaders/glb_instantiator.py
"""GLB instantiator - creates Entity hierarchy from GLB files."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np

from termin.geombase.pose3 import Pose3
from termin.mesh.mesh import Mesh3
from termin.visualization.core.entity import Entity
from termin.visualization.core.mesh import MeshDrawable
from termin.visualization.render.components.mesh_renderer import MeshRenderer
from termin.visualization.render.materials.default_material import DefaultMaterial

from termin.loaders.glb_loader import (
    load_glb_file,
    GLBSceneData,
    GLBNodeData,
    GLBMeshData,
)


def _glb_mesh_to_mesh3(glb_mesh: GLBMeshData) -> Mesh3:
    """Convert GLBMeshData to Mesh3."""
    vertices = glb_mesh.vertices
    indices = glb_mesh.indices.reshape(-1, 3)

    mesh = Mesh3(vertices=vertices, triangles=indices, uvs=glb_mesh.uvs)

    if glb_mesh.normals is not None:
        mesh.vertex_normals = glb_mesh.normals
    else:
        mesh.compute_vertex_normals()

    return mesh


def _create_entity_from_node(
    node_index: int,
    scene_data: GLBSceneData,
    mesh_drawables: Dict[int, MeshDrawable],
    default_material: DefaultMaterial,
) -> Entity:
    """Recursively create Entity hierarchy from GLBNodeData."""
    node = scene_data.nodes[node_index]

    # Create pose from translation and rotation
    pose = Pose3(lin=node.translation, ang=node.rotation)
    scale = node.scale

    entity = Entity(pose=pose, name=node.name, scale=scale)

    # Add MeshRenderer if node has a mesh
    if node.mesh_index is not None and node.mesh_index < len(scene_data.meshes):
        mesh_idx = node.mesh_index

        # Get or create MeshDrawable
        if mesh_idx not in mesh_drawables:
            mesh3 = _glb_mesh_to_mesh3(scene_data.meshes[mesh_idx])
            mesh_drawables[mesh_idx] = MeshDrawable(mesh3, name=scene_data.meshes[mesh_idx].name)

        drawable = mesh_drawables[mesh_idx]
        renderer = MeshRenderer(mesh=drawable, material=default_material)
        entity.add_component(renderer)

    # Recursively create children
    for child_index in node.children:
        child_entity = _create_entity_from_node(
            child_index, scene_data, mesh_drawables, default_material
        )
        entity.transform.add_child(child_entity.transform)

    return entity


def instantiate_glb(path: Path, name: str = None) -> Entity:
    """
    Load GLB file and create Entity hierarchy.

    Args:
        path: Path to the GLB file.
        name: Optional name for the root entity. Defaults to filename without extension.

    Returns:
        Root Entity containing the GLB hierarchy with MeshRenderers.
    """
    scene_data = load_glb_file(str(path))

    if name is None:
        name = path.stem

    # Shared material for all meshes
    default_material = DefaultMaterial(color=(0.8, 0.8, 0.8, 1.0))

    # Cache for MeshDrawables (shared between nodes referencing same mesh)
    mesh_drawables: Dict[int, MeshDrawable] = {}

    if scene_data.root_nodes:
        if len(scene_data.root_nodes) == 1:
            # Single root - use it directly
            root_entity = _create_entity_from_node(
                scene_data.root_nodes[0],
                scene_data,
                mesh_drawables,
                default_material,
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
                )
                root_entity.transform.add_child(child_entity.transform)
    else:
        # No hierarchy - create flat structure from meshes
        root_entity = Entity(pose=Pose3.identity(), name=name)

        for i, glb_mesh in enumerate(scene_data.meshes):
            mesh3 = _glb_mesh_to_mesh3(glb_mesh)
            drawable = MeshDrawable(mesh3, name=glb_mesh.name)
            mesh_drawables[i] = drawable

            mesh_entity = Entity(pose=Pose3.identity(), name=glb_mesh.name)
            renderer = MeshRenderer(mesh=drawable, material=default_material)
            mesh_entity.add_component(renderer)

            root_entity.transform.add_child(mesh_entity.transform)

    return root_entity
