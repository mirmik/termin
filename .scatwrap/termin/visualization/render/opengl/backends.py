<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/render/opengl/backends.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;OpenGL-based&nbsp;graphics&nbsp;backend.&quot;&quot;&quot;<br>
<br>
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
import&nbsp;ctypes<br>
from&nbsp;typing&nbsp;import&nbsp;Dict,&nbsp;Tuple<br>
<br>
import&nbsp;numpy&nbsp;as&nbsp;np<br>
from&nbsp;OpenGL&nbsp;import&nbsp;GL&nbsp;as&nbsp;gl<br>
from&nbsp;OpenGL&nbsp;import&nbsp;GL&nbsp;as&nbsp;GL<br>
from&nbsp;OpenGL.raw.GL.VERSION.GL_2_0&nbsp;import&nbsp;glVertexAttribPointer&nbsp;as&nbsp;_gl_vertex_attrib_pointer<br>
<br>
from&nbsp;termin.mesh.mesh&nbsp;import&nbsp;Mesh,&nbsp;VertexAttribType<br>
<br>
from&nbsp;termin.visualization.platform.backends.base&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;FramebufferHandle,<br>
&nbsp;&nbsp;&nbsp;&nbsp;GraphicsBackend,<br>
&nbsp;&nbsp;&nbsp;&nbsp;MeshHandle,<br>
&nbsp;&nbsp;&nbsp;&nbsp;PolylineHandle,<br>
&nbsp;&nbsp;&nbsp;&nbsp;ShaderHandle,<br>
&nbsp;&nbsp;&nbsp;&nbsp;TextureHandle,<br>
)<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;OpenGLGraphicsBackend&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;OpenGLShaderHandle&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;OpenGLMeshHandle&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;OpenGLPolylineHandle&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;OpenGLTextureHandle&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;OpenGLFramebufferHandle&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;GL_TYPE_MAP&quot;,<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
