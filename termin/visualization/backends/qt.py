"""PyQt5-based window backend using QOpenGLWindow."""

from __future__ import annotations

from typing import Callable, Optional, Any

from PyQt5 import QtCore, QtGui, QtWidgets

from .base import Action, BackendWindow, Key, MouseButton, WindowBackend

from OpenGL import GL
from OpenGL import GL as gl



def _qt_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _translate_mouse(button: QtCore.Qt.MouseButton) -> MouseButton:
    if button == QtCore.Qt.LeftButton:
        return MouseButton.LEFT
    if button == QtCore.Qt.RightButton:
        return MouseButton.RIGHT
    if button == QtCore.Qt.MiddleButton:
        return MouseButton.MIDDLE
    return MouseButton.LEFT


def _translate_action(action: bool) -> Action:
    return Action.PRESS if action else Action.RELEASE


def _translate_key(key: int) -> Key:
    if key == QtCore.Qt.Key_Escape:
        return Key.ESCAPE
    if key == QtCore.Qt.Key_Space:
        return Key.SPACE
    try:
        return Key(key)
    except ValueError:
        return Key.UNKNOWN


class _QtGLWidget(QtWidgets.QOpenGLWidget):
    def __init__(self, owner: "QtGLWindowHandle", parent=None):
        super().__init__(parent)
        self._owner = owner
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setUpdateBehavior(QtWidgets.QOpenGLWidget.PartialUpdate)
        self.setMouseTracking(True)

    # --- События мыши / клавиатуры --------------------------------------

    def mousePressEvent(self, event):
        cb = self._owner._mouse_callback
        if cb:
            cb(self._owner, _translate_mouse(event.button()), Action.PRESS, int(event.modifiers()))

    def mouseReleaseEvent(self, event):
        cb = self._owner._mouse_callback
        if cb:
            cb(self._owner, _translate_mouse(event.button()), Action.RELEASE, int(event.modifiers()))

    def mouseMoveEvent(self, event):
        cb = self._owner._cursor_callback
        if cb:
            cb(self._owner, float(event.x()), float(event.y()))

    def wheelEvent(self, event):
        angle = event.angleDelta()
        cb = self._owner._scroll_callback
        if cb:
            cb(self._owner, angle.x() / 120.0, angle.y() / 120.0)

    def keyPressEvent(self, event):
        cb = self._owner._key_callback
        if cb:
            cb(self._owner, _translate_key(event.key()), event.nativeScanCode(), Action.PRESS, int(event.modifiers()))

    def keyReleaseEvent(self, event):
        cb = self._owner._key_callback
        if cb:
            cb(self._owner, _translate_key(event.key()), event.nativeScanCode(), Action.RELEASE, int(event.modifiers()))

    # --- Рендер ----------------------------------------------------------

    def paintGL(self):
        # Тут есть активный GL-контекст — выполняем рендер движка
        window_obj = self._owner._user_ptr
        if window_obj is not None:
            window_obj._render_core(from_backend=True)

    def resizeGL(self, w, h):
        cb = self._owner._framebuffer_callback
        if cb:
            cb(self._owner, w, h)


class QtGLWindowHandle(BackendWindow):
    def __init__(self, width, height, title, share=None, parent=None):
        self.app = _qt_app()

        self._widget = _QtGLWidget(self, parent=parent)
        self._widget.setMinimumSize(50, 50)
        self._widget.resize(width, height)
        self._widget.show()

        self._closed = False
        self._user_ptr = None

        # Все callback-и окна (их вызывает Window)
        self._framebuffer_callback = None
        self._cursor_callback = None
        self._scroll_callback = None
        self._mouse_callback = None
        self._key_callback = None

    # --- BackendWindow API ----------------------------------------------

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._widget.close()

    def should_close(self) -> bool:
        return self._closed or not self._widget.isVisible()

    def make_current(self):
        # QOpenGLWidget сам делает makeCurrent() прямо перед paintGL
        # но движок может вызвать это — тогда просто делегируем
        self._widget.makeCurrent()

    def swap_buffers(self):
        # QOpenGLWidget сам вызывает swapBuffers
        pass

    def framebuffer_size(self):
        ratio = self._widget.devicePixelRatioF()
        return int(self._widget.width() * ratio), int(self._widget.height() * ratio)

    def window_size(self):
        return self._widget.width(), self._widget.height()

    def get_cursor_pos(self):
        pos = self._widget.mapFromGlobal(QtGui.QCursor.pos())
        return float(pos.x()), float(pos.y())

    def set_should_close(self, flag: bool):
        if flag:
            self.close()

    def set_user_pointer(self, ptr):
        self._user_ptr = ptr

    # --- callback setters -----------------------------------------------

    def set_framebuffer_size_callback(self, cb):
        self._framebuffer_callback = cb

    def set_cursor_pos_callback(self, cb):
        self._cursor_callback = cb

    def set_scroll_callback(self, cb):
        self._scroll_callback = cb

    def set_mouse_button_callback(self, cb):
        self._mouse_callback = cb

    def set_key_callback(self, cb):
        self._key_callback = cb

    # --- Чтобы движок понимал push-модель Qt ----------------------------

    def drives_render(self) -> bool:
        return True

    @property
    def widget(self):
        return self._widget


    def request_update(self):
        # Просим Qt перерисовать виджет (это вызовет paintGL)
        self._widget.update()

    
    def bind_window_framebuffer(self):        
        fbo_id = int(self._widget.defaultFramebufferObject())
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo_id)




class QtWindowBackend(WindowBackend):
    """Window backend, использующий QOpenGLWindow и Qt event loop."""

    def __init__(self, app: Optional[QtWidgets.QApplication] = None):
        self.app = app or _qt_app()

    def create_window(
        self,
        width: int,
        height: int,
        title: str,
        share: Optional[BackendWindow] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> QtGLWindowHandle:
        return QtGLWindowHandle(width, height, title, share=share, parent=parent)

    def poll_events(self):
        # Обрабатываем накопившиеся Qt-события
        self.app.processEvents()

    def terminate(self):
        self.app.quit()
