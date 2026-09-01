"""Native ``Viewport3D`` surface adapter for the standalone CSG CAD."""

from __future__ import annotations

from collections.abc import Callable

from termin.base import Action, MouseButton

from termin.csg.viewer_camera import OrbitCamera


ScenePointerCallback = Callable[[float, float, int, int], bool]


class NativeCadViewportSurface:
    """Expose a rendered CSG texture through the native viewport host protocol.

    The surface owns input state, but it deliberately does not own either the
    scene renderer or the native ``Viewport3D`` widget.  The CAD application
    renders when it is dirty and publishes the resulting texture handle here.
    """

    def __init__(self, camera: OrbitCamera) -> None:
        self.camera = camera
        self.on_changed: Callable[[], None] | None = None
        self.on_scene_mouse_down: ScenePointerCallback | None = None
        self.on_scene_mouse_move: ScenePointerCallback | None = None
        self.on_scene_mouse_up: ScenePointerCallback | None = None
        self.on_scene_click: ScenePointerCallback | None = None

        self._valid = True
        self._width = 1
        self._height = 1
        self._texture = None
        self._pointer_x = 0.0
        self._pointer_y = 0.0
        self._drag_mode = ""
        self._drag_x = 0.0
        self._drag_y = 0.0
        self._pan_gesture = None

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def publish_texture(self, texture) -> None:
        """Publish the renderer-owned texture used by the next native paint."""

        if not self._valid:
            raise RuntimeError("cannot publish a texture to a closed CSG CAD viewport surface")
        self._texture = texture

    def close(self) -> None:
        """Invalidate the host without destroying the renderer-owned texture."""

        self._valid = False
        self._texture = None
        self._drag_mode = ""
        self._pan_gesture = None

    # ViewportSurfaceHost protocol.

    def is_valid(self) -> bool:
        return self._valid

    def get_tgfx_color_tex_id(self) -> int:
        if not self._valid or self._texture is None:
            return 0
        return int(self._texture.id)

    def framebuffer_size(self) -> tuple[int, int]:
        return self._width, self._height

    def resize(self, width: int, height: int) -> bool:
        if not self._valid:
            return False
        next_size = (max(int(width), 1), max(int(height), 1))
        if next_size == (self._width, self._height):
            return True
        self._width, self._height = next_size
        # The previously published texture has different dimensions.  Do not
        # expose it between layout and the next CAD render.
        self._texture = None
        self._notify_changed()
        return True

    def dispatch_pointer_move(self, x: float, y: float) -> bool:
        if not self._valid:
            return False
        self._pointer_x = float(x)
        self._pointer_y = float(y)
        if not self._drag_mode:
            return False

        if self._drag_mode == "scene":
            callback = self.on_scene_mouse_move
            if callback is not None and callback(
                self._pointer_x,
                self._pointer_y,
                self._width,
                self._height,
            ):
                self._notify_changed()
            return True

        dx = self._pointer_x - self._drag_x
        dy = self._pointer_y - self._drag_y
        if self._drag_mode == "orbit":
            self.camera.orbit(dx, dy)
        elif self._drag_mode == "pan":
            if self._pan_gesture is None or not self.camera.pan_to(
                self._pan_gesture, self._pointer_x, self._pointer_y
            ):
                raise RuntimeError("failed to update CSG orbital camera pan")
        self._drag_x = self._pointer_x
        self._drag_y = self._pointer_y
        self._notify_changed()
        return True

    def dispatch_pointer_button(
        self,
        x: float,
        y: float,
        button: int,
        action: int,
        modifiers: int,
        click_count: int,
    ) -> bool:
        del modifiers, click_count
        if not self._valid:
            return False
        self._pointer_x = float(x)
        self._pointer_y = float(y)
        if int(action) == int(Action.PRESS):
            return self._pointer_down(int(button))
        if int(action) == int(Action.RELEASE):
            self._pointer_up()
            return True
        return False

    def dispatch_wheel(
        self,
        x: float,
        y: float,
        wheel_x: float,
        wheel_y: float,
        modifiers: int,
    ) -> bool:
        del wheel_x, modifiers
        if not self._valid:
            return False
        self._pointer_x = float(x)
        self._pointer_y = float(y)
        self.camera.zoom(float(wheel_y))
        self._notify_changed()
        return True

    def dispatch_key(self, key: int, scancode: int, action: int, modifiers: int) -> bool:
        del key, scancode, action, modifiers
        return False

    def dispatch_text(self, codepoint: int) -> bool:
        del codepoint
        return False

    def _pointer_down(self, button: int) -> bool:
        if button == int(MouseButton.LEFT):
            callback = self.on_scene_mouse_down
            if callback is not None and callback(
                self._pointer_x,
                self._pointer_y,
                self._width,
                self._height,
            ):
                self._begin_drag("scene")
                self._notify_changed()
                return True

            click_callback = self.on_scene_click
            if click_callback is not None and click_callback(
                self._pointer_x,
                self._pointer_y,
                self._width,
                self._height,
            ):
                self._notify_changed()
            return True
        if button == int(MouseButton.MIDDLE):
            self._begin_drag("orbit")
            return True
        if button == int(MouseButton.RIGHT):
            self._pan_gesture = self.camera.begin_pan(
                self._pointer_x,
                self._pointer_y,
                self._width,
                self._height,
            )
            if self._pan_gesture is None:
                return False
            self._begin_drag("pan")
            return True
        return False

    def _pointer_up(self) -> None:
        if self._drag_mode == "scene":
            callback = self.on_scene_mouse_up
            if callback is not None and callback(
                self._pointer_x,
                self._pointer_y,
                self._width,
                self._height,
            ):
                self._notify_changed()
        self._drag_mode = ""
        self._pan_gesture = None

    def _begin_drag(self, mode: str) -> None:
        self._drag_mode = mode
        self._drag_x = self._pointer_x
        self._drag_y = self._pointer_y

    def _notify_changed(self) -> None:
        callback = self.on_changed
        if callback is not None:
            callback()


__all__ = ["NativeCadViewportSurface", "ScenePointerCallback"]
