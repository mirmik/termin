<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/render/shader.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Shader&nbsp;program&nbsp;-&nbsp;re-export&nbsp;from&nbsp;C++.&quot;&quot;&quot;<br>
<br>
#&nbsp;Re-export&nbsp;C++&nbsp;classes<br>
from&nbsp;termin._native.render&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;TcShader,<br>
&nbsp;&nbsp;&nbsp;&nbsp;GlslPreprocessor,<br>
&nbsp;&nbsp;&nbsp;&nbsp;glsl_preprocessor,<br>
)<br>
<br>
<br>
class&nbsp;ShaderCompilationError(RuntimeError):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Raised&nbsp;when&nbsp;GLSL&nbsp;compilation&nbsp;or&nbsp;program&nbsp;linking&nbsp;fails.&quot;&quot;&quot;<br>
<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;TcShader&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;ShaderCompilationError&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;GlslPreprocessor&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;glsl_preprocessor&quot;,<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
