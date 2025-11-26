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
from OpenGL import GL as gl<br>
<br>
_OPENGL_INITED = False<br>
<br>
def init_opengl():<br>
&#9;&quot;&quot;&quot;Initializes OpenGL state.&quot;&quot;&quot;<br>
&#9;global _OPENGL_INITED<br>
&#9;if _OPENGL_INITED:<br>
&#9;&#9;return<br>
<br>
&#9;gl.glEnable(gl.GL_DEPTH_TEST)<br>
&#9;gl.glEnable(gl.GL_CULL_FACE)<br>
&#9;gl.glCullFace(gl.GL_BACK)<br>
&#9;gl.glFrontFace(gl.GL_CCW)<br>
&#9;_OPENGL_INITED = True<br>
<br>
def opengl_is_inited() -&gt; bool:<br>
&#9;&quot;&quot;&quot;Checks if OpenGL has been initialized.&quot;&quot;&quot;<br>
&#9;return _OPENGL_INITED<br>
<!-- END SCAT CODE -->
</body>
</html>
