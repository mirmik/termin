"""
SpaceMouseController — 3DConnexion SpaceMouse support via libspnav.

Uses spacenavd daemon + libspnav (ctypes) for 6DOF input.
QSocketNotifier on spnav_fd() for event-driven processing.

Install: sudo apt install spacenavd libspnav-dev
"""

from __future__ import annotations

import ctypes
import ctypes.util
from typing import TYPE_CHECKING, Callable

from termin._native import log

if TYPE_CHECKING:
    from termin.visualization.core.camera import OrbitCameraController

# --- libspnav ctypes bindings ---

SPNAV_EVENT_MOTION = 1
SPNAV_EVENT_BUTTON = 2


class _SpnavEventMotion(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("z", ctypes.c_int),
        ("rx", ctypes.c_int),
        ("ry", ctypes.c_int),
        ("rz", ctypes.c_int),
        ("period", ctypes.c_uint),
        ("data", ctypes.c_void_p),
    ]


class _SpnavEventButton(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("press", ctypes.c_int),
        ("bnum", ctypes.c_int),
    ]


class _SpnavEvent(ctypes.Union):
    _fields_ = [
        ("type", ctypes.c_int),
        ("motion", _SpnavEventMotion),
        ("button", _SpnavEventButton),
    ]


def _load_libspnav():
    """Try to load libspnav shared library."""
    lib_path = ctypes.util.find_library("spnav")
    if lib_path is None:
        return None

    try:
        lib = ctypes.CDLL(lib_path)
    except OSError as e:
        log.error(f"[SpaceMouse] Failed to load {lib_path}: {e}")
        return None

    lib.spnav_open.restype = ctypes.c_int
    lib.spnav_open.argtypes = []

    lib.spnav_close.restype = ctypes.c_int
    lib.spnav_close.argtypes = []

    lib.spnav_fd.restype = ctypes.c_int
    lib.spnav_fd.argtypes = []

    lib.spnav_poll_event.restype = ctypes.c_int
    lib.spnav_poll_event.argtypes = [ctypes.POINTER(_SpnavEvent)]

    lib.spnav_sensitivity.restype = ctypes.c_int
    lib.spnav_sensitivity.argtypes = [ctypes.c_double]

    return lib


_libspnav = _load_libspnav()


