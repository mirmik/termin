<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/lighting/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Lighting&nbsp;primitives&nbsp;shared&nbsp;by&nbsp;rendering&nbsp;pipelines.&quot;&quot;&quot;<br>
<br>
#&nbsp;Setup&nbsp;DLL&nbsp;paths&nbsp;before&nbsp;importing&nbsp;native&nbsp;extensions<br>
from&nbsp;termin&nbsp;import&nbsp;_dll_setup&nbsp;&nbsp;#&nbsp;noqa:&nbsp;F401<br>
<br>
from&nbsp;termin.lighting._lighting_native&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;AttenuationCoefficients,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Light,<br>
&nbsp;&nbsp;&nbsp;&nbsp;LightComponent,<br>
&nbsp;&nbsp;&nbsp;&nbsp;LightSample,<br>
&nbsp;&nbsp;&nbsp;&nbsp;LightShadowParams,<br>
&nbsp;&nbsp;&nbsp;&nbsp;LightType,<br>
&nbsp;&nbsp;&nbsp;&nbsp;ShadowSettings,<br>
&nbsp;&nbsp;&nbsp;&nbsp;light_type_from_value,<br>
)<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;AttenuationCoefficients&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Light&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;LightComponent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;LightSample&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;LightShadowParams&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;LightType&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;ShadowSettings&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;light_type_from_value&quot;,<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
