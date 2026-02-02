<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/render/shadow/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Модуль&nbsp;для&nbsp;shadow&nbsp;mapping.&quot;&quot;&quot;<br>
<br>
from&nbsp;termin.visualization.render.shadow.shadow_camera&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;ShadowCameraParams,<br>
&nbsp;&nbsp;&nbsp;&nbsp;build_shadow_view_matrix,<br>
&nbsp;&nbsp;&nbsp;&nbsp;build_shadow_projection_matrix,<br>
&nbsp;&nbsp;&nbsp;&nbsp;compute_light_space_matrix,<br>
)<br>
#&nbsp;ShadowMapArrayResource&nbsp;и&nbsp;ShadowMapArrayEntry&nbsp;перенесены&nbsp;в&nbsp;framegraph.resource<br>
from&nbsp;termin.visualization.render.framegraph.resource&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;ShadowMapArrayEntry,<br>
&nbsp;&nbsp;&nbsp;&nbsp;ShadowMapArrayResource,<br>
)<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;ShadowCameraParams&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;build_shadow_view_matrix&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;build_shadow_projection_matrix&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;compute_light_space_matrix&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;ShadowMapArrayEntry&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;ShadowMapArrayResource&quot;,<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
