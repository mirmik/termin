<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/entity/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Entity&nbsp;and&nbsp;Component&nbsp;system.<br>
<br>
Re-exports&nbsp;from&nbsp;C++&nbsp;backend.<br>
Component&nbsp;and&nbsp;InputComponent&nbsp;are&nbsp;available&nbsp;via&nbsp;termin.visualization.core.component.<br>
&quot;&quot;&quot;<br>
<br>
#&nbsp;Setup&nbsp;DLL&nbsp;paths&nbsp;before&nbsp;importing&nbsp;native&nbsp;extensions<br>
from&nbsp;termin&nbsp;import&nbsp;_dll_setup&nbsp;&nbsp;#&nbsp;noqa:&nbsp;F401<br>
<br>
#&nbsp;Import&nbsp;_geom_native&nbsp;first&nbsp;to&nbsp;register&nbsp;Mat44&nbsp;type&nbsp;before&nbsp;_entity_native&nbsp;uses&nbsp;it<br>
from&nbsp;termin.geombase&nbsp;import&nbsp;_geom_native&nbsp;&nbsp;#&nbsp;noqa:&nbsp;F401<br>
<br>
#&nbsp;Import&nbsp;_viewport_native&nbsp;to&nbsp;register&nbsp;TcViewport&nbsp;type&nbsp;before&nbsp;_entity_native&nbsp;uses&nbsp;it<br>
from&nbsp;termin.viewport&nbsp;import&nbsp;_viewport_native&nbsp;&nbsp;#&nbsp;noqa:&nbsp;F401<br>
from&nbsp;termin.viewport&nbsp;import&nbsp;Viewport<br>
<br>
from&nbsp;termin.entity._entity_native&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;Entity,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Component,<br>
&nbsp;&nbsp;&nbsp;&nbsp;ComponentRegistry,<br>
&nbsp;&nbsp;&nbsp;&nbsp;EntityRegistry,<br>
&nbsp;&nbsp;&nbsp;&nbsp;TcComponentRef,<br>
&nbsp;&nbsp;&nbsp;&nbsp;TcSceneRef,<br>
&nbsp;&nbsp;&nbsp;&nbsp;CameraComponent,<br>
&nbsp;&nbsp;&nbsp;&nbsp;PerspectiveCameraComponent,<br>
&nbsp;&nbsp;&nbsp;&nbsp;OrthographicCameraComponent,<br>
)<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Component&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Entity&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;ComponentRegistry&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;EntityRegistry&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;TcComponentRef&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;TcSceneRef&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Viewport&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;CameraComponent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;PerspectiveCameraComponent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;OrthographicCameraComponent&quot;,<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
