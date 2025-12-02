<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/render/framegraph/passes/base.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
from&nbsp;termin.visualization.render.framegraph.core&nbsp;import&nbsp;FramePass<br>
<br>
<br>
class&nbsp;RenderFramePass(FramePass):<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;execute(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;graphics:&nbsp;&quot;GraphicsBackend&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;reads_fbos:&nbsp;dict[str,&nbsp;&quot;FramebufferHandle&quot;&nbsp;|&nbsp;None],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;writes_fbos:&nbsp;dict[str,&nbsp;&quot;FramebufferHandle&quot;&nbsp;|&nbsp;None],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rect:&nbsp;tuple[int,&nbsp;int,&nbsp;int,&nbsp;int],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;scene:&nbsp;&quot;Scene&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;camera:&nbsp;&quot;Camera&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;context_key:&nbsp;int,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;lights:&nbsp;list[&quot;Light&quot;]&nbsp;|&nbsp;None&nbsp;=&nbsp;None,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;canvas=None,<br>
&nbsp;&nbsp;&nbsp;&nbsp;)&nbsp;-&gt;&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Абстрактное&nbsp;выполнение&nbsp;прохода&nbsp;кадра.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Все&nbsp;зависимости&nbsp;прокидываются&nbsp;явно:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;graphics:&nbsp;графический&nbsp;бэкенд;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;reads_fbos:&nbsp;карта&nbsp;FBO,&nbsp;из&nbsp;которых&nbsp;пасс&nbsp;читает;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;writes_fbos:&nbsp;карта&nbsp;FBO,&nbsp;в&nbsp;которые&nbsp;пасс&nbsp;пишет;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;rect:&nbsp;(px,&nbsp;py,&nbsp;pw,&nbsp;ph)&nbsp;–&nbsp;целевой&nbsp;прямоугольник&nbsp;вывода&nbsp;в&nbsp;пикселях;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;scene,&nbsp;camera,&nbsp;renderer:&nbsp;объекты&nbsp;текущего&nbsp;вьюпорта;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;context_key:&nbsp;ключ&nbsp;для&nbsp;кэшей&nbsp;VAO/шейдеров;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;lights:&nbsp;предвычисленные&nbsp;источники&nbsp;света&nbsp;(может&nbsp;быть&nbsp;None);<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;canvas:&nbsp;2D-канва&nbsp;вьюпорта&nbsp;(для&nbsp;CanvasPass).<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise&nbsp;NotImplementedError<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;required_resources(self)&nbsp;-&gt;&nbsp;set[str]:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Возвращает&nbsp;множество&nbsp;ресурсов,&nbsp;которые&nbsp;должны&nbsp;быть&nbsp;доступны&nbsp;пассу.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;По&nbsp;умолчанию&nbsp;это&nbsp;объединение&nbsp;reads&nbsp;и&nbsp;writes,&nbsp;но&nbsp;конкретные&nbsp;пассы<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;могут&nbsp;переопределить&nbsp;метод,&nbsp;если&nbsp;набор&nbsp;зависимостей&nbsp;меняется<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;динамически&nbsp;(например,&nbsp;BlitPass&nbsp;с&nbsp;переключаемым&nbsp;источником).<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;set(self.reads)&nbsp;|&nbsp;set(self.writes)<br>
<!-- END SCAT CODE -->
</body>
</html>
