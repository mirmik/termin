"""PyQt6-based window backend using QOpenGLWidget."""

from __future__ import annotations

from typing import Callable, Optional, Any

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

from tcbase import Action, Key, MouseButton
from tgfx.window import BackendWindow, WindowBackend

from termin.graphics import OpenGLGraphicsBackend


class _TcSurfaceWrapper:
    """Wrapper with .ptr attribute for C interop (same as sdl_embedded.py)."""

    def __init__(self, ptr: int):
        self.ptr = ptr



def _qt_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        # Enable shared GL contexts so VBOs/textures/shaders are shared
        # between QOpenGLWidgets (VAOs are still per-context)
        QtWidgets.QApplication.setAttribute(
            QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts
        )
        app = QtWidgets.QApplication([])
    return app


def _translate_mouse(button: QtCore.Qt.MouseButton) -> MouseButton:
    if button == QtCore.Qt.MouseButton.LeftButton:
        return MouseButton.LEFT
    if button == QtCore.Qt.MouseButton.RightButton:
        return MouseButton.RIGHT
    if button == QtCore.Qt.MouseButton.MiddleButton:
        return MouseButton.MIDDLE
    return MouseButton.LEFT


def _translate_action(action: bool) -> Action:
    return Action.PRESS if action else Action.RELEASE


def _translate_key(key: int) -> Key:
    if key == QtCore.Qt.Key.Key_Escape:
        return Key.ESCAPE
    if key == QtCore.Qt.Key.Key_Space:
        return Key.SPACE
    try:
        return Key(key)
    except ValueError:
        return Key.UNKNOWN


def _translate_qt_mods(qt_mods: int) -> int:
    """Translate Qt modifier flags to GLFW-compatible flags."""
    # Qt: ShiftModifier=0x02000000, ControlModifier=0x04000000, AltModifier=0x08000000
    # GLFW: SHIFT=0x0001, CTRL=0x0002, ALT=0x0004, SUPER=0x0008
    result = 0
    if qt_mods & 0x02000000:  # ShiftModifier
        result |= 0x0001  # MOD_SHIFT
    if qt_mods & 0x04000000:  # ControlModifier
        result |= 0x0002  # MOD_CONTROL
    if qt_mods & 0x08000000:  # AltModifier
        result |= 0x0004  # MOD_ALT
    return result


class _QtGLWidget(QOpenGLWidget):
    def __init__(self, owner: "QtGLWindowHandle", parent=None, vsync: bool = True):
        super().__init__(parent)
        self._owner = owner
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.PartialUpdate)
        self.setMouseTracking(True)

        # Configure swap interval (vsync)
        fmt = QtGui.QSurfaceFormat()
        fmt.setSwapInterval(1 if vsync else 0)
        self.setFormat(fmt)

    # --- События мыши / клавиатуры --------------------------------------

    def mousePressEvent(self, event):
        cb = self._owner._mouse_callback
        if cb:
            cb(self._owner, _translate_mouse(event.button()), Action.PRESS, event.modifiers().value)

    def mouseReleaseEvent(self, event):
        cb = self._owner._mouse_callback
        if cb:
            cb(self._owner, _translate_mouse(event.button()), Action.RELEASE, event.modifiers().value)

    def mouseMoveEvent(self, event):
        cb = self._owner._cursor_callback
        if cb:
            pos = event.position()
            cb(self._owner, float(pos.x()), float(pos.y()))

    def wheelEvent(self, event):
        angle = event.angleDelta()
        cb = self._owner._scroll_callback
        if cb:
            mods = _translate_qt_mods(event.modifiers().value)
            cb(self._owner, angle.x() / 120.0, angle.y() / 120.0, mods)

    def keyPressEvent(self, event):
        cb = self._owner._key_callback
        if cb:
            cb(self._owner, _translate_key(event.key()), event.nativeScanCode(), Action.PRESS, event.modifiers().value)

    def keyReleaseEvent(self, event):
        cb = self._owner._key_callback
        if cb:
            cb(self._owner, _translate_key(event.key()), event.nativeScanCode(), Action.RELEASE, event.modifiers().value)

    # --- Рендер ----------------------------------------------------------

    def paintGL(self):
        # Тут есть активный GL-контекст — выполняем рендер движка
        window_obj = self._owner._user_ptr
        if window_obj is not None:
            window_obj.render(from_backend=True)

    def resizeGL(self, w, h):
        cb = self._owner._framebuffer_callback
        if cb:
            cb(self._owner, w, h)


