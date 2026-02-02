<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/loader/load_fbx.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import&nbsp;termin.loaders.fbx_loader&nbsp;as&nbsp;fbx_loader<br>
from&nbsp;termin.mesh.mesh&nbsp;import&nbsp;mesh3_from_assimp,&nbsp;show_mesh<br>
from&nbsp;termin.visualization.animation.clip&nbsp;import&nbsp;AnimationClip<br>
<br>
data&nbsp;=&nbsp;fbx_loader.load_fbx_file(&quot;examples/data/FBX/animcube.fbx&quot;)<br>
<br>
print(&quot;Loaded&nbsp;FBX&nbsp;file:&quot;)<br>
print(f&quot;Number&nbsp;of&nbsp;meshes:&nbsp;{len(data.meshes)}&quot;)<br>
print(f&quot;Number&nbsp;of&nbsp;materials:&nbsp;{len(data.materials)}&quot;)<br>
print(f&quot;Number&nbsp;of&nbsp;animations:&nbsp;{len(data.animations)}&quot;)<br>
<br>
for&nbsp;i,&nbsp;mesh&nbsp;in&nbsp;enumerate(data.meshes):<br>
&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;&nbsp;Mesh&nbsp;{i}:&nbsp;{mesh.name},&nbsp;vertices:&nbsp;{len(mesh.vertices)},&nbsp;indices:&nbsp;{len(mesh.indices)},&nbsp;material&nbsp;index:&nbsp;{mesh.material_index}&quot;)<br>
<br>
for&nbsp;i,&nbsp;anim&nbsp;in&nbsp;enumerate(data.animations):<br>
&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;&nbsp;Animation&nbsp;{i}:&nbsp;{anim.name},&nbsp;duration:&nbsp;{anim.duration}&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;ch&nbsp;in&nbsp;anim.channels:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;&nbsp;&nbsp;Channel&nbsp;for&nbsp;node:&nbsp;{ch.node_name},&nbsp;pos&nbsp;keys:&nbsp;{len(ch.pos_keys)},&nbsp;rot&nbsp;keys:&nbsp;{len(ch.rot_keys)},&nbsp;scale&nbsp;keys:&nbsp;{len(ch.scale_keys)}&quot;)<br>
<br>
<br>
m&nbsp;=&nbsp;mesh3_from_assimp(data.meshes[0])<br>
print(f&quot;Converted&nbsp;first&nbsp;mesh&nbsp;to&nbsp;Mesh&nbsp;object:&nbsp;vertices={len(m.vertices)},&nbsp;indices={len(m.triangles)}&quot;)<br>
<br>
for&nbsp;raw_clip&nbsp;in&nbsp;data.animations:<br>
&nbsp;&nbsp;&nbsp;&nbsp;conv&nbsp;=&nbsp;AnimationClip.from_assimp_clip(raw_clip)<br>
&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;Converted&nbsp;animation&nbsp;clip:&nbsp;{conv}&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;print(f&quot;Channels:&nbsp;{list(conv.channels.values())}&quot;)<br>
<br>
<br>
show_mesh(m)<br>
<!-- END SCAT CODE -->
</body>
</html>
