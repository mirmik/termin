<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/materials/pick_material.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# termin/visualization/materials/pick_material.py (или рядом)<br>
<br>
from termin.visualization.material import Material<br>
from termin.visualization.shader import ShaderProgram<br>
<br>
vert_shader = &quot;&quot;&quot;<br>
#version 330 core<br>
<br>
layout(location=0) in vec3 a_position;<br>
layout(location=1) in vec3 a_normal;<br>
layout(location=2) in vec2 a_texcoord;<br>
<br>
uniform mat4 u_model;<br>
uniform mat4 u_view;<br>
uniform mat4 u_projection;<br>
void main() {<br>
&#9;gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
frag_shader = &quot;&quot;&quot;<br>
#version 330 core<br>
uniform vec3 u_pickColor;<br>
out vec4 fragColor;<br>
void main() {<br>
&#9;fragColor = vec4(u_pickColor, 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
class PickMaterial(Material):<br>
&#9;def __init__(self):<br>
&#9;&#9;shader = ShaderProgram(vert_shader, frag_shader)<br>
&#9;&#9;super().__init__(shader=shader)<br>
<br>
&#9;def apply_for_pick(self, model, view, proj, pick_color, graphics, context_key):<br>
&#9;&#9;self.shader.ensure_ready(graphics)<br>
&#9;&#9;self.apply(model, view, proj, graphics=graphics, context_key=context_key)<br>
&#9;&#9;self.shader.set_uniform_vec3(&quot;u_pickColor&quot;, pick_color)<br>
<!-- END SCAT CODE -->
</body>
</html>
