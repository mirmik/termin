<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/loaders/fbx_loader.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# termin/mesh/loaders/fbx_loader.py<br>
<br>
import numpy as np<br>
import pyassimp<br>
<br>
<br>
# ---------- DATA CLASSES ----------<br>
<br>
class FBXMeshData:<br>
    def __init__(self, name, vertices, normals, uvs, indices, material_index):<br>
        self.name = name<br>
        self.vertices = vertices<br>
        self.normals = normals<br>
        self.uvs = uvs<br>
        self.indices = indices<br>
        self.material_index = material_index<br>
<br>
<br>
class FBXMaterialData:<br>
    def __init__(self, name, diffuse_color=None, diffuse_texture=None):<br>
        self.name = name<br>
        self.diffuse_color = diffuse_color<br>
        self.diffuse_texture = diffuse_texture<br>
<br>
<br>
class FBXNodeData:<br>
    def __init__(self, name, children=None, mesh_indices=None, transform=None):<br>
        self.name = name<br>
        self.children = children or []<br>
        self.mesh_indices = mesh_indices or []<br>
        self.transform = transform<br>
<br>
<br>
class FBXAnimationChannel:<br>
    def __init__(self, node_name, pos_keys, rot_keys, scale_keys):<br>
        self.node_name = node_name<br>
        self.pos_keys = pos_keys<br>
        self.rot_keys = rot_keys<br>
        self.scale_keys = scale_keys<br>
<br>
<br>
class FBXAnimationClip:<br>
    def __init__(self, name, duration, tps, channels):<br>
        self.name = name<br>
        self.duration = duration<br>
        self.ticks_per_second = tps<br>
        self.channels = channels<br>
<br>
<br>
class FBXSceneData:<br>
    def __init__(self):<br>
        self.meshes = []<br>
        self.materials = []<br>
        self.root = None<br>
        self.animations = []<br>
<br>
<br>
# ---------- PARSER HELPERS ----------<br>
<br>
def _parse_materials(scene, out):<br>
    for mat in scene.materials:<br>
        name = mat.properties.get(&quot;name&quot;, &quot;Material&quot;)<br>
        diffuse = mat.properties.get(&quot;diffuse&quot;, None)<br>
<br>
        tex = None<br>
        for key, value in mat.properties.items():<br>
            if isinstance(value, str) and value.lower().endswith((&quot;.jpg&quot;, &quot;.png&quot;, &quot;.jpeg&quot;, &quot;.tga&quot;)):<br>
                tex = value<br>
<br>
        out.materials.append(<br>
            FBXMaterialData(<br>
                name=name,<br>
                diffuse_color=np.array(diffuse) if diffuse is not None else None,<br>
                diffuse_texture=tex<br>
            )<br>
        )<br>
<br>
<br>
def _parse_meshes(scene, out):<br>
    for mesh in scene.meshes:<br>
        verts = np.array(mesh.vertices, dtype=np.float32)<br>
        norms = np.array(mesh.normals, dtype=np.float32) if mesh.normals is not None else None<br>
<br>
        # ---- FIXED UV CHECK ----<br>
        uvs = None<br>
        if (<br>
            mesh.texturecoords is not None<br>
            and len(mesh.texturecoords) &gt; 0<br>
            and mesh.texturecoords[0] is not None<br>
        ):<br>
            # Assimp дает UV как Nx3 массив (uv + padding), берём первые 2 колонки<br>
            uvs = np.array(mesh.texturecoords[0][:, :2], dtype=np.float32)<br>
<br>
        faces = []<br>
        for f in mesh.faces:<br>
            if len(f) == 3:<br>
                faces.extend(f)<br>
<br>
        indices = np.array(faces, dtype=np.uint32)<br>
<br>
        out.meshes.append(<br>
            FBXMeshData(<br>
                name=mesh.name,<br>
                vertices=verts,<br>
                normals=norms,<br>
                uvs=uvs,<br>
                indices=indices,<br>
                material_index=mesh.materialindex<br>
            )<br>
        )<br>
<br>
<br>
<br>
def _parse_nodes(node):<br>
    name = node.name<br>
    m = node.transformation.astype(np.float32)<br>
    children = [_parse_nodes(c) for c in node.children]<br>
    mesh_indices = list(node.meshes or [])<br>
    return FBXNodeData(name, children, mesh_indices, m)<br>
<br>
<br>
def _parse_animations(scene, out):<br>
    for anim in scene.animations:<br>
        name = anim.name if anim.name else &quot;Anim&quot;<br>
        tps = anim.tickspersecond if anim.tickspersecond &gt; 0 else 30.0<br>
<br>
        channels = []<br>
        for ch in anim.channels:<br>
            pos_keys = [(k.time, np.array(k.value)) for k in (ch.positionkeys or [])]<br>
            rot_keys = [(k.time, np.array(k.value)) for k in (ch.rotationkeys or [])]<br>
            scale_keys = [(k.time, np.array(k.value)) for k in (ch.scalingkeys or [])]<br>
<br>
            channels.append(<br>
                FBXAnimationChannel(<br>
                    node_name=ch.nodename,<br>
                    pos_keys=pos_keys,<br>
                    rot_keys=rot_keys,<br>
                    scale_keys=scale_keys<br>
                )<br>
            )<br>
<br>
        out.animations.append(<br>
            FBXAnimationClip(<br>
                name=name,<br>
                duration=anim.duration,<br>
                tps=tps,<br>
                channels=channels<br>
            )<br>
        )<br>
<br>
<br>
# ---------- PUBLIC API ----------<br>
<br>
def load_fbx_file(path):<br>
    scene_data = FBXSceneData()<br>
<br>
    with pyassimp.load(path) as scene:<br>
        if not scene:<br>
            raise RuntimeError(f&quot;Failed to load FBX: {path}&quot;)<br>
<br>
        _parse_materials(scene, scene_data)<br>
        _parse_meshes(scene, scene_data)<br>
        scene_data.root = _parse_nodes(scene.rootnode)<br>
        _parse_animations(scene, scene_data)<br>
<br>
        return scene_data<br>
<!-- END SCAT CODE -->
</body>
</html>
