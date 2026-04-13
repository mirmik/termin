

from OpenGL import GL as gl

_OPENGL_INITED = False

def init_opengl():
    """Initializes OpenGL state."""
    global _OPENGL_INITED
    if _OPENGL_INITED:
        return

    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_CULL_FACE)
    gl.glCullFace(gl.GL_BACK)
    gl.glFrontFace(gl.GL_CCW)
    _OPENGL_INITED = True

def opengl_is_inited() -> bool:
    """Checks if OpenGL has been initialized."""
    return _OPENGL_INITED