<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/components/teleport_component.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;TeleportComponent&nbsp;—&nbsp;телепортирует&nbsp;entity&nbsp;в&nbsp;точку&nbsp;клика&nbsp;по&nbsp;коллайдеру.&quot;&quot;&quot;<br>
<br>
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
from&nbsp;termin.visualization.core.component&nbsp;import&nbsp;InputComponent<br>
from&nbsp;termin.visualization.core.input_events&nbsp;import&nbsp;MouseButtonEvent<br>
from&nbsp;termin.visualization.platform.backends.base&nbsp;import&nbsp;MouseButton,&nbsp;Action<br>
<br>
<br>
class&nbsp;TeleportComponent(InputComponent):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Компонент&nbsp;телепортации.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;При&nbsp;клике&nbsp;ЛКМ&nbsp;делает&nbsp;рейкаст&nbsp;и&nbsp;телепортирует&nbsp;entity<br>
&nbsp;&nbsp;&nbsp;&nbsp;в&nbsp;точку&nbsp;пересечения&nbsp;с&nbsp;коллайдером.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;on_mouse_button(self,&nbsp;event:&nbsp;MouseButtonEvent):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Только&nbsp;при&nbsp;нажатии&nbsp;ЛКМ<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;event.button&nbsp;!=&nbsp;MouseButton.LEFT&nbsp;or&nbsp;event.action&nbsp;!=&nbsp;Action.PRESS:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;self.entity&nbsp;is&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Получаем&nbsp;луч&nbsp;из&nbsp;позиции&nbsp;курсора<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ray&nbsp;=&nbsp;event.viewport.screen_point_to_ray(event.x,&nbsp;event.y)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;ray&nbsp;is&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Рейкаст&nbsp;по&nbsp;сцене<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;scene&nbsp;=&nbsp;event.viewport.scene<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;hit&nbsp;=&nbsp;scene.raycast(ray)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;hit&nbsp;is&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Не&nbsp;телепортируемся&nbsp;в&nbsp;себя<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;hit.entity&nbsp;is&nbsp;self.entity:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Телепортируем&nbsp;в&nbsp;точку&nbsp;пересечения<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;from&nbsp;termin.geombase&nbsp;import&nbsp;Pose3<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;old_pose&nbsp;=&nbsp;self.entity.transform.global_pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;new_pose&nbsp;=&nbsp;Pose3(lin=hit.collider_point,&nbsp;ang=old_pose.ang)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.entity.transform.relocate_global(new_pose)<br>
<!-- END SCAT CODE -->
</body>
</html>
