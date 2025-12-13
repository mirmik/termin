# termin/loaders/stl_loader.py

import numpy as np
import pyassimp


class STLMeshData:
    def __init__(self, name, vertices, normals, indices):
        self.name = name
        self.vertices = vertices  # np.ndarray (N, 3) float32
        self.normals = normals    # np.ndarray (N, 3) float32 or None
        self.indices = indices    # np.ndarray (M,) uint32


class STLSceneData:
    def __init__(self):
        self.meshes = []


def load_stl_file(path) -> STLSceneData:
    """Load STL file using pyassimp."""
    scene_data = STLSceneData()

    with pyassimp.load(path) as scene:
        if not scene:
            raise RuntimeError(f"Failed to load STL: {path}")

        for mesh in scene.meshes:
            verts = np.array(mesh.vertices, dtype=np.float32)
            norms = np.array(mesh.normals, dtype=np.float32) if mesh.normals is not None else None

            faces = []
            for f in mesh.faces:
                if len(f) == 3:
                    faces.extend(f)

            indices = np.array(faces, dtype=np.uint32)

            scene_data.meshes.append(
                STLMeshData(
                    name=mesh.name or "mesh",
                    vertices=verts,
                    normals=norms,
                    indices=indices,
                )
            )

    return scene_data
