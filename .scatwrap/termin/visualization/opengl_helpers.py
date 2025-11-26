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
    &quot;&quot;&quot;Initializes OpenGL state.&quot;&quot;&quot;<br>
    global _OPENGL_INITED<br>
    if _OPENGL_INITED:<br>
        return<br>
<br>
    gl.glEnable(gl.GL_DEPTH_TEST)<br>
    gl.glEnable(gl.GL_CULL_FACE)<br>
    gl.glCullFace(gl.GL_BACK)<br>
    gl.glFrontFace(gl.GL_CCW)<br>
    _OPENGL_INITED = True<br>
<br>
def opengl_is_inited() -&gt; bool:<br>
    &quot;&quot;&quot;Checks if OpenGL has been initialized.&quot;&quot;&quot;<br>
    return _OPENGL_INITED<br>
<!-- END SCAT CODE -->
</body>
</html>
