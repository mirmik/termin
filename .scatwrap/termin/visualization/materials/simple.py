<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/materials/simple.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
from&nbsp;termin.visualization.material&nbsp;import&nbsp;Material<br>
from&nbsp;termin.visualization.shader&nbsp;import&nbsp;ShaderProgram<br>
<br>
ColorMaterial_VERT&nbsp;=&nbsp;&quot;&quot;&quot;<br>
#version&nbsp;330&nbsp;core<br>
layout(location&nbsp;=&nbsp;0)&nbsp;in&nbsp;vec3&nbsp;a_position;<br>
layout(location&nbsp;=&nbsp;1)&nbsp;in&nbsp;vec3&nbsp;a_normal;<br>
<br>
uniform&nbsp;mat4&nbsp;u_model;<br>
uniform&nbsp;mat4&nbsp;u_view;<br>
uniform&nbsp;mat4&nbsp;u_projection;<br>
<br>
out&nbsp;vec3&nbsp;v_normal;<br>
<br>
void&nbsp;main()&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;v_normal&nbsp;=&nbsp;mat3(transpose(inverse(u_model)))&nbsp;*&nbsp;a_normal;<br>
&nbsp;&nbsp;&nbsp;&nbsp;gl_Position&nbsp;=&nbsp;u_projection&nbsp;*&nbsp;u_view&nbsp;*&nbsp;u_model&nbsp;*&nbsp;vec4(a_position,&nbsp;1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
ColorMaterial_FRAG&nbsp;=&nbsp;&quot;&quot;&quot;<br>
#version&nbsp;330&nbsp;core<br>
in&nbsp;vec3&nbsp;v_normal;<br>
uniform&nbsp;vec4&nbsp;u_color;<br>
<br>
out&nbsp;vec4&nbsp;FragColor;<br>
<br>
void&nbsp;main()&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;vec3&nbsp;n&nbsp;=&nbsp;normalize(v_normal);<br>
&nbsp;&nbsp;&nbsp;&nbsp;float&nbsp;ndotl&nbsp;=&nbsp;max(dot(n,&nbsp;vec3(0.2,&nbsp;0.6,&nbsp;0.5)),&nbsp;0.0);<br>
&nbsp;&nbsp;&nbsp;&nbsp;vec3&nbsp;color&nbsp;=&nbsp;u_color.rgb&nbsp;*&nbsp;(0.25&nbsp;+&nbsp;0.75&nbsp;*&nbsp;ndotl);<br>
&nbsp;&nbsp;&nbsp;&nbsp;FragColor&nbsp;=&nbsp;vec4(color,&nbsp;u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
class&nbsp;ColorMaterial(Material):<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;color:&nbsp;tuple[float,&nbsp;float,&nbsp;float,&nbsp;float]):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.color&nbsp;=&nbsp;color<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.shader&nbsp;=&nbsp;ShaderProgram(ColorMaterial_VERT,&nbsp;ColorMaterial_FRAG)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__(shader=self.shader,&nbsp;color=color)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
<!-- END SCAT CODE -->
</body>
</html>
