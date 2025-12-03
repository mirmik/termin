<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/render/framegraph/pipeline.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
RenderPipeline&nbsp;—&nbsp;контейнер&nbsp;для&nbsp;конвейера&nbsp;рендеринга.<br>
<br>
Содержит:<br>
-&nbsp;passes:&nbsp;список&nbsp;FramePass,&nbsp;определяющих&nbsp;порядок&nbsp;рендеринга<br>
-&nbsp;clear_resources:&nbsp;список&nbsp;ресурсов&nbsp;(FBO),&nbsp;которые&nbsp;нужно&nbsp;очистить&nbsp;перед&nbsp;стартом<br>
<br>
Также&nbsp;хранит&nbsp;ссылку&nbsp;на&nbsp;DebugBlitPass,&nbsp;чтобы&nbsp;дебаггер&nbsp;мог<br>
напрямую&nbsp;управлять&nbsp;его&nbsp;состоянием&nbsp;(reads,&nbsp;enabled).<br>
&quot;&quot;&quot;<br>
<br>
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
from&nbsp;dataclasses&nbsp;import&nbsp;dataclass,&nbsp;field<br>
from&nbsp;typing&nbsp;import&nbsp;TYPE_CHECKING,&nbsp;List<br>
<br>
from&nbsp;termin.visualization.render.framegraph.resource_spec&nbsp;import&nbsp;ResourceSpec<br>
<br>
if&nbsp;TYPE_CHECKING:<br>
&nbsp;&nbsp;&nbsp;&nbsp;from&nbsp;termin.visualization.render.framegraph.core&nbsp;import&nbsp;FramePass<br>
&nbsp;&nbsp;&nbsp;&nbsp;from&nbsp;termin.visualization.render.framegraph.passes.present&nbsp;import&nbsp;BlitPass<br>
<br>
<br>
@dataclass<br>
class&nbsp;RenderPipeline:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Контейнер&nbsp;конвейера&nbsp;рендеринга.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;passes:&nbsp;список&nbsp;FramePass<br>
&nbsp;&nbsp;&nbsp;&nbsp;debug_blit_pass:&nbsp;ссылка&nbsp;на&nbsp;BlitPass&nbsp;для&nbsp;управления&nbsp;из&nbsp;дебаггера&nbsp;(опционально)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Спецификации&nbsp;ресурсов&nbsp;(размер,&nbsp;очистка,&nbsp;формат)&nbsp;теперь&nbsp;объявляются<br>
&nbsp;&nbsp;&nbsp;&nbsp;самими&nbsp;pass'ами&nbsp;через&nbsp;метод&nbsp;get_resource_specs().<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;passes:&nbsp;List[&quot;FramePass&quot;]&nbsp;=&nbsp;field(default_factory=list)<br>
&nbsp;&nbsp;&nbsp;&nbsp;debug_blit_pass:&nbsp;&quot;BlitPass&nbsp;|&nbsp;None&quot;&nbsp;=&nbsp;None<br>
&nbsp;&nbsp;&nbsp;&nbsp;pipeline_specs:&nbsp;List[ResourceSpec]&nbsp;=&nbsp;field(default_factory=list)<br>
<!-- END SCAT CODE -->
</body>
</html>
