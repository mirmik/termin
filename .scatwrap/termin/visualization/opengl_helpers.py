<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/opengl_helpers.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
<br>
from&nbsp;OpenGL&nbsp;import&nbsp;GL&nbsp;as&nbsp;gl<br>
<br>
_OPENGL_INITED&nbsp;=&nbsp;False<br>
<br>
def&nbsp;init_opengl():<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Initializes&nbsp;OpenGL&nbsp;state.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;global&nbsp;_OPENGL_INITED<br>
&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;_OPENGL_INITED:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;gl.glEnable(gl.GL_DEPTH_TEST)<br>
&nbsp;&nbsp;&nbsp;&nbsp;gl.glEnable(gl.GL_CULL_FACE)<br>
&nbsp;&nbsp;&nbsp;&nbsp;gl.glCullFace(gl.GL_BACK)<br>
&nbsp;&nbsp;&nbsp;&nbsp;gl.glFrontFace(gl.GL_CCW)<br>
&nbsp;&nbsp;&nbsp;&nbsp;_OPENGL_INITED&nbsp;=&nbsp;True<br>
<br>
def&nbsp;opengl_is_inited()&nbsp;-&gt;&nbsp;bool:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Checks&nbsp;if&nbsp;OpenGL&nbsp;has&nbsp;been&nbsp;initialized.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;_OPENGL_INITED<br>
<!-- END SCAT CODE -->
</body>
</html>
