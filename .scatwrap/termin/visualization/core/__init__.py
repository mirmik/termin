<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/core/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Core&nbsp;scene&nbsp;graph&nbsp;primitives&nbsp;and&nbsp;resource&nbsp;helpers.&quot;&quot;&quot;<br>
<br>
from&nbsp;termin.visualization.core.camera&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;CameraComponent,<br>
&nbsp;&nbsp;&nbsp;&nbsp;OrbitCameraController,<br>
&nbsp;&nbsp;&nbsp;&nbsp;OrthographicCameraComponent,<br>
&nbsp;&nbsp;&nbsp;&nbsp;PerspectiveCameraComponent,<br>
)<br>
from&nbsp;termin.visualization.core.entity&nbsp;import&nbsp;Component,&nbsp;Entity,&nbsp;InputComponent,&nbsp;RenderContext<br>
from&nbsp;termin.visualization.core.line&nbsp;import&nbsp;LineEntity<br>
from&nbsp;termin.visualization.core.material&nbsp;import&nbsp;Material<br>
from&nbsp;termin.visualization.core.mesh&nbsp;import&nbsp;Mesh2Drawable,&nbsp;MeshDrawable<br>
from&nbsp;termin.visualization.core.picking&nbsp;import&nbsp;id_to_rgb,&nbsp;rgb_to_id<br>
from&nbsp;termin.visualization.core.polyline&nbsp;import&nbsp;Polyline,&nbsp;PolylineDrawable<br>
from&nbsp;termin.visualization.core.resources&nbsp;import&nbsp;ResourceManager<br>
from&nbsp;termin.visualization.core.scene&nbsp;import&nbsp;Scene<br>
from&nbsp;termin.visualization.core.serialization&nbsp;import&nbsp;COMPONENT_REGISTRY,&nbsp;serializable<br>
from&nbsp;termin.visualization.core.lighting.light&nbsp;import&nbsp;Light,&nbsp;LightSample,&nbsp;LightShadowParams,&nbsp;LightType<br>
from&nbsp;termin.visualization.core.lighting.attenuation&nbsp;import&nbsp;AttenuationCoefficients<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;CameraComponent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;OrbitCameraController&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;OrthographicCameraComponent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;PerspectiveCameraComponent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Component&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Entity&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;InputComponent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;RenderContext&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;LineEntity&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Material&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Mesh2Drawable&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;MeshDrawable&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Polyline&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;PolylineDrawable&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;ResourceManager&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Scene&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;id_to_rgb&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;rgb_to_id&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;serializable&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;COMPONENT_REGISTRY&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Light&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;LightSample&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;LightShadowParams&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;LightType&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;AttenuationCoefficients&quot;,<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
