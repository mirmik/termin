<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/tween/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Tween&nbsp;module&nbsp;-&nbsp;smooth&nbsp;parameter&nbsp;animation&nbsp;system.<br>
<br>
Usage:<br>
&nbsp;&nbsp;&nbsp;&nbsp;from&nbsp;termin.tween&nbsp;import&nbsp;TweenManagerComponent,&nbsp;Ease<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Add&nbsp;to&nbsp;scene<br>
&nbsp;&nbsp;&nbsp;&nbsp;tween_entity&nbsp;=&nbsp;Entity(name=&quot;TweenManager&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;tweens&nbsp;=&nbsp;TweenManagerComponent()<br>
&nbsp;&nbsp;&nbsp;&nbsp;tween_entity.add_component(tweens)<br>
&nbsp;&nbsp;&nbsp;&nbsp;scene.add(tween_entity)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Create&nbsp;tweens<br>
&nbsp;&nbsp;&nbsp;&nbsp;tweens.move(entity.transform,&nbsp;target_pos,&nbsp;1.0,&nbsp;ease=Ease.OUT_QUAD)<br>
&nbsp;&nbsp;&nbsp;&nbsp;tweens.rotate(entity.transform,&nbsp;target_quat,&nbsp;0.5,&nbsp;ease=Ease.IN_OUT_CUBIC)<br>
&nbsp;&nbsp;&nbsp;&nbsp;tweens.scale(entity.transform,&nbsp;2.0,&nbsp;0.3)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;With&nbsp;callbacks<br>
&nbsp;&nbsp;&nbsp;&nbsp;tweens.move(entity.transform,&nbsp;pos,&nbsp;1.0).on_complete(lambda:&nbsp;print(&quot;Done!&quot;))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Chaining<br>
&nbsp;&nbsp;&nbsp;&nbsp;tweens.move(entity.transform,&nbsp;pos1,&nbsp;1.0).on_complete(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;lambda:&nbsp;tweens.move(entity.transform,&nbsp;pos2,&nbsp;1.0)<br>
&nbsp;&nbsp;&nbsp;&nbsp;)<br>
&quot;&quot;&quot;<br>
<br>
from&nbsp;termin.tween.ease&nbsp;import&nbsp;Ease<br>
from&nbsp;termin.tween.tween&nbsp;import&nbsp;Tween,&nbsp;TweenState,&nbsp;MoveTween,&nbsp;RotateTween,&nbsp;ScaleTween<br>
from&nbsp;termin.tween.manager&nbsp;import&nbsp;TweenManager<br>
from&nbsp;termin.tween.component&nbsp;import&nbsp;TweenManagerComponent<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Easing<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Ease&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Base&nbsp;classes<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Tween&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;TweenState&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Transform&nbsp;tweens<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;MoveTween&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;RotateTween&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;ScaleTween&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Manager<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;TweenManager&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;TweenManagerComponent&quot;,<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