class QtGLWindowHandle(BackendWindow):
    def __init__(
        self,
        width: int,
        height: int,
        title: str,
        share=None,
        parent=None,
        graphics: Optional[OpenGLGraphicsBackend] = None,
        vsync: bool = False,
    ):
        self.app = _qt_app()

        self._closed = False
        self._user_ptr = None
        self._graphics = graphics
        self._window_fb_handle = None
        self._tc_surface_ptr: int = 0

        # Callbacks (must be set before widget creation — Qt calls resizeGL during init)
        self._framebuffer_callback = None
        self._cursor_callback = None
        self._scroll_callback = None
        self._mouse_callback = None
        self._key_callback = None

        self._widget = _QtGLWidget(self, parent=parent, vsync=vsync)
        self._widget.setMinimumSize(50, 50)
        self._widget.resize(width, height)
        self._widget.show()

    # --- BackendWindow API ----------------------------------------------

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._tc_surface_ptr:
            from termin._native.render import _render_surface_free_external
            _render_surface_free_external(self._tc_surface_ptr)
            self._tc_surface_ptr = 0
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
        # Ask Qt to repaint the widget (this will call paintGL)
        self._widget.update()

    def get_window_framebuffer(self):
        fbo_id = int(self._widget.defaultFramebufferObject())
        width, height = self.framebuffer_size()

        if self._window_fb_handle is None and self._graphics is not None:
            self._window_fb_handle = self._graphics.create_external_framebuffer(fbo_id, width, height)
        elif self._window_fb_handle is not None:
            self._window_fb_handle.set_external_target(fbo_id, width, height)

        return self._window_fb_handle

    def get_framebuffer_id(self) -> int:
        """Return raw OpenGL FBO id (for C++ vtable dispatch)."""
        return int(self._widget.defaultFramebufferObject())

    def get_framebuffer(self):
        """Return FramebufferHandle for rendering (used by Python render path)."""
        return self.get_window_framebuffer()

    def tc_surface(self) -> _TcSurfaceWrapper:
        """Create/return tc_render_surface wrapping this handle."""
        if not self._tc_surface_ptr:
            from termin._native.render import _render_surface_new_from_python
            self._tc_surface_ptr = _render_surface_new_from_python(self)
        return _TcSurfaceWrapper(self._tc_surface_ptr)

    def share_group_key(self) -> int:
        """All Qt widgets share GL resources via AA_ShareOpenGLContexts."""
        return 1

    def set_graphics(self, graphics: OpenGLGraphicsBackend) -> None:
        """Set graphics backend for framebuffer creation."""
        self._graphics = graphics




class QtWindowBackend(WindowBackend):
    """Window backend using QOpenGLWidget and Qt event loop."""

    def __init__(
        self,
        app: Optional[QtWidgets.QApplication] = None,
        graphics: Optional[OpenGLGraphicsBackend] = None,
        vsync: bool = False,
    ):
        self.app = app or _qt_app()
        self._graphics = graphics
        self._vsync = vsync

    def set_graphics(self, graphics: OpenGLGraphicsBackend) -> None:
        """Set graphics backend for new windows."""
        self._graphics = graphics

    def create_window(
        self,
        width: int,
        height: int,
        title: str,
        share: Optional[BackendWindow] = None,
        parent: Optional[QtWidgets.QWidget] = None,
        vsync: Optional[bool] = None,
    ) -> QtGLWindowHandle:
        return QtGLWindowHandle(
            width, height, title,
            share=share,
            parent=parent,
            graphics=self._graphics,
            vsync=vsync if vsync is not None else self._vsync,
        )

    def poll_events(self):
        self.app.processEvents()

    def terminate(self):
        self.app.quit()
