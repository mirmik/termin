<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/project/NewShader.shader</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
@program&nbsp;NewShader<br>
<br>
@phase&nbsp;opaque<br>
<br>
@property&nbsp;Float&nbsp;u_time&nbsp;=&nbsp;0.0<br>
@property&nbsp;Color&nbsp;u_color&nbsp;=&nbsp;Color(1.0,&nbsp;1.0,&nbsp;1.0,&nbsp;1.0)<br>
<br>
@stage&nbsp;vertex<br>
#version&nbsp;330&nbsp;core<br>
<br>
layout(location&nbsp;=&nbsp;0)&nbsp;in&nbsp;vec3&nbsp;a_position;<br>
layout(location&nbsp;=&nbsp;1)&nbsp;in&nbsp;vec3&nbsp;a_normal;<br>
layout(location&nbsp;=&nbsp;2)&nbsp;in&nbsp;vec2&nbsp;a_texcoord;<br>
<br>
uniform&nbsp;mat4&nbsp;u_model;<br>
uniform&nbsp;mat4&nbsp;u_view;<br>
uniform&nbsp;mat4&nbsp;u_projection;<br>
<br>
out&nbsp;vec3&nbsp;v_normal;<br>
out&nbsp;vec2&nbsp;v_texcoord;<br>
<br>
void&nbsp;main()&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;v_normal&nbsp;=&nbsp;mat3(u_model)&nbsp;*&nbsp;a_normal;<br>
&nbsp;&nbsp;&nbsp;&nbsp;v_texcoord&nbsp;=&nbsp;a_texcoord;<br>
&nbsp;&nbsp;&nbsp;&nbsp;gl_Position&nbsp;=&nbsp;u_projection&nbsp;*&nbsp;u_view&nbsp;*&nbsp;u_model&nbsp;*&nbsp;vec4(a_position,&nbsp;1.0);<br>
}<br>
<br>
@stage&nbsp;fragment<br>
#version&nbsp;330&nbsp;core<br>
<br>
in&nbsp;vec3&nbsp;v_normal;<br>
in&nbsp;vec2&nbsp;v_texcoord;<br>
<br>
uniform&nbsp;vec4&nbsp;u_color;<br>
<br>
out&nbsp;vec4&nbsp;frag_color;<br>
<br>
void&nbsp;main()&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;vec3&nbsp;normal&nbsp;=&nbsp;normalize(v_normal);<br>
&nbsp;&nbsp;&nbsp;&nbsp;float&nbsp;light&nbsp;=&nbsp;max(dot(normal,&nbsp;vec3(0.0,&nbsp;1.0,&nbsp;0.0)),&nbsp;0.2);<br>
&nbsp;&nbsp;&nbsp;&nbsp;frag_color&nbsp;=&nbsp;vec4(u_color.rgb&nbsp;*&nbsp;light,&nbsp;u_color.a);<br>
}<br>
<!-- END SCAT CODE -->
</body>
</html>
