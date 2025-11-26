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
&#9;def __init__(self, name, vertices, normals, uvs, indices, material_index):<br>
&#9;&#9;self.name = name<br>
&#9;&#9;self.vertices = vertices<br>
&#9;&#9;self.normals = normals<br>
&#9;&#9;self.uvs = uvs<br>
&#9;&#9;self.indices = indices<br>
&#9;&#9;self.material_index = material_index<br>
<br>
<br>
class FBXMaterialData:<br>
&#9;def __init__(self, name, diffuse_color=None, diffuse_texture=None):<br>
&#9;&#9;self.name = name<br>
&#9;&#9;self.diffuse_color = diffuse_color<br>
&#9;&#9;self.diffuse_texture = diffuse_texture<br>
<br>
<br>
class FBXNodeData:<br>
&#9;def __init__(self, name, children=None, mesh_indices=None, transform=None):<br>
&#9;&#9;self.name = name<br>
&#9;&#9;self.children = children or []<br>
&#9;&#9;self.mesh_indices = mesh_indices or []<br>
&#9;&#9;self.transform = transform<br>
<br>
<br>
class FBXAnimationChannel:<br>
&#9;def __init__(self, node_name, pos_keys, rot_keys, scale_keys):<br>
&#9;&#9;self.node_name = node_name<br>
&#9;&#9;self.pos_keys = pos_keys<br>
&#9;&#9;self.rot_keys = rot_keys<br>
&#9;&#9;self.scale_keys = scale_keys<br>
<br>
<br>
class FBXAnimationClip:<br>
&#9;def __init__(self, name, duration, tps, channels):<br>
&#9;&#9;self.name = name<br>
&#9;&#9;self.duration = duration<br>
&#9;&#9;self.ticks_per_second = tps<br>
&#9;&#9;self.channels = channels<br>
<br>
<br>
class FBXSceneData:<br>
&#9;def __init__(self):<br>
&#9;&#9;self.meshes = []<br>
&#9;&#9;self.materials = []<br>
&#9;&#9;self.root = None<br>
&#9;&#9;self.animations = []<br>
<br>
<br>
# ---------- PARSER HELPERS ----------<br>
<br>
def _parse_materials(scene, out):<br>
&#9;for mat in scene.materials:<br>
&#9;&#9;name = mat.properties.get(&quot;name&quot;, &quot;Material&quot;)<br>
&#9;&#9;diffuse = mat.properties.get(&quot;diffuse&quot;, None)<br>
<br>
&#9;&#9;tex = None<br>
&#9;&#9;for key, value in mat.properties.items():<br>
&#9;&#9;&#9;if isinstance(value, str) and value.lower().endswith((&quot;.jpg&quot;, &quot;.png&quot;, &quot;.jpeg&quot;, &quot;.tga&quot;)):<br>
&#9;&#9;&#9;&#9;tex = value<br>
<br>
&#9;&#9;out.materials.append(<br>
&#9;&#9;&#9;FBXMaterialData(<br>
&#9;&#9;&#9;&#9;name=name,<br>
&#9;&#9;&#9;&#9;diffuse_color=np.array(diffuse) if diffuse is not None else None,<br>
&#9;&#9;&#9;&#9;diffuse_texture=tex<br>
&#9;&#9;&#9;)<br>
&#9;&#9;)<br>
<br>
<br>
def _parse_meshes(scene, out):<br>
&#9;for mesh in scene.meshes:<br>
&#9;&#9;verts = np.array(mesh.vertices, dtype=np.float32)<br>
&#9;&#9;norms = np.array(mesh.normals, dtype=np.float32) if mesh.normals is not None else None<br>
<br>
&#9;&#9;# ---- FIXED UV CHECK ----<br>
&#9;&#9;uvs = None<br>
&#9;&#9;if (<br>
&#9;&#9;&#9;mesh.texturecoords is not None<br>
&#9;&#9;&#9;and len(mesh.texturecoords) &gt; 0<br>
&#9;&#9;&#9;and mesh.texturecoords[0] is not None<br>
&#9;&#9;):<br>
&#9;&#9;&#9;# Assimp дает UV как Nx3 массив (uv + padding), берём первые 2 колонки<br>
&#9;&#9;&#9;uvs = np.array(mesh.texturecoords[0][:, :2], dtype=np.float32)<br>
<br>
&#9;&#9;faces = []<br>
&#9;&#9;for f in mesh.faces:<br>
&#9;&#9;&#9;if len(f) == 3:<br>
&#9;&#9;&#9;&#9;faces.extend(f)<br>
<br>
&#9;&#9;indices = np.array(faces, dtype=np.uint32)<br>
<br>
&#9;&#9;out.meshes.append(<br>
&#9;&#9;&#9;FBXMeshData(<br>
&#9;&#9;&#9;&#9;name=mesh.name,<br>
&#9;&#9;&#9;&#9;vertices=verts,<br>
&#9;&#9;&#9;&#9;normals=norms,<br>
&#9;&#9;&#9;&#9;uvs=uvs,<br>
&#9;&#9;&#9;&#9;indices=indices,<br>
&#9;&#9;&#9;&#9;material_index=mesh.materialindex<br>
&#9;&#9;&#9;)<br>
&#9;&#9;)<br>
<br>
<br>
<br>
def _parse_nodes(node):<br>
&#9;name = node.name<br>
&#9;m = node.transformation.astype(np.float32)<br>
&#9;children = [_parse_nodes(c) for c in node.children]<br>
&#9;mesh_indices = list(node.meshes or [])<br>
&#9;return FBXNodeData(name, children, mesh_indices, m)<br>
<br>
<br>
def _parse_animations(scene, out):<br>
&#9;for anim in scene.animations:<br>
&#9;&#9;name = anim.name if anim.name else &quot;Anim&quot;<br>
&#9;&#9;tps = anim.tickspersecond if anim.tickspersecond &gt; 0 else 30.0<br>
<br>
&#9;&#9;channels = []<br>
&#9;&#9;for ch in anim.channels:<br>
&#9;&#9;&#9;pos_keys = [(k.time, np.array(k.value)) for k in (ch.positionkeys or [])]<br>
&#9;&#9;&#9;rot_keys = [(k.time, np.array(k.value)) for k in (ch.rotationkeys or [])]<br>
&#9;&#9;&#9;scale_keys = [(k.time, np.array(k.value)) for k in (ch.scalingkeys or [])]<br>
<br>
&#9;&#9;&#9;channels.append(<br>
&#9;&#9;&#9;&#9;FBXAnimationChannel(<br>
&#9;&#9;&#9;&#9;&#9;node_name=ch.nodename,<br>
&#9;&#9;&#9;&#9;&#9;pos_keys=pos_keys,<br>
&#9;&#9;&#9;&#9;&#9;rot_keys=rot_keys,<br>
&#9;&#9;&#9;&#9;&#9;scale_keys=scale_keys<br>
&#9;&#9;&#9;&#9;)<br>
&#9;&#9;&#9;)<br>
<br>
&#9;&#9;out.animations.append(<br>
&#9;&#9;&#9;FBXAnimationClip(<br>
&#9;&#9;&#9;&#9;name=name,<br>
&#9;&#9;&#9;&#9;duration=anim.duration,<br>
&#9;&#9;&#9;&#9;tps=tps,<br>
&#9;&#9;&#9;&#9;channels=channels<br>
&#9;&#9;&#9;)<br>
&#9;&#9;)<br>
<br>
<br>
# ---------- PUBLIC API ----------<br>
<br>
def load_fbx_file(path):<br>
&#9;scene_data = FBXSceneData()<br>
<br>
&#9;with pyassimp.load(path) as scene:<br>
&#9;&#9;if not scene:<br>
&#9;&#9;&#9;raise RuntimeError(f&quot;Failed to load FBX: {path}&quot;)<br>
<br>
&#9;&#9;_parse_materials(scene, scene_data)<br>
&#9;&#9;_parse_meshes(scene, scene_data)<br>
&#9;&#9;scene_data.root = _parse_nodes(scene.rootnode)<br>
&#9;&#9;_parse_animations(scene, scene_data)<br>
<br>
&#9;&#9;return scene_data<br>
<!-- END SCAT CODE -->
</body>
</html>
