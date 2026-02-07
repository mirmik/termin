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
        log.warn("[SpaceMouse] ctypes.util.find_library('spnav') returned None")
        return None

    log.warn(f"[SpaceMouse] Found libspnav at: {lib_path}")

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

    Uses QSocketNotifier for event-driven input — no polling needed.
    """

    def __init__(self):
        self._is_open: bool = False
        self._editor_attachment = None  # EditorSceneAttachment — always get fresh orbit_controller
        self._request_update: Callable[[], None] | None = None
        self._notifier = None  # QSocketNotifier

        # Sensitivity (libspnav values are integers, typical range ±350)
        self.pan_sensitivity: float = 0.00002
        self.zoom_sensitivity: float = 0.00005
        self.orbit_sensitivity: float = 0.002

        # Deadzone (integer threshold)
        self.deadzone: int = 15

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
            log.warn("[SpaceMouse] libspnav not loaded, cannot open")
            return False

        ret = _libspnav.spnav_open()
        log.warn(f"[SpaceMouse] spnav_open() returned {ret}")
        if ret == -1:
            log.warn("[SpaceMouse] Failed to connect to spacenavd (systemctl start spacenavd)")
            return False

        self._editor_attachment = editor_attachment
        self._request_update = request_update
        self._is_open = True

        # Set up QSocketNotifier for event-driven input
        fd = _libspnav.spnav_fd()
        log.warn(f"[SpaceMouse] spnav_fd() returned {fd}")

        if fd >= 0:
            from PyQt6.QtCore import QSocketNotifier
            self._notifier = QSocketNotifier(fd, QSocketNotifier.Type.Read)
            self._notifier.activated.connect(self._on_data_ready)
            log.warn(f"[SpaceMouse] QSocketNotifier created for fd={fd}, enabled={self._notifier.isEnabled()}")
        else:
            log.error(f"[SpaceMouse] spnav_fd() returned invalid fd={fd}")

        log.warn("[SpaceMouse] Device connected")
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

    def _on_data_ready(self, _socket=None) -> None:
        """Called by QSocketNotifier when spacenavd has data."""
        log.warn("[SpaceMouse] _on_data_ready called")

        if _libspnav is None or not self._is_open:
            log.warn("[SpaceMouse] _on_data_ready: not ready (lib=%s, open=%s)" % (_libspnav is not None, self._is_open))
            return

        event = _SpnavEvent()
        moved = False
        event_count = 0

        # Drain all pending events
        while _libspnav.spnav_poll_event(ctypes.byref(event)) != 0:
            event_count += 1
            if event.type == SPNAV_EVENT_MOTION:
                m = event.motion
                log.warn(f"[SpaceMouse] MOTION x={m.x} y={m.y} z={m.z} rx={m.rx} ry={m.ry} rz={m.rz}")
                if self._handle_motion(m):
                    moved = True
            elif event.type == SPNAV_EVENT_BUTTON:
                self._handle_button(event.button)
            else:
                log.warn(f"[SpaceMouse] Unknown event type: {event.type}")

        if event_count == 0:
            log.warn("[SpaceMouse] _on_data_ready: no events from spnav_poll_event")

        if moved and self._request_update is not None:
            self._request_update()

    def _apply_deadzone(self, value: int) -> float:
        """Apply deadzone and return normalized float."""
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
            log.warn("[SpaceMouse] _handle_motion: no orbit controller")
            return False

        tx = self._apply_deadzone(m.x)
        ty = self._apply_deadzone(m.y)
        tz = self._apply_deadzone(m.z)
        ry = self._apply_deadzone(m.ry)
        rz = self._apply_deadzone(m.rz)

        if tx == ty == tz == ry == rz == 0.0:
            return False

        old_az = ctrl.azimuth
        old_el = ctrl.elevation

        moved = False

        # Pan: X → horizontal, Z → vertical
        if tx != 0.0 or tz != 0.0:
            pan_x = tx * self.pan_sensitivity * ctrl.radius
            pan_y = tz * self.pan_sensitivity * ctrl.radius
            ctrl.pan(-pan_x, pan_y)
            moved = True

        # Zoom: Y → push/pull
        if ty != 0.0:
            zoom_delta = ty * self.zoom_sensitivity * ctrl.radius
            ctrl.zoom(-zoom_delta)
            moved = True

        # Orbit: RY → azimuth, RZ → elevation
        if rz != 0.0 or ry != 0.0:
            ctrl.orbit(-ry * self.orbit_sensitivity, -rz * self.orbit_sensitivity)
            moved = True

        if moved:
            ctrl._update_pose()
            # Check entity transform to see if _update_pose() actually worked
            cm = self._editor_attachment._camera_manager if self._editor_attachment else None
            cam = cm.camera if cm else None
            if cam is not None and cam.entity is not None:
                pos = cam.entity.transform.global_position
                log.warn(
                    f"[SpaceMouse] az={old_az:.4f}->{ctrl.azimuth:.4f} r={ctrl.radius:.2f} "
                    f"entity_pos=({pos.x:.3f},{pos.y:.3f},{pos.z:.3f}) ptr={ctrl.c_component_ptr()}"
                )
            else:
                log.warn("[SpaceMouse] camera or entity is None!")

        return moved

    def _handle_button(self, b: _SpnavEventButton) -> None:
        """Handle button press/release."""
        action = "pressed" if b.press else "released"
        log.warn(f"[SpaceMouse] Button {b.bnum} {action}")
