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
    app = QtWidgets.QApplication.instance()<br>
    if app is None:<br>
        app = QtWidgets.QApplication([])<br>
    return app<br>
<br>
<br>
def _translate_mouse(button: QtCore.Qt.MouseButton) -&gt; MouseButton:<br>
    if button == QtCore.Qt.LeftButton:<br>
        return MouseButton.LEFT<br>
    if button == QtCore.Qt.RightButton:<br>
        return MouseButton.RIGHT<br>
    if button == QtCore.Qt.MiddleButton:<br>
        return MouseButton.MIDDLE<br>
    return MouseButton.LEFT<br>
<br>
<br>
def _translate_action(action: bool) -&gt; Action:<br>
    return Action.PRESS if action else Action.RELEASE<br>
<br>
<br>
def _translate_key(key: int) -&gt; Key:<br>
    if key == QtCore.Qt.Key_Escape:<br>
        return Key.ESCAPE<br>
    if key == QtCore.Qt.Key_Space:<br>
        return Key.SPACE<br>
    try:<br>
        return Key(key)<br>
    except ValueError:<br>
        return Key.UNKNOWN<br>
<br>
<br>
class _QtGLWidget(QtWidgets.QOpenGLWidget):<br>
    def __init__(self, owner: &quot;QtGLWindowHandle&quot;, parent=None):<br>
        super().__init__(parent)<br>
        self._owner = owner<br>
        self.setFocusPolicy(QtCore.Qt.StrongFocus)<br>
        self.setUpdateBehavior(QtWidgets.QOpenGLWidget.PartialUpdate)<br>
        self.setMouseTracking(True)<br>
<br>
    # --- События мыши / клавиатуры --------------------------------------<br>
<br>
    def mousePressEvent(self, event):<br>
        cb = self._owner._mouse_callback<br>
        if cb:<br>
            cb(self._owner, _translate_mouse(event.button()), Action.PRESS, int(event.modifiers()))<br>
<br>
    def mouseReleaseEvent(self, event):<br>
        cb = self._owner._mouse_callback<br>
        if cb:<br>
            cb(self._owner, _translate_mouse(event.button()), Action.RELEASE, int(event.modifiers()))<br>
<br>
    def mouseMoveEvent(self, event):<br>
        cb = self._owner._cursor_callback<br>
        if cb:<br>
            cb(self._owner, float(event.x()), float(event.y()))<br>
<br>
    def wheelEvent(self, event):<br>
        angle = event.angleDelta()<br>
        cb = self._owner._scroll_callback<br>
        if cb:<br>
            cb(self._owner, angle.x() / 120.0, angle.y() / 120.0)<br>
<br>
    def keyPressEvent(self, event):<br>
        cb = self._owner._key_callback<br>
        if cb:<br>
            cb(self._owner, _translate_key(event.key()), event.nativeScanCode(), Action.PRESS, int(event.modifiers()))<br>
<br>
    def keyReleaseEvent(self, event):<br>
        cb = self._owner._key_callback<br>
        if cb:<br>
            cb(self._owner, _translate_key(event.key()), event.nativeScanCode(), Action.RELEASE, int(event.modifiers()))<br>
<br>
    # --- Рендер ----------------------------------------------------------<br>
<br>
    def paintGL(self):<br>
        # Тут есть активный GL-контекст — выполняем рендер движка<br>
        window_obj = self._owner._user_ptr<br>
        if window_obj is not None:<br>
            window_obj._render_core(from_backend=True)<br>
<br>
    def resizeGL(self, w, h):<br>
        cb = self._owner._framebuffer_callback<br>
        if cb:<br>
            cb(self._owner, w, h)<br>
<br>
<br>
class QtGLWindowHandle(BackendWindow):<br>
    def __init__(self, width, height, title, share=None, parent=None):<br>
        self.app = _qt_app()<br>
<br>
        self._widget = _QtGLWidget(self, parent=parent)<br>
        self._widget.setMinimumSize(50, 50)<br>
        self._widget.resize(width, height)<br>
        self._widget.show()<br>
