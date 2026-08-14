"""Toolkit-neutral SpaceMouse settings projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .spacemouse_controller import SpaceMouseController


@dataclass(frozen=True)
class SpaceMouseSettingsSnapshot:
    fly_mode: bool
    horizon_lock: bool
    pan_sensitivity: float
    zoom_sensitivity: float
    orbit_sensitivity: float
    fly_sensitivity: float
    deadzone: int
    invert_x: bool
    invert_y: bool
    invert_z: bool
    invert_rx: bool
    invert_ry: bool
    invert_rz: bool


class SpaceMouseSettingsController:
    def __init__(
        self,
        spacemouse: SpaceMouseController,
        *,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        self._spacemouse = spacemouse
        self._on_changed = on_changed

    def load(self) -> SpaceMouseSettingsSnapshot:
        value = self._spacemouse
        return SpaceMouseSettingsSnapshot(
            value.fly_mode,
            value.horizon_lock,
            value.pan_sensitivity,
            value.zoom_sensitivity,
            value.orbit_sensitivity,
            value.fly_sensitivity,
            value.deadzone,
            value.invert_x,
            value.invert_y,
            value.invert_z,
            value.invert_rx,
            value.invert_ry,
            value.invert_rz,
        )

    def apply(self, snapshot: SpaceMouseSettingsSnapshot) -> SpaceMouseSettingsSnapshot:
        value = self.validate(snapshot)
        spacemouse = self._spacemouse
        spacemouse.fly_mode = value.fly_mode
        spacemouse.horizon_lock = value.horizon_lock
        spacemouse.pan_sensitivity = value.pan_sensitivity
        spacemouse.zoom_sensitivity = value.zoom_sensitivity
        spacemouse.orbit_sensitivity = value.orbit_sensitivity
        spacemouse.fly_sensitivity = value.fly_sensitivity
        spacemouse.deadzone = value.deadzone
        spacemouse.invert_x = value.invert_x
        spacemouse.invert_y = value.invert_y
        spacemouse.invert_z = value.invert_z
        spacemouse.invert_rx = value.invert_rx
        spacemouse.invert_ry = value.invert_ry
        spacemouse.invert_rz = value.invert_rz
        if self._on_changed is not None:
            self._on_changed()
        return self.load()

    @staticmethod
    def validate(snapshot: SpaceMouseSettingsSnapshot) -> SpaceMouseSettingsSnapshot:
        ranges = (
            ("pan sensitivity", snapshot.pan_sensitivity, 0.000001, 0.01),
            ("zoom sensitivity", snapshot.zoom_sensitivity, 0.000001, 0.01),
            ("orbit sensitivity", snapshot.orbit_sensitivity, 0.0001, 0.1),
            ("fly sensitivity", snapshot.fly_sensitivity, 0.000001, 0.01),
        )
        for label, value, minimum, maximum in ranges:
            if not minimum <= float(value) <= maximum:
                raise ValueError(f"SpaceMouse {label} must be in range {minimum}..{maximum}")
        if not 0 <= int(snapshot.deadzone) <= 100:
            raise ValueError("SpaceMouse deadzone must be in range 0..100")
        return SpaceMouseSettingsSnapshot(
            bool(snapshot.fly_mode),
            bool(snapshot.horizon_lock),
            float(snapshot.pan_sensitivity),
            float(snapshot.zoom_sensitivity),
            float(snapshot.orbit_sensitivity),
            float(snapshot.fly_sensitivity),
            int(snapshot.deadzone),
            bool(snapshot.invert_x),
            bool(snapshot.invert_y),
            bool(snapshot.invert_z),
            bool(snapshot.invert_rx),
            bool(snapshot.invert_ry),
            bool(snapshot.invert_rz),
        )


__all__ = ["SpaceMouseSettingsController", "SpaceMouseSettingsSnapshot"]
