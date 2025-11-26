<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/backends/qt.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;PyQt5-based window backend using QOpenGLWindow.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
from typing import Callable, Optional, Any<br>
<br>
from PyQt5 import QtCore, QtGui, QtWidgets<br>
<br>
from .base import Action, BackendWindow, Key, MouseButton, WindowBackend<br>
<br>
from OpenGL import GL<br>
from OpenGL import GL as gl<br>
<br>
<br>
<br>
def _qt_app() -&gt; QtWidgets.QApplication:<br>
&#9;app = QtWidgets.QApplication.instance()<br>
&#9;if app is None:<br>
&#9;&#9;app = QtWidgets.QApplication([])<br>
&#9;return app<br>
<br>
<br>
def _translate_mouse(button: QtCore.Qt.MouseButton) -&gt; MouseButton:<br>
&#9;if button == QtCore.Qt.LeftButton:<br>
&#9;&#9;return MouseButton.LEFT<br>
&#9;if button == QtCore.Qt.RightButton:<br>
&#9;&#9;return MouseButton.RIGHT<br>
&#9;if button == QtCore.Qt.MiddleButton:<br>
&#9;&#9;return MouseButton.MIDDLE<br>
&#9;return MouseButton.LEFT<br>
<br>
<br>
def _translate_action(action: bool) -&gt; Action:<br>
&#9;return Action.PRESS if action else Action.RELEASE<br>
<br>
<br>
def _translate_key(key: int) -&gt; Key:<br>
&#9;if key == QtCore.Qt.Key_Escape:<br>
&#9;&#9;return Key.ESCAPE<br>
&#9;if key == QtCore.Qt.Key_Space:<br>
&#9;&#9;return Key.SPACE<br>
&#9;try:<br>
&#9;&#9;return Key(key)<br>
&#9;except ValueError:<br>
&#9;&#9;return Key.UNKNOWN<br>
<br>
<br>
class _QtGLWidget(QtWidgets.QOpenGLWidget):<br>
&#9;def __init__(self, owner: &quot;QtGLWindowHandle&quot;, parent=None):<br>
&#9;&#9;super().__init__(parent)<br>
&#9;&#9;self._owner = owner<br>
&#9;&#9;self.setFocusPolicy(QtCore.Qt.StrongFocus)<br>
&#9;&#9;self.setUpdateBehavior(QtWidgets.QOpenGLWidget.PartialUpdate)<br>
&#9;&#9;self.setMouseTracking(True)<br>
<br>
&#9;# --- События мыши / клавиатуры --------------------------------------<br>
<br>
&#9;def mousePressEvent(self, event):<br>
&#9;&#9;cb = self._owner._mouse_callback<br>
&#9;&#9;if cb:<br>
&#9;&#9;&#9;cb(self._owner, _translate_mouse(event.button()), Action.PRESS, int(event.modifiers()))<br>
<br>
&#9;def mouseReleaseEvent(self, event):<br>
&#9;&#9;cb = self._owner._mouse_callback<br>
&#9;&#9;if cb:<br>
&#9;&#9;&#9;cb(self._owner, _translate_mouse(event.button()), Action.RELEASE, int(event.modifiers()))<br>
<br>
&#9;def mouseMoveEvent(self, event):<br>
&#9;&#9;cb = self._owner._cursor_callback<br>
&#9;&#9;if cb:<br>
&#9;&#9;&#9;cb(self._owner, float(event.x()), float(event.y()))<br>
<br>
&#9;def wheelEvent(self, event):<br>
&#9;&#9;angle = event.angleDelta()<br>
&#9;&#9;cb = self._owner._scroll_callback<br>
&#9;&#9;if cb:<br>
&#9;&#9;&#9;cb(self._owner, angle.x() / 120.0, angle.y() / 120.0)<br>
<br>
&#9;def keyPressEvent(self, event):<br>
&#9;&#9;cb = self._owner._key_callback<br>
&#9;&#9;if cb:<br>
&#9;&#9;&#9;cb(self._owner, _translate_key(event.key()), event.nativeScanCode(), Action.PRESS, int(event.modifiers()))<br>
<br>
&#9;def keyReleaseEvent(self, event):<br>
&#9;&#9;cb = self._owner._key_callback<br>
&#9;&#9;if cb:<br>
&#9;&#9;&#9;cb(self._owner, _translate_key(event.key()), event.nativeScanCode(), Action.RELEASE, int(event.modifiers()))<br>
<br>
&#9;# --- Рендер ----------------------------------------------------------<br>
<br>
&#9;def paintGL(self):<br>
&#9;&#9;# Тут есть активный GL-контекст — выполняем рендер движка<br>
&#9;&#9;window_obj = self._owner._user_ptr<br>
&#9;&#9;if window_obj is not None:<br>
&#9;&#9;&#9;window_obj._render_core(from_backend=True)<br>
<br>
&#9;def resizeGL(self, w, h):<br>
&#9;&#9;cb = self._owner._framebuffer_callback<br>
&#9;&#9;if cb:<br>
&#9;&#9;&#9;cb(self._owner, w, h)<br>
<br>
<br>
class QtGLWindowHandle(BackendWindow):<br>
&#9;def __init__(self, width, height, title, share=None, parent=None):<br>
&#9;&#9;self.app = _qt_app()<br>
<br>
&#9;&#9;self._widget = _QtGLWidget(self, parent=parent)<br>
&#9;&#9;self._widget.setMinimumSize(50, 50)<br>
&#9;&#9;self._widget.resize(width, height)<br>
&#9;&#9;self._widget.show()<br>
<br>
&#9;&#9;self._closed = False<br>
&#9;&#9;self._user_ptr = None<br>
<br>
&#9;&#9;# Все callback-и окна (их вызывает Window)<br>
&#9;&#9;self._framebuffer_callback = None<br>
&#9;&#9;self._cursor_callback = None<br>
&#9;&#9;self._scroll_callback = None<br>
&#9;&#9;self._mouse_callback = None<br>
&#9;&#9;self._key_callback = None<br>
<br>
&#9;# --- BackendWindow API ----------------------------------------------<br>
<br>
&#9;def close(self):<br>
&#9;&#9;if self._closed:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;self._closed = True<br>
&#9;&#9;self._widget.close()<br>
<br>
&#9;def should_close(self) -&gt; bool:<br>
&#9;&#9;return self._closed or not self._widget.isVisible()<br>
<br>
&#9;def make_current(self):<br>
&#9;&#9;# QOpenGLWidget сам делает makeCurrent() прямо перед paintGL<br>
&#9;&#9;# но движок может вызвать это — тогда просто делегируем<br>
&#9;&#9;self._widget.makeCurrent()<br>
<br>
&#9;def swap_buffers(self):<br>
&#9;&#9;# QOpenGLWidget сам вызывает swapBuffers<br>
&#9;&#9;pass<br>
<br>
&#9;def framebuffer_size(self):<br>
&#9;&#9;ratio = self._widget.devicePixelRatioF()<br>
&#9;&#9;return int(self._widget.width() * ratio), int(self._widget.height() * ratio)<br>
<br>
&#9;def window_size(self):<br>
&#9;&#9;return self._widget.width(), self._widget.height()<br>
<br>
&#9;def get_cursor_pos(self):<br>
&#9;&#9;pos = self._widget.mapFromGlobal(QtGui.QCursor.pos())<br>
&#9;&#9;return float(pos.x()), float(pos.y())<br>
<br>
&#9;def set_should_close(self, flag: bool):<br>
&#9;&#9;if flag:<br>
&#9;&#9;&#9;self.close()<br>
<br>
&#9;def set_user_pointer(self, ptr):<br>
&#9;&#9;self._user_ptr = ptr<br>
<br>
&#9;# --- callback setters -----------------------------------------------<br>
<br>
&#9;def set_framebuffer_size_callback(self, cb):<br>
&#9;&#9;self._framebuffer_callback = cb<br>
<br>
&#9;def set_cursor_pos_callback(self, cb):<br>
&#9;&#9;self._cursor_callback = cb<br>
<br>
&#9;def set_scroll_callback(self, cb):<br>
&#9;&#9;self._scroll_callback = cb<br>
<br>
&#9;def set_mouse_button_callback(self, cb):<br>
&#9;&#9;self._mouse_callback = cb<br>
<br>
&#9;def set_key_callback(self, cb):<br>
&#9;&#9;self._key_callback = cb<br>
<br>
&#9;# --- Чтобы движок понимал push-модель Qt ----------------------------<br>
<br>
&#9;def drives_render(self) -&gt; bool:<br>
&#9;&#9;return True<br>
<br>
&#9;@property<br>
&#9;def widget(self):<br>
&#9;&#9;return self._widget<br>
<br>
<br>
&#9;def request_update(self):<br>
&#9;&#9;# Просим Qt перерисовать виджет (это вызовет paintGL)<br>
&#9;&#9;self._widget.update()<br>
<br>
&#9;<br>
&#9;def bind_window_framebuffer(self):        <br>
&#9;&#9;fbo_id = int(self._widget.defaultFramebufferObject())<br>
&#9;&#9;gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo_id)<br>
<br>
<br>
<br>
<br>
class QtWindowBackend(WindowBackend):<br>
&#9;&quot;&quot;&quot;Window backend, использующий QOpenGLWindow и Qt event loop.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, app: Optional[QtWidgets.QApplication] = None):<br>
&#9;&#9;self.app = app or _qt_app()<br>
<br>
&#9;def create_window(<br>
&#9;&#9;self,<br>
&#9;&#9;width: int,<br>
&#9;&#9;height: int,<br>
&#9;&#9;title: str,<br>
&#9;&#9;share: Optional[BackendWindow] = None,<br>
&#9;&#9;parent: Optional[QtWidgets.QWidget] = None,<br>
&#9;) -&gt; QtGLWindowHandle:<br>
&#9;&#9;return QtGLWindowHandle(width, height, title, share=share, parent=parent)<br>
<br>
&#9;def poll_events(self):<br>
&#9;&#9;# Обрабатываем накопившиеся Qt-события<br>
&#9;&#9;self.app.processEvents()<br>
<br>
&#9;def terminate(self):<br>
&#9;&#9;self.app.quit()<br>
<!-- END SCAT CODE -->
</body>
</html>
