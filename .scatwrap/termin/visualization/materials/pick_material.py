<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/materials/pick_material.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#&nbsp;termin/visualization/materials/pick_material.py&nbsp;(или&nbsp;рядом)<br>
<br>
from&nbsp;termin.visualization.material&nbsp;import&nbsp;Material<br>
from&nbsp;termin.visualization.shader&nbsp;import&nbsp;ShaderProgram<br>
<br>
vert_shader&nbsp;=&nbsp;&quot;&quot;&quot;<br>
#version&nbsp;330&nbsp;core<br>
<br>
layout(location=0)&nbsp;in&nbsp;vec3&nbsp;a_position;<br>
layout(location=1)&nbsp;in&nbsp;vec3&nbsp;a_normal;<br>
layout(location=2)&nbsp;in&nbsp;vec2&nbsp;a_texcoord;<br>
<br>
uniform&nbsp;mat4&nbsp;u_model;<br>
uniform&nbsp;mat4&nbsp;u_view;<br>
uniform&nbsp;mat4&nbsp;u_projection;<br>
void&nbsp;main()&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;gl_Position&nbsp;=&nbsp;u_projection&nbsp;*&nbsp;u_view&nbsp;*&nbsp;u_model&nbsp;*&nbsp;vec4(a_position,&nbsp;1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
frag_shader&nbsp;=&nbsp;&quot;&quot;&quot;<br>
#version&nbsp;330&nbsp;core<br>
uniform&nbsp;vec3&nbsp;u_pickColor;<br>
out&nbsp;vec4&nbsp;fragColor;<br>
void&nbsp;main()&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;fragColor&nbsp;=&nbsp;vec4(u_pickColor,&nbsp;1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
class&nbsp;PickMaterial(Material):<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;shader&nbsp;=&nbsp;ShaderProgram(vert_shader,&nbsp;frag_shader)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__(shader=shader)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;apply_for_pick(self,&nbsp;model,&nbsp;view,&nbsp;proj,&nbsp;pick_color,&nbsp;graphics,&nbsp;context_key):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.shader.ensure_ready(graphics)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.apply(model,&nbsp;view,&nbsp;proj,&nbsp;graphics=graphics,&nbsp;context_key=context_key)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.shader.set_uniform_vec3(&quot;u_pickColor&quot;,&nbsp;pick_color)<br>
<!-- END SCAT CODE -->
</body>
</html>
