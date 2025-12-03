<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/render/framegraph/resource_spec.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
from&nbsp;dataclasses&nbsp;import&nbsp;dataclass<br>
from&nbsp;typing&nbsp;import&nbsp;Tuple<br>
<br>
<br>
@dataclass<br>
class&nbsp;ResourceSpec:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Спецификация&nbsp;требований&nbsp;к&nbsp;ресурсу&nbsp;конвейера.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Объединяет&nbsp;различные&nbsp;требования&nbsp;pass'а&nbsp;к&nbsp;ресурсу:<br>
&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;Тип&nbsp;ресурса&nbsp;(FBO,&nbsp;ShadowMapArray,&nbsp;и&nbsp;т.д.)<br>
&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;Размер&nbsp;(например,&nbsp;для&nbsp;shadow&nbsp;map&nbsp;—&nbsp;фиксированный&nbsp;1024x1024)<br>
&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;Очистка&nbsp;(цвет&nbsp;и/или&nbsp;глубина)<br>
&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;Формат&nbsp;(для&nbsp;будущего:&nbsp;depth&nbsp;texture,&nbsp;RGBA16F&nbsp;и&nbsp;т.д.)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Атрибуты:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;resource:&nbsp;имя&nbsp;ресурса<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;resource_type:&nbsp;тип&nbsp;ресурса:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;&quot;fbo&quot;&nbsp;(по&nbsp;умолчанию)&nbsp;—&nbsp;стандартный&nbsp;framebuffer<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;&quot;shadow_map_array&quot;&nbsp;—&nbsp;массив&nbsp;shadow&nbsp;maps&nbsp;(ShadowMapArray)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;size:&nbsp;требуемый&nbsp;размер&nbsp;(width,&nbsp;height)&nbsp;или&nbsp;None&nbsp;для&nbsp;размера&nbsp;viewport'а<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;clear_color:&nbsp;RGBA&nbsp;цвет&nbsp;очистки&nbsp;(None&nbsp;—&nbsp;не&nbsp;очищать&nbsp;цвет)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;clear_depth:&nbsp;значение&nbsp;глубины&nbsp;(None&nbsp;—&nbsp;не&nbsp;очищать&nbsp;глубину)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;format:&nbsp;формат&nbsp;текстуры/attachment'ов&nbsp;(None&nbsp;—&nbsp;по&nbsp;умолчанию)<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Если&nbsp;спек&nbsp;для&nbsp;ресурса&nbsp;не&nbsp;объявлен,&nbsp;считается&nbsp;что&nbsp;это&nbsp;FBO&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;с&nbsp;размером&nbsp;viewport'а&nbsp;камеры&nbsp;(обратная&nbsp;совместимость).<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;resource:&nbsp;str<br>
&nbsp;&nbsp;&nbsp;&nbsp;resource_type:&nbsp;str&nbsp;=&nbsp;&quot;fbo&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;size:&nbsp;Tuple[int,&nbsp;int]&nbsp;|&nbsp;None&nbsp;=&nbsp;None<br>
&nbsp;&nbsp;&nbsp;&nbsp;clear_color:&nbsp;Tuple[float,&nbsp;float,&nbsp;float,&nbsp;float]&nbsp;|&nbsp;None&nbsp;=&nbsp;None<br>
&nbsp;&nbsp;&nbsp;&nbsp;clear_depth:&nbsp;float&nbsp;|&nbsp;None&nbsp;=&nbsp;None<br>
&nbsp;&nbsp;&nbsp;&nbsp;format:&nbsp;str&nbsp;|&nbsp;None&nbsp;=&nbsp;None<br>
<!-- END SCAT CODE -->
</body>
</html>
