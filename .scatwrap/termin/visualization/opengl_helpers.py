<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/opengl_helpers.py</title>
</head>
<body>
<pre><code>


from OpenGL import GL as gl

_OPENGL_INITED = False

def init_opengl():
    &quot;&quot;&quot;Initializes OpenGL state.&quot;&quot;&quot;
    global _OPENGL_INITED
    if _OPENGL_INITED:
        return

    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_CULL_FACE)
    gl.glCullFace(gl.GL_BACK)
    gl.glFrontFace(gl.GL_CCW)
    _OPENGL_INITED = True

def opengl_is_inited() -&gt; bool:
    &quot;&quot;&quot;Checks if OpenGL has been initialized.&quot;&quot;&quot;
    return _OPENGL_INITED
</code></pre>
</body>
</html>
