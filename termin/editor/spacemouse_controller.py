"""
SpaceMouseController — support for 3DConnexion SpaceMouse devices.

Provides 6DOF input for camera navigation:
- Translation (X, Y, Z) → pan and dolly
- Rotation (roll, pitch, yaw) → orbit
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from termin._native import log

if TYPE_CHECKING:
    from termin.visualization.core.camera import OrbitCameraController


class SpaceMouseController:
    """
    Controller for 3DConnexion SpaceMouse devices.

    Reads 6DOF input and applies it to OrbitCameraController.

    Usage:
        controller = SpaceMouseController()
        if controller.open():
            # In tick loop:
            controller.update(camera_controller, request_update_callback)
    """

    def __init__(self):
        self._device_open = False
        self._pyspacemouse = None

        # Sensitivity settings
        self.pan_sensitivity = 0.001
        self.zoom_sensitivity = 0.002
        self.orbit_sensitivity = 0.5

        # Deadzone to filter noise
        self.deadzone = 0.05

        # Invert axes if needed
        self.invert_pan_x = False
        self.invert_pan_y = False
        self.invert_zoom = False
        self.invert_orbit_x = False
        self.invert_orbit_y = True  # Usually feels more natural inverted

    def open(self) -> bool:
        """
        Open SpaceMouse device.

        Returns:
            True if device opened successfully, False otherwise.
        """
        if self._device_open:
            return True

        try:
            import pyspacemouse
            self._pyspacemouse = pyspacemouse

            success = pyspacemouse.open()
            if success:
                self._device_open = True
                return True
            return False
        except ImportError:
            return False
        except Exception as e:
            log.debug(f"[SpaceMouse] Failed to open device: {e}")
            return False

    def close(self) -> None:
        """Close SpaceMouse device."""
        if self._device_open and self._pyspacemouse is not None:
            try:
                self._pyspacemouse.close()
            except Exception as e:
                log.debug(f"[SpaceMouse] Failed to close device: {e}")
            self._device_open = False

    @property
    def is_open(self) -> bool:
        """Check if device is open."""
        return self._device_open

    def _apply_deadzone(self, value: float) -> float:
        """Apply deadzone to filter small movements."""
        if abs(value) < self.deadzone:
            return 0.0
        # Scale remaining range to start from 0
        sign = 1.0 if value > 0 else -1.0
        return sign * (abs(value) - self.deadzone) / (1.0 - self.deadzone)

    def update(
        self,
        camera_controller: Optional["OrbitCameraController"],
        request_update: Optional[Callable[[], None]] = None,
    ) -> bool:
        """
        Read SpaceMouse state and apply to camera.

        Args:
            camera_controller: OrbitCameraController to manipulate.
            request_update: Callback to request viewport redraw.

        Returns:
            True if any input was applied, False otherwise.
        """
        if not self._device_open or self._pyspacemouse is None:
            return False

        if camera_controller is None:
            return False

        try:
            state = self._pyspacemouse.read()
        except Exception as e:
            log.debug(f"[SpaceMouse] Failed to read device state: {e}")
            return False

        # Apply deadzone
        tx = self._apply_deadzone(state.x)
        ty = self._apply_deadzone(state.y)
        tz = self._apply_deadzone(state.z)
        rx = self._apply_deadzone(state.roll)
        ry = self._apply_deadzone(state.pitch)
        rz = self._apply_deadzone(state.yaw)

        # Check if any significant input
        if tx == ty == tz == rx == ry == rz == 0.0:
            return False

        # Apply inversion
        if self.invert_pan_x:
            tx = -tx
        if self.invert_pan_y:
            tz = -tz
        if self.invert_zoom:
            ty = -ty
        if self.invert_orbit_x:
            rz = -rz
        if self.invert_orbit_y:
            ry = -ry

        # Map SpaceMouse axes to camera controls:
        # Translation X → pan horizontal
        # Translation Z → pan vertical (SpaceMouse Z is up/down)
        # Translation Y → zoom (push/pull)
        # Rotation yaw (rz) → orbit azimuth
        # Rotation pitch (ry) → orbit elevation

        moved = False

        # Pan (horizontal and vertical)
        if tx != 0.0 or tz != 0.0:
            pan_x = tx * self.pan_sensitivity * camera_controller.radius
            pan_y = tz * self.pan_sensitivity * camera_controller.radius
            camera_controller.pan(-pan_x, pan_y)
            moved = True

        # Zoom (push/pull on Y axis)
        if ty != 0.0:
            zoom_delta = ty * self.zoom_sensitivity * camera_controller.radius
            camera_controller.zoom(-zoom_delta)
            moved = True

        # Orbit (rotation)
        if rz != 0.0 or ry != 0.0:
            orbit_azimuth = rz * self.orbit_sensitivity
            orbit_elevation = ry * self.orbit_sensitivity
            camera_controller.orbit(orbit_azimuth, orbit_elevation)
            moved = True

        if moved and request_update is not None:
            request_update()

        return moved

    def read_buttons(self) -> list[bool]:
        """
        Read button states.

        Returns:
            List of button states (True = pressed).
        """
        if not self._device_open or self._pyspacemouse is None:
            return []

        try:
            state = self._pyspacemouse.read()
            return list(state.buttons) if hasattr(state, 'buttons') else []
        except Exception as e:
            log.debug(f"[SpaceMouse] Failed to read buttons: {e}")
            return []
