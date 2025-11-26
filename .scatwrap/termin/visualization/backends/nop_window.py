<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/backends/nop_window.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from typing import Any, Optional, Tuple<br>
from .base import BackendWindow, WindowBackend<br>
<br>
class NOPWindowHandle(BackendWindow):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Псевдо-окно:<br>
&#9;- имеет размеры;<br>
&#9;- хранит курсор;<br>
&#9;- умеет закрываться;<br>
&#9;- хранит коллбеки, но сам их не вызывает.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, width: int, height: int, title: str, share: Optional[BackendWindow] = None):<br>
&#9;&#9;self._width = width<br>
&#9;&#9;self._height = height<br>
&#9;&#9;self._closed = False<br>
&#9;&#9;self._user_ptr: Any = None<br>
<br>
&#9;&#9;self._cursor_x: float = 0.0<br>
&#9;&#9;self._cursor_y: float = 0.0<br>
<br>
&#9;&#9;# Коллбеки, чтобы Window мог их установить<br>
&#9;&#9;self._framebuffer_callback = None<br>
&#9;&#9;self._cursor_callback = None<br>
&#9;&#9;self._scroll_callback = None<br>
&#9;&#9;self._mouse_callback = None<br>
&#9;&#9;self._key_callback = None<br>
<br>
&#9;# --- BackendWindow API ----------------------------------------------<br>
<br>
&#9;def close(self):<br>
&#9;&#9;self._closed = True<br>
<br>
&#9;def should_close(self) -&gt; bool:<br>
&#9;&#9;return self._closed is True<br>
<br>
&#9;def make_current(self):<br>
&#9;&#9;# Нет реального контекста, просто заглушка<br>
&#9;&#9;pass<br>
<br>
&#9;def swap_buffers(self):<br>
&#9;&#9;# Ничего не свапаем<br>
&#9;&#9;pass<br>
<br>
&#9;def framebuffer_size(self) -&gt; Tuple[int, int]:<br>
&#9;&#9;return self._width, self._height<br>
<br>
&#9;def window_size(self) -&gt; Tuple[int, int]:<br>
&#9;&#9;return self._width, self._height<br>
<br>
&#9;def get_cursor_pos(self) -&gt; Tuple[float, float]:<br>
&#9;&#9;return self._cursor_x, self._cursor_y<br>
<br>
&#9;def set_should_close(self, flag: bool):<br>
&#9;&#9;if flag:<br>
&#9;&#9;&#9;self._closed = True<br>
<br>
&#9;def set_user_pointer(self, ptr: Any):<br>
&#9;&#9;self._user_ptr = ptr<br>
<br>
&#9;def set_framebuffer_size_callback(self, callback):<br>
&#9;&#9;self._framebuffer_callback = callback<br>
<br>
&#9;def set_cursor_pos_callback(self, callback):<br>
&#9;&#9;self._cursor_callback = callback<br>
<br>
&#9;def set_scroll_callback(self, callback):<br>
&#9;&#9;self._scroll_callback = callback<br>
<br>
&#9;def set_mouse_button_callback(self, callback):<br>
&#9;&#9;self._mouse_callback = callback<br>
<br>
&#9;def set_key_callback(self, callback):<br>
&#9;&#9;self._key_callback = callback<br>
<br>
&#9;# drives_render() оставляем по умолчанию (из базового класса),<br>
&#9;# то есть False: движок сам будет вызывать render().<br>
&#9;# Если хочешь симулировать push-модель, можно сделать здесь True.<br>
<br>
&#9;def bind_window_framebuffer(self):<br>
&#9;&#9;# Нет реального фреймбуфера, просто заглушка<br>
&#9;&#9;pass<br>
<br>
&#9;def request_update(self):<br>
&#9;&#9;# Нечего обновлять<br>
&#9;&#9;pass<br>
<br>
<br>
class NOPWindowBackend(WindowBackend):<br>
&#9;&quot;&quot;&quot;Оконный бэкенд без настоящих окон (удобно для тестов).&quot;&quot;&quot;<br>
<br>
&#9;def create_window(<br>
&#9;&#9;self,<br>
&#9;&#9;width: int,<br>
&#9;&#9;height: int,<br>
&#9;&#9;title: str,<br>
&#9;&#9;share: Optional[Any] = None,<br>
&#9;) -&gt; NOPWindowHandle:<br>
&#9;&#9;return NOPWindowHandle(width, height, title, share=share)<br>
<br>
&#9;def poll_events(self):<br>
&#9;&#9;# Событий нет, всё молчит<br>
&#9;&#9;pass<br>
<br>
&#9;def terminate(self):<br>
&#9;&#9;# Нечего завершать<br>
&#9;&#9;pass<br>
<!-- END SCAT CODE -->
</body>
</html>
