<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/assets/resources/_manager.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;ResourceManager&nbsp;combining&nbsp;all&nbsp;mixins.&quot;&quot;&quot;<br>
<br>
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
from&nbsp;._base&nbsp;import&nbsp;ResourceManagerBase<br>
from&nbsp;._registration&nbsp;import&nbsp;RegistrationMixin<br>
from&nbsp;._assets&nbsp;import&nbsp;AssetsMixin<br>
from&nbsp;._components&nbsp;import&nbsp;ComponentsMixin<br>
from&nbsp;._pipelines&nbsp;import&nbsp;PipelinesMixin<br>
from&nbsp;._scene_pipelines&nbsp;import&nbsp;ScenePipelinesMixin<br>
from&nbsp;._accessors&nbsp;import&nbsp;AccessorsMixin<br>
from&nbsp;._serialization&nbsp;import&nbsp;SerializationMixin<br>
<br>
<br>
class&nbsp;ResourceManager(<br>
&nbsp;&nbsp;&nbsp;&nbsp;ResourceManagerBase,<br>
&nbsp;&nbsp;&nbsp;&nbsp;RegistrationMixin,<br>
&nbsp;&nbsp;&nbsp;&nbsp;AssetsMixin,<br>
&nbsp;&nbsp;&nbsp;&nbsp;ComponentsMixin,<br>
&nbsp;&nbsp;&nbsp;&nbsp;PipelinesMixin,<br>
&nbsp;&nbsp;&nbsp;&nbsp;ScenePipelinesMixin,<br>
&nbsp;&nbsp;&nbsp;&nbsp;AccessorsMixin,<br>
&nbsp;&nbsp;&nbsp;&nbsp;SerializationMixin,<br>
):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Central&nbsp;manager&nbsp;for&nbsp;all&nbsp;resources:&nbsp;materials,&nbsp;meshes,&nbsp;textures,&nbsp;shaders,&nbsp;etc.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;This&nbsp;is&nbsp;a&nbsp;singleton&nbsp;class.&nbsp;Use&nbsp;ResourceManager.instance()&nbsp;to&nbsp;get&nbsp;the&nbsp;instance.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;pass<br>
<!-- END SCAT CODE -->
</body>
</html>