class SpaceMouseController:
    """
    Controller for 3DConnexion SpaceMouse via libspnav/spacenavd.

    Supports orbit mode (default) and fly mode.
    Uses QSocketNotifier for event-driven input.
    """

    def __init__(self):
        self._is_open: bool = False
        self._editor_attachment = None
        self._request_update: Callable[[], None] | None = None
        self._notifier = None  # QSocketNotifier

        # Mode
        self.fly_mode: bool = True

        # Sensitivity (libspnav values are integers, typical range ±350)
        self.pan_sensitivity: float = 0.00002
        self.zoom_sensitivity: float = 0.00005
        self.orbit_sensitivity: float = 0.002
        self.fly_sensitivity: float = 0.0001

        # Deadzone (integer threshold)
        self.deadzone: int = 15

        # Axis inversion (6 physical axes)
        self.invert_x: bool = False   # Left/Right
        self.invert_y: bool = False   # Forward/Backward
        self.invert_z: bool = False   # Up/Down
        self.invert_rx: bool = False  # Pitch
        self.invert_ry: bool = False  # Yaw
        self.invert_rz: bool = False  # Roll

    def open(
        self,
        editor_attachment,
        request_update: Callable[[], None],
    ) -> bool:
        """
        Open SpaceMouse device via spacenavd.

        Args:
            editor_attachment: EditorSceneAttachment to get orbit controller from.
            request_update: Callback to request viewport redraw.

        Returns:
            True if device opened successfully.
        """
        if self._is_open:
            return True

        if _libspnav is None:
            return False

        if _libspnav.spnav_open() == -1:
            log.warn("[SpaceMouse] Failed to connect to spacenavd")
            return False

        self._editor_attachment = editor_attachment
        self._request_update = request_update
        self._is_open = True

        fd = _libspnav.spnav_fd()
        if fd >= 0:
            from PyQt6.QtCore import QSocketNotifier
            self._notifier = QSocketNotifier(fd, QSocketNotifier.Type.Read)
            self._notifier.activated.connect(self._on_data_ready)
        else:
            log.error(f"[SpaceMouse] spnav_fd() returned invalid fd={fd}")

        return True

    def close(self) -> None:
        """Close SpaceMouse device."""
        if not self._is_open:
            return

        if self._notifier is not None:
            self._notifier.setEnabled(False)
            self._notifier = None

        if _libspnav is not None:
            _libspnav.spnav_close()

        self._is_open = False
        self._editor_attachment = None
        self._request_update = None

    @property
    def is_open(self) -> bool:
        return self._is_open

    @property
    def horizon_lock(self) -> bool:
        ctrl = self._get_orbit_controller()
        return ctrl.horizon_lock if ctrl is not None else True

    @horizon_lock.setter
    def horizon_lock(self, value: bool) -> None:
        ctrl = self._get_orbit_controller()
        if ctrl is not None:
            ctrl.horizon_lock = value

    def _on_data_ready(self, _socket=None) -> None:
        """Called by QSocketNotifier when spacenavd has data."""
        if _libspnav is None or not self._is_open:
            return

        event = _SpnavEvent()
        moved = False

        while _libspnav.spnav_poll_event(ctypes.byref(event)) != 0:
            if event.type == SPNAV_EVENT_MOTION:
                if self._handle_motion(event.motion):
                    moved = True
            elif event.type == SPNAV_EVENT_BUTTON:
                self._handle_button(event.button)

        if moved and self._request_update is not None:
            self._request_update()

    def _apply_deadzone(self, value: int) -> float:
        """Apply deadzone and return float."""
        if abs(value) < self.deadzone:
            return 0.0
        return float(value)

    def _get_orbit_controller(self):
        """Get current orbit controller from editor attachment."""
        if self._editor_attachment is None:
            return None
        cm = self._editor_attachment._camera_manager
        if cm is None:
            return None
        return cm.orbit_controller

    def _handle_motion(self, m: _SpnavEventMotion) -> bool:
        """Map 6DOF motion to camera controls. Returns True if camera moved."""
        ctrl = self._get_orbit_controller()
        if ctrl is None:
            return False

        tx = self._apply_deadzone(m.x)
        ty = self._apply_deadzone(m.y)
        tz = self._apply_deadzone(m.z)
        rx = self._apply_deadzone(m.rx)
        ry = self._apply_deadzone(m.ry)
        rz = self._apply_deadzone(m.rz)

        if tx == ty == tz == rx == ry == rz == 0.0:
            return False

        moved = False
        r = ctrl.radius

        if self.fly_mode:
            # Fly: direct camera movement along local axes
            # X → strafe, Y → up/down, Z → forward/back
            right = tx * self.pan_sensitivity * r
            up = ty * self.pan_sensitivity * r
            forward = tz * self.fly_sensitivity * r

            # Apply inversion on camera directions
            if self.invert_x:
                right = -right
            if self.invert_y:
                forward = -forward
            if self.invert_z:
                up = -up
            if right != 0.0 or forward != 0.0 or up != 0.0:
                ctrl.fly_move(right, forward, up)
                moved = True

            # Rotation: rx → pitch, ry → yaw, rz → roll
            pitch = rx * self.orbit_sensitivity
            yaw = ry * self.orbit_sensitivity
            roll = rz * self.orbit_sensitivity

            # Apply inversion on camera rotations
            if self.invert_rx:
                pitch = -pitch
            if self.invert_ry:
                yaw = -yaw
            if self.invert_rz:
                roll = -roll

            if yaw != 0.0 or pitch != 0.0 or roll != 0.0:
                ctrl.fly_rotate(yaw, pitch, roll)
                moved = True
        else:
            # Orbit: X → pan horizontal, Y → pan vertical, Z → zoom
            pan_x = tx * self.pan_sensitivity * r
            pan_y = -ty * self.pan_sensitivity * r
            zoom_val = -tz * self.zoom_sensitivity * r

            # Apply inversion on camera directions
            if self.invert_x:
                pan_x = -pan_x
            if self.invert_z:
                pan_y = -pan_y
            if self.invert_y:
                zoom_val = -zoom_val

            if pan_x != 0.0 or pan_y != 0.0:
                ctrl.pan(-pan_x, pan_y)
                moved = True

            if zoom_val != 0.0:
                ctrl.zoom(zoom_val)
                moved = True

            # Orbit rotation: rx → elevation (pitch), ry → azimuth (yaw)
            orbit_yaw = -ry * self.orbit_sensitivity
            orbit_pitch = -rx * self.orbit_sensitivity
            if self.invert_rx:
                orbit_pitch = -orbit_pitch
            if self.invert_ry:
                orbit_yaw = -orbit_yaw
            if orbit_yaw != 0.0 or orbit_pitch != 0.0:
                ctrl.orbit(orbit_yaw, orbit_pitch)
                moved = True

        return moved

    def _handle_button(self, b: _SpnavEventButton) -> None:
        """Handle button press/release."""
        if not b.press:
            return

        # Button 0: toggle fly/orbit mode
        if b.bnum == 0:
            self.fly_mode = not self.fly_mode
            mode = "Fly" if self.fly_mode else "Orbit"
            log.warn(f"[SpaceMouse] Mode: {mode}")
