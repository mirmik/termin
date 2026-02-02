<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/core/input_events.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Input&nbsp;event&nbsp;structures.<br>
<br>
Re-exports&nbsp;C++&nbsp;event&nbsp;classes&nbsp;from&nbsp;_entity_native&nbsp;module.<br>
These&nbsp;structures&nbsp;are&nbsp;used&nbsp;for&nbsp;input&nbsp;event&nbsp;dispatch&nbsp;between<br>
the&nbsp;platform&nbsp;layer&nbsp;and&nbsp;C++&nbsp;components.<br>
<br>
Классы&nbsp;событий:<br>
&nbsp;&nbsp;&nbsp;&nbsp;MouseButtonEvent:&nbsp;событие&nbsp;нажатия/отпускания&nbsp;кнопки&nbsp;мыши<br>
&nbsp;&nbsp;&nbsp;&nbsp;MouseMoveEvent:&nbsp;событие&nbsp;перемещения&nbsp;мыши<br>
&nbsp;&nbsp;&nbsp;&nbsp;ScrollEvent:&nbsp;событие&nbsp;прокрутки&nbsp;колеса&nbsp;мыши<br>
&nbsp;&nbsp;&nbsp;&nbsp;KeyEvent:&nbsp;событие&nbsp;клавиатуры<br>
<br>
Константы:<br>
&nbsp;&nbsp;&nbsp;&nbsp;MouseButton.Left/Right/Middle:&nbsp;кнопки&nbsp;мыши&nbsp;(0,&nbsp;1,&nbsp;2)<br>
&nbsp;&nbsp;&nbsp;&nbsp;Action.Release/Press/Repeat:&nbsp;действия&nbsp;(0,&nbsp;1,&nbsp;2)<br>
&nbsp;&nbsp;&nbsp;&nbsp;Mods.Shift/Ctrl/Alt/Super:&nbsp;модификаторы&nbsp;(1,&nbsp;2,&nbsp;4,&nbsp;8)<br>
<br>
Все&nbsp;события&nbsp;содержат&nbsp;поле&nbsp;viewport&nbsp;типа&nbsp;TcViewport&nbsp;(Viewport).<br>
&quot;&quot;&quot;<br>
<br>
from&nbsp;__future__&nbsp;import&nbsp;annotations<br>
<br>
#&nbsp;Import&nbsp;C++&nbsp;event&nbsp;classes<br>
from&nbsp;termin.entity._entity_native&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;MouseButtonEvent,<br>
&nbsp;&nbsp;&nbsp;&nbsp;MouseMoveEvent,<br>
&nbsp;&nbsp;&nbsp;&nbsp;ScrollEvent,<br>
&nbsp;&nbsp;&nbsp;&nbsp;KeyEvent,<br>
&nbsp;&nbsp;&nbsp;&nbsp;MouseButton,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Action,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Mods,<br>
)<br>
<br>
#&nbsp;Re-export&nbsp;Viewport&nbsp;for&nbsp;type&nbsp;hints<br>
from&nbsp;termin.viewport&nbsp;import&nbsp;Viewport<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;MouseButtonEvent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;MouseMoveEvent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;ScrollEvent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;KeyEvent&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;MouseButton&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Action&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Mods&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;Viewport&quot;,<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
