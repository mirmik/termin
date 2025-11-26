<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/backends/nop_window.py</title>
</head>
<body>
<pre><code>
from typing import Any, Optional, Tuple
from .base import BackendWindow, WindowBackend

class NOPWindowHandle(BackendWindow):
    &quot;&quot;&quot;
    Псевдо-окно:
    - имеет размеры;
    - хранит курсор;
    - умеет закрываться;
    - хранит коллбеки, но сам их не вызывает.
    &quot;&quot;&quot;

    def __init__(self, width: int, height: int, title: str, share: Optional[BackendWindow] = None):
        self._width = width
        self._height = height
        self._closed = False
        self._user_ptr: Any = None

        self._cursor_x: float = 0.0
        self._cursor_y: float = 0.0

        # Коллбеки, чтобы Window мог их установить
        self._framebuffer_callback = None
        self._cursor_callback = None
        self._scroll_callback = None
        self._mouse_callback = None
        self._key_callback = None

    # --- BackendWindow API ----------------------------------------------

    def close(self):
        self._closed = True

    def should_close(self) -&gt; bool:
        return self._closed is True

    def make_current(self):
        # Нет реального контекста, просто заглушка
        pass

    def swap_buffers(self):
        # Ничего не свапаем
        pass

    def framebuffer_size(self) -&gt; Tuple[int, int]:
        return self._width, self._height

    def window_size(self) -&gt; Tuple[int, int]:
        return self._width, self._height

    def get_cursor_pos(self) -&gt; Tuple[float, float]:
        return self._cursor_x, self._cursor_y

    def set_should_close(self, flag: bool):
        if flag:
            self._closed = True

    def set_user_pointer(self, ptr: Any):
        self._user_ptr = ptr

    def set_framebuffer_size_callback(self, callback):
        self._framebuffer_callback = callback

    def set_cursor_pos_callback(self, callback):
        self._cursor_callback = callback

    def set_scroll_callback(self, callback):
        self._scroll_callback = callback

    def set_mouse_button_callback(self, callback):
        self._mouse_callback = callback

    def set_key_callback(self, callback):
        self._key_callback = callback

    # drives_render() оставляем по умолчанию (из базового класса),
    # то есть False: движок сам будет вызывать render().
    # Если хочешь симулировать push-модель, можно сделать здесь True.

    def bind_window_framebuffer(self):
        # Нет реального фреймбуфера, просто заглушка
        pass

    def request_update(self):
        # Нечего обновлять
        pass


class NOPWindowBackend(WindowBackend):
    &quot;&quot;&quot;Оконный бэкенд без настоящих окон (удобно для тестов).&quot;&quot;&quot;

    def create_window(
        self,
        width: int,
        height: int,
        title: str,
        share: Optional[Any] = None,
    ) -&gt; NOPWindowHandle:
        return NOPWindowHandle(width, height, title, share=share)

    def poll_events(self):
        # Событий нет, всё молчит
        pass

    def terminate(self):
        # Нечего завершать
        pass

</code></pre>
</body>
</html>
