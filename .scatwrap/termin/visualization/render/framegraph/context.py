<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/render/framegraph/context.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
from&nbsp;dataclasses&nbsp;import&nbsp;dataclass,&nbsp;field<br>
from&nbsp;typing&nbsp;import&nbsp;Any,&nbsp;Dict,&nbsp;Tuple,&nbsp;List<br>
<br>
<br>
@dataclass<br>
class&nbsp;FrameExecutionContext:<br>
&nbsp;&nbsp;&nbsp;&nbsp;graphics:&nbsp;&quot;GraphicsBackend&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;window:&nbsp;&quot;Window&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;viewport:&nbsp;&quot;Viewport&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;rect:&nbsp;Tuple[int,&nbsp;int,&nbsp;int,&nbsp;int]&nbsp;&nbsp;#&nbsp;(px,&nbsp;py,&nbsp;pw,&nbsp;ph)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;карта&nbsp;ресурс&nbsp;-&gt;&nbsp;FBO&nbsp;(или&nbsp;None,&nbsp;если&nbsp;это&nbsp;swapchain/экран)<br>
&nbsp;&nbsp;&nbsp;&nbsp;fbos:&nbsp;Dict[str,&nbsp;&quot;FramebufferHandle&quot;&nbsp;|&nbsp;None]<br>
<br>
<br>
@dataclass<br>
class&nbsp;FrameContext:<br>
&nbsp;&nbsp;&nbsp;&nbsp;window:&nbsp;&quot;Window&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;viewport:&nbsp;&quot;Viewport&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;rect:&nbsp;Tuple[int,&nbsp;int,&nbsp;int,&nbsp;int]<br>
&nbsp;&nbsp;&nbsp;&nbsp;size:&nbsp;Tuple[int,&nbsp;int]<br>
&nbsp;&nbsp;&nbsp;&nbsp;graphics:&nbsp;&quot;GraphicsBackend&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;fbos:&nbsp;Dict[str,&nbsp;Any]&nbsp;=&nbsp;field(default_factory=dict)<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Предвычисленные&nbsp;источники&nbsp;света&nbsp;для&nbsp;текущего&nbsp;кадра/вьюпорта.<br>
&nbsp;&nbsp;&nbsp;&nbsp;lights:&nbsp;List[&quot;Light&quot;]&nbsp;|&nbsp;None&nbsp;=&nbsp;None<br>
<!-- END SCAT CODE -->
</body>
</html>
