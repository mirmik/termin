<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/project/Shaders/TransparentShader.shader</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
@program&nbsp;TransparentShader<br>
<br>
&nbsp;&nbsp;@phase&nbsp;transparent<br>
<br>
&nbsp;&nbsp;@glBlend&nbsp;true<br>
&nbsp;&nbsp;@glDepthMask&nbsp;false<br>
&nbsp;&nbsp;@glDepthTest&nbsp;true<br>
&nbsp;&nbsp;@glCull&nbsp;false<br>
<br>
&nbsp;&nbsp;@property&nbsp;Color&nbsp;u_color&nbsp;=&nbsp;Color(1.0,&nbsp;1.0,&nbsp;1.0,&nbsp;0.5)<br>
<br>
&nbsp;&nbsp;@stage&nbsp;vertex<br>
&nbsp;&nbsp;#version&nbsp;330&nbsp;core<br>
<br>
&nbsp;&nbsp;layout(location&nbsp;=&nbsp;0)&nbsp;in&nbsp;vec3&nbsp;a_position;<br>
&nbsp;&nbsp;layout(location&nbsp;=&nbsp;1)&nbsp;in&nbsp;vec3&nbsp;a_normal;<br>
<br>
&nbsp;&nbsp;uniform&nbsp;mat4&nbsp;u_model;<br>
&nbsp;&nbsp;uniform&nbsp;mat4&nbsp;u_view;<br>
&nbsp;&nbsp;uniform&nbsp;mat4&nbsp;u_projection;<br>
<br>
&nbsp;&nbsp;void&nbsp;main()&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gl_Position&nbsp;=&nbsp;u_projection&nbsp;*&nbsp;u_view&nbsp;*&nbsp;u_model&nbsp;*&nbsp;vec4(a_position,&nbsp;1.0);<br>
&nbsp;&nbsp;}<br>
<br>
&nbsp;&nbsp;@stage&nbsp;fragment<br>
&nbsp;&nbsp;#version&nbsp;330&nbsp;core<br>
<br>
&nbsp;&nbsp;uniform&nbsp;vec4&nbsp;u_color;<br>
<br>
&nbsp;&nbsp;out&nbsp;vec4&nbsp;frag_color;<br>
<br>
&nbsp;&nbsp;void&nbsp;main()&nbsp;{<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;frag_color&nbsp;=&nbsp;u_color;<br>
&nbsp;&nbsp;}<br>
&nbsp;&nbsp;<br>
<!-- END SCAT CODE -->
</body>
</html>
