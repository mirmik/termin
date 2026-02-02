<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/platform/backends/opengl.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;OpenGL&nbsp;context&nbsp;management.<br>
<br>
The&nbsp;main&nbsp;OpenGLGraphicsBackend&nbsp;is&nbsp;now&nbsp;in&nbsp;C++&nbsp;(_native&nbsp;module).<br>
This&nbsp;file&nbsp;contains&nbsp;context&nbsp;management&nbsp;for&nbsp;GPU&nbsp;resource&nbsp;cleanup.<br>
<br>
Framebuffer&nbsp;handles&nbsp;are&nbsp;now&nbsp;created&nbsp;via:<br>
-&nbsp;OpenGLGraphicsBackend.create_framebuffer(width,&nbsp;height)&nbsp;-&nbsp;for&nbsp;offscreen&nbsp;rendering<br>
-&nbsp;OpenGLGraphicsBackend.create_shadow_framebuffer(width,&nbsp;height)&nbsp;-&nbsp;for&nbsp;shadows<br>
-&nbsp;OpenGLGraphicsBackend.create_external_framebuffer(fbo_id,&nbsp;width,&nbsp;height)&nbsp;-&nbsp;for&nbsp;window&nbsp;FBOs<br>
&quot;&quot;&quot;<br>
<br>
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
from&nbsp;typing&nbsp;import&nbsp;Callable<br>
<br>
#&nbsp;---&nbsp;Context&nbsp;Management&nbsp;---<br>
#&nbsp;Single&nbsp;context&nbsp;-&nbsp;used&nbsp;for&nbsp;making&nbsp;context&nbsp;current&nbsp;before&nbsp;GPU&nbsp;operations<br>
<br>
_make_current_fn:&nbsp;Callable[[],&nbsp;None]&nbsp;|&nbsp;None&nbsp;=&nbsp;None<br>
<br>
<br>
def&nbsp;register_context(make_current:&nbsp;Callable[[],&nbsp;None])&nbsp;-&gt;&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Register&nbsp;the&nbsp;context's&nbsp;make_current&nbsp;function.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;global&nbsp;_make_current_fn<br>
&nbsp;&nbsp;&nbsp;&nbsp;_make_current_fn&nbsp;=&nbsp;make_current<br>
<br>
<br>
def&nbsp;get_make_current()&nbsp;-&gt;&nbsp;Callable[[],&nbsp;None]&nbsp;|&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Get&nbsp;the&nbsp;make_current&nbsp;function.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;_make_current_fn<br>
<!-- END SCAT CODE -->
</body>
</html>
