<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/render/framegraph/passes/canvas.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
from&nbsp;termin.visualization.render.framegraph.context&nbsp;import&nbsp;FrameContext<br>
from&nbsp;termin.visualization.render.framegraph.passes.base&nbsp;import&nbsp;RenderFramePass<br>
<br>
<br>
class&nbsp;CanvasPass(RenderFramePass):<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;src:&nbsp;str&nbsp;=&nbsp;&quot;screen&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;dst:&nbsp;str&nbsp;=&nbsp;&quot;screen+ui&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pass_name:&nbsp;str&nbsp;=&nbsp;&quot;Canvas&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pass_name=pass_name,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;reads={src},<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;writes={dst},<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inplace=True,&nbsp;&nbsp;#&nbsp;&lt;-&nbsp;ключевое:&nbsp;модифицирующий&nbsp;пасс<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.src&nbsp;=&nbsp;src<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.dst&nbsp;=&nbsp;dst<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;execute(self,&nbsp;ctx:&nbsp;FrameContext):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gfx&nbsp;=&nbsp;ctx.graphics<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;window&nbsp;=&nbsp;ctx.window<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;viewport&nbsp;=&nbsp;ctx.viewport<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;px,&nbsp;py,&nbsp;pw,&nbsp;ph&nbsp;=&nbsp;ctx.rect<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;key&nbsp;=&nbsp;ctx.context_key<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;fb_out&nbsp;=&nbsp;ctx.fbos.get(self.dst)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gfx.bind_framebuffer(fb_out)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gfx.set_viewport(0,&nbsp;0,&nbsp;pw,&nbsp;ph)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;viewport.canvas:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;viewport.canvas.render(gfx,&nbsp;key,&nbsp;(0,&nbsp;0,&nbsp;pw,&nbsp;ph))<br>
<!-- END SCAT CODE -->
</body>
</html>
