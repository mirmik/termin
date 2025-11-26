<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/materials/simple.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from __future__ import annotations<br>
from termin.visualization.material import Material<br>
from termin.visualization.shader import ShaderProgram<br>
<br>
ColorMaterial_VERT = &quot;&quot;&quot;<br>
#version 330 core<br>
layout(location = 0) in vec3 a_position;<br>
layout(location = 1) in vec3 a_normal;<br>
<br>
uniform mat4 u_model;<br>
uniform mat4 u_view;<br>
uniform mat4 u_projection;<br>
<br>
out vec3 v_normal;<br>
<br>
void main() {<br>
&#9;v_normal = mat3(transpose(inverse(u_model))) * a_normal;<br>
&#9;gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
ColorMaterial_FRAG = &quot;&quot;&quot;<br>
#version 330 core<br>
in vec3 v_normal;<br>
uniform vec4 u_color;<br>
<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
&#9;vec3 n = normalize(v_normal);<br>
&#9;float ndotl = max(dot(n, vec3(0.2, 0.6, 0.5)), 0.0);<br>
&#9;vec3 color = u_color.rgb * (0.25 + 0.75 * ndotl);<br>
&#9;FragColor = vec4(color, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
class ColorMaterial(Material):<br>
&#9;def __init__(self, color: tuple[float, float, float, float]):<br>
&#9;&#9;self.color = color<br>
&#9;&#9;self.shader = ShaderProgram(ColorMaterial_VERT, ColorMaterial_FRAG)<br>
&#9;&#9;super().__init__(shader=self.shader, color=color)<br>
<br>
&#9;<br>
<!-- END SCAT CODE -->
</body>
</html>
