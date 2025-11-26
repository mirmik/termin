<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/loaders/fbx_loader.py</title>
</head>
<body>
<pre><code>
# termin/mesh/loaders/fbx_loader.py

import numpy as np
import pyassimp


# ---------- DATA CLASSES ----------

class FBXMeshData:
    def __init__(self, name, vertices, normals, uvs, indices, material_index):
        self.name = name
        self.vertices = vertices
        self.normals = normals
        self.uvs = uvs
        self.indices = indices
        self.material_index = material_index


class FBXMaterialData:
    def __init__(self, name, diffuse_color=None, diffuse_texture=None):
        self.name = name
        self.diffuse_color = diffuse_color
        self.diffuse_texture = diffuse_texture


class FBXNodeData:
    def __init__(self, name, children=None, mesh_indices=None, transform=None):
        self.name = name
        self.children = children or []
        self.mesh_indices = mesh_indices or []
        self.transform = transform


class FBXAnimationChannel:
    def __init__(self, node_name, pos_keys, rot_keys, scale_keys):
        self.node_name = node_name
        self.pos_keys = pos_keys
        self.rot_keys = rot_keys
        self.scale_keys = scale_keys


class FBXAnimationClip:
    def __init__(self, name, duration, tps, channels):
        self.name = name
        self.duration = duration
        self.ticks_per_second = tps
        self.channels = channels


class FBXSceneData:
    def __init__(self):
        self.meshes = []
        self.materials = []
        self.root = None
        self.animations = []


# ---------- PARSER HELPERS ----------

def _parse_materials(scene, out):
    for mat in scene.materials:
        name = mat.properties.get(&quot;name&quot;, &quot;Material&quot;)
        diffuse = mat.properties.get(&quot;diffuse&quot;, None)

        tex = None
        for key, value in mat.properties.items():
            if isinstance(value, str) and value.lower().endswith((&quot;.jpg&quot;, &quot;.png&quot;, &quot;.jpeg&quot;, &quot;.tga&quot;)):
                tex = value

        out.materials.append(
            FBXMaterialData(
                name=name,
                diffuse_color=np.array(diffuse) if diffuse is not None else None,
                diffuse_texture=tex
            )
        )


def _parse_meshes(scene, out):
    for mesh in scene.meshes:
        verts = np.array(mesh.vertices, dtype=np.float32)
        norms = np.array(mesh.normals, dtype=np.float32) if mesh.normals is not None else None

        # ---- FIXED UV CHECK ----
        uvs = None
        if (
            mesh.texturecoords is not None
            and len(mesh.texturecoords) &gt; 0
            and mesh.texturecoords[0] is not None
        ):
            # Assimp дает UV как Nx3 массив (uv + padding), берём первые 2 колонки
            uvs = np.array(mesh.texturecoords[0][:, :2], dtype=np.float32)

        faces = []
        for f in mesh.faces:
            if len(f) == 3:
                faces.extend(f)

        indices = np.array(faces, dtype=np.uint32)

        out.meshes.append(
            FBXMeshData(
                name=mesh.name,
                vertices=verts,
                normals=norms,
                uvs=uvs,
                indices=indices,
                material_index=mesh.materialindex
            )
        )



def _parse_nodes(node):
    name = node.name
    m = node.transformation.astype(np.float32)
    children = [_parse_nodes(c) for c in node.children]
    mesh_indices = list(node.meshes or [])
    return FBXNodeData(name, children, mesh_indices, m)


def _parse_animations(scene, out):
    for anim in scene.animations:
        name = anim.name if anim.name else &quot;Anim&quot;
        tps = anim.tickspersecond if anim.tickspersecond &gt; 0 else 30.0

        channels = []
        for ch in anim.channels:
            pos_keys = [(k.time, np.array(k.value)) for k in (ch.positionkeys or [])]
            rot_keys = [(k.time, np.array(k.value)) for k in (ch.rotationkeys or [])]
            scale_keys = [(k.time, np.array(k.value)) for k in (ch.scalingkeys or [])]

            channels.append(
                FBXAnimationChannel(
                    node_name=ch.nodename,
                    pos_keys=pos_keys,
                    rot_keys=rot_keys,
                    scale_keys=scale_keys
                )
            )

        out.animations.append(
            FBXAnimationClip(
                name=name,
                duration=anim.duration,
                tps=tps,
                channels=channels
            )
        )


# ---------- PUBLIC API ----------

def load_fbx_file(path):
    scene_data = FBXSceneData()

    with pyassimp.load(path) as scene:
        if not scene:
            raise RuntimeError(f&quot;Failed to load FBX: {path}&quot;)

        _parse_materials(scene, scene_data)
        _parse_meshes(scene, scene_data)
        scene_data.root = _parse_nodes(scene.rootnode)
        _parse_animations(scene, scene_data)

        return scene_data

</code></pre>
</body>
</html>