<br>
        self._closed = False<br>
        self._user_ptr = None<br>
<br>
        # Все callback-и окна (их вызывает Window)<br>
        self._framebuffer_callback = None<br>
        self._cursor_callback = None<br>
        self._scroll_callback = None<br>
        self._mouse_callback = None<br>
        self._key_callback = None<br>
<br>
    # --- BackendWindow API ----------------------------------------------<br>
<br>
    def close(self):<br>
        if self._closed:<br>
            return<br>
        self._closed = True<br>
        self._widget.close()<br>
<br>
    def should_close(self) -&gt; bool:<br>
        return self._closed or not self._widget.isVisible()<br>
<br>
    def make_current(self):<br>
        # QOpenGLWidget сам делает makeCurrent() прямо перед paintGL<br>
        # но движок может вызвать это — тогда просто делегируем<br>
        self._widget.makeCurrent()<br>
<br>
    def swap_buffers(self):<br>
        # QOpenGLWidget сам вызывает swapBuffers<br>
        pass<br>
<br>
    def framebuffer_size(self):<br>
        ratio = self._widget.devicePixelRatioF()<br>
        return int(self._widget.width() * ratio), int(self._widget.height() * ratio)<br>
<br>
    def window_size(self):<br>
        return self._widget.width(), self._widget.height()<br>
<br>
    def get_cursor_pos(self):<br>
        pos = self._widget.mapFromGlobal(QtGui.QCursor.pos())<br>
        return float(pos.x()), float(pos.y())<br>
<br>
    def set_should_close(self, flag: bool):<br>
        if flag:<br>
            self.close()<br>
<br>
    def set_user_pointer(self, ptr):<br>
        self._user_ptr = ptr<br>
<br>
    # --- callback setters -----------------------------------------------<br>
<br>
    def set_framebuffer_size_callback(self, cb):<br>
        self._framebuffer_callback = cb<br>
<br>
    def set_cursor_pos_callback(self, cb):<br>
        self._cursor_callback = cb<br>
<br>
    def set_scroll_callback(self, cb):<br>
        self._scroll_callback = cb<br>
<br>
    def set_mouse_button_callback(self, cb):<br>
        self._mouse_callback = cb<br>
<br>
    def set_key_callback(self, cb):<br>
        self._key_callback = cb<br>
<br>
    # --- Чтобы движок понимал push-модель Qt ----------------------------<br>
<br>
    def drives_render(self) -&gt; bool:<br>
        return True<br>
<br>
    @property<br>
    def widget(self):<br>
        return self._widget<br>
<br>
<br>
    def request_update(self):<br>
        # Просим Qt перерисовать виджет (это вызовет paintGL)<br>
        self._widget.update()<br>
<br>
    <br>
    def bind_window_framebuffer(self):        <br>
        fbo_id = int(self._widget.defaultFramebufferObject())<br>
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo_id)<br>
<br>
<br>
<br>
<br>
class QtWindowBackend(WindowBackend):<br>
    &quot;&quot;&quot;Window backend, использующий QOpenGLWindow и Qt event loop.&quot;&quot;&quot;<br>
<br>
    def __init__(self, app: Optional[QtWidgets.QApplication] = None):<br>
        self.app = app or _qt_app()<br>
<br>
    def create_window(<br>
        self,<br>
        width: int,<br>
        height: int,<br>
        title: str,<br>
        share: Optional[BackendWindow] = None,<br>
        parent: Optional[QtWidgets.QWidget] = None,<br>
    ) -&gt; QtGLWindowHandle:<br>
        return QtGLWindowHandle(width, height, title, share=share, parent=parent)<br>
<br>
    def poll_events(self):<br>
        # Обрабатываем накопившиеся Qt-события<br>
        self.app.processEvents()<br>
<br>
    def terminate(self):<br>
        self.app.quit()<br>
<!-- END SCAT CODE -->
</body>
</html>
