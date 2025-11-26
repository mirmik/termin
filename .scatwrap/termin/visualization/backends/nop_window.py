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
    &quot;&quot;&quot;<br>
    Псевдо-окно:<br>
    - имеет размеры;<br>
    - хранит курсор;<br>
    - умеет закрываться;<br>
    - хранит коллбеки, но сам их не вызывает.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, width: int, height: int, title: str, share: Optional[BackendWindow] = None):<br>
        self._width = width<br>
        self._height = height<br>
        self._closed = False<br>
        self._user_ptr: Any = None<br>
<br>
        self._cursor_x: float = 0.0<br>
        self._cursor_y: float = 0.0<br>
<br>
        # Коллбеки, чтобы Window мог их установить<br>
        self._framebuffer_callback = None<br>
        self._cursor_callback = None<br>
        self._scroll_callback = None<br>
        self._mouse_callback = None<br>
        self._key_callback = None<br>
<br>
    # --- BackendWindow API ----------------------------------------------<br>
<br>
    def close(self):<br>
        self._closed = True<br>
<br>
    def should_close(self) -&gt; bool:<br>
        return self._closed is True<br>
<br>
    def make_current(self):<br>
        # Нет реального контекста, просто заглушка<br>
        pass<br>
<br>
    def swap_buffers(self):<br>
        # Ничего не свапаем<br>
        pass<br>
<br>
    def framebuffer_size(self) -&gt; Tuple[int, int]:<br>
        return self._width, self._height<br>
<br>
    def window_size(self) -&gt; Tuple[int, int]:<br>
        return self._width, self._height<br>
<br>
    def get_cursor_pos(self) -&gt; Tuple[float, float]:<br>
        return self._cursor_x, self._cursor_y<br>
<br>
    def set_should_close(self, flag: bool):<br>
        if flag:<br>
            self._closed = True<br>
<br>
    def set_user_pointer(self, ptr: Any):<br>
        self._user_ptr = ptr<br>
<br>
    def set_framebuffer_size_callback(self, callback):<br>
        self._framebuffer_callback = callback<br>
<br>
    def set_cursor_pos_callback(self, callback):<br>
        self._cursor_callback = callback<br>
<br>
    def set_scroll_callback(self, callback):<br>
        self._scroll_callback = callback<br>
<br>
    def set_mouse_button_callback(self, callback):<br>
        self._mouse_callback = callback<br>
<br>
    def set_key_callback(self, callback):<br>
        self._key_callback = callback<br>
<br>
    # drives_render() оставляем по умолчанию (из базового класса),<br>
    # то есть False: движок сам будет вызывать render().<br>
    # Если хочешь симулировать push-модель, можно сделать здесь True.<br>
<br>
    def bind_window_framebuffer(self):<br>
        # Нет реального фреймбуфера, просто заглушка<br>
        pass<br>
<br>
    def request_update(self):<br>
        # Нечего обновлять<br>
        pass<br>
<br>
<br>
class NOPWindowBackend(WindowBackend):<br>
    &quot;&quot;&quot;Оконный бэкенд без настоящих окон (удобно для тестов).&quot;&quot;&quot;<br>
<br>
    def create_window(<br>
        self,<br>
        width: int,<br>
        height: int,<br>
        title: str,<br>
        share: Optional[Any] = None,<br>
    ) -&gt; NOPWindowHandle:<br>
        return NOPWindowHandle(width, height, title, share=share)<br>
<br>
    def poll_events(self):<br>
        # Событий нет, всё молчит<br>
        pass<br>
<br>
    def terminate(self):<br>
        # Нечего завершать<br>
        pass<br>
<!-- END SCAT CODE -->
</body>
</html>
