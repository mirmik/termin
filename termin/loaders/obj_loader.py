# termin/loaders/obj_loader.py

import numpy as np
import pyassimp


class OBJMeshData:
    def __init__(self, name, vertices, normals, uvs, indices):
        self.name = name
        self.vertices = vertices  # np.ndarray (N, 3) float32
        self.normals = normals    # np.ndarray (N, 3) float32 or None
        self.uvs = uvs            # np.ndarray (N, 2) float32 or None
        self.indices = indices    # np.ndarray (M,) uint32


class OBJSceneData:
    def __init__(self):
        self.meshes = []


def load_obj_file(path) -> OBJSceneData:
    """Load OBJ file using pyassimp."""
    scene_data = OBJSceneData()

    with pyassimp.load(path) as scene:
        if not scene:
            raise RuntimeError(f"Failed to load OBJ: {path}")

        for mesh in scene.meshes:
            verts = np.array(mesh.vertices, dtype=np.float32)
            norms = np.array(mesh.normals, dtype=np.float32) if mesh.normals is not None else None

            uvs = None
            if (
                mesh.texturecoords is not None
                and len(mesh.texturecoords) > 0
                and mesh.texturecoords[0] is not None
            ):
                uvs = np.array(mesh.texturecoords[0][:, :2], dtype=np.float32)

            faces = []
            for f in mesh.faces:
                if len(f) == 3:
                    faces.extend(f)

            indices = np.array(faces, dtype=np.uint32)

            scene_data.meshes.append(
                OBJMeshData(
                    name=mesh.name or "mesh",
                    vertices=verts,
                    normals=norms,
                    uvs=uvs,
                    indices=indices,
                )
            )

    return scene_data
