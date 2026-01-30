"""
Lighting configuration and management for Scene.

Delegates to tc_scene_lighting in C for actual storage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from termin.lighting import ShadowSettings
from termin._native.scene import TcSceneLighting

if TYPE_CHECKING:
    pass


# Add METHOD_NAMES for UI compatibility
ShadowSettings.METHOD_NAMES = ["Hard", "PCF 5x5", "Poisson"]


class LightingManager:
    """
    Manages scene lighting settings.

    Handles:
    - Ambient light (color + intensity) - stored in tc_scene
    - Shadow settings - stored in tc_scene

    Note: Light sources are now managed by LightComponent.
    The actual light collection is done in C++ (build_lights_from_scene).
    """

    tc_scene = None  # Set by Scene after creation
    _tc_lighting: TcSceneLighting | None = None

    def __init__(self):
        self._tc_lighting = None

    def _ensure_tc_lighting(self) -> TcSceneLighting | None:
        """Get or create TcSceneLighting view from tc_scene."""
        if self._tc_lighting is None and self.tc_scene is not None:
            ptr = self.tc_scene.lighting_ptr()
            if ptr:
                self._tc_lighting = TcSceneLighting(ptr)
        return self._tc_lighting

    @property
    def ambient_color(self) -> np.ndarray:
        """Ambient light color (r, g, b)."""
        lighting = self._ensure_tc_lighting()
        if lighting is not None:
            c = lighting.ambient_color
            return np.array([c[0], c[1], c[2]], dtype=np.float32)
        return np.array([1.0, 1.0, 1.0], dtype=np.float32)

    @ambient_color.setter
    def ambient_color(self, value):
        lighting = self._ensure_tc_lighting()
        if lighting is not None:
            arr = np.asarray(value, dtype=np.float32)
            lighting.ambient_color = (float(arr[0]), float(arr[1]), float(arr[2]))

    @property
    def ambient_intensity(self) -> float:
        """Ambient light intensity."""
        lighting = self._ensure_tc_lighting()
        if lighting is not None:
            return lighting.ambient_intensity
        return 0.1

    @ambient_intensity.setter
    def ambient_intensity(self, value: float):
        lighting = self._ensure_tc_lighting()
        if lighting is not None:
            lighting.ambient_intensity = float(value)

    @property
    def shadow_settings(self) -> ShadowSettings:
        """Shadow rendering settings."""
        lighting = self._ensure_tc_lighting()
        if lighting is not None:
            return lighting.shadow_settings
        return ShadowSettings()

    @shadow_settings.setter
    def shadow_settings(self, value: ShadowSettings):
        lighting = self._ensure_tc_lighting()
        if lighting is not None:
            lighting.shadow_settings = value

    def serialize(self) -> dict:
        """Serialize lighting settings."""
        ss = self.shadow_settings
        return {
            "ambient_color": list(self.ambient_color),
            "ambient_intensity": self.ambient_intensity,
            "shadow_settings": ss.serialize(),
        }

    def load_from_data(self, data: dict) -> None:
        """Load lighting settings from serialized data."""
        self.ambient_color = np.asarray(
            data.get("ambient_color", [1.0, 1.0, 1.0]),
            dtype=np.float32
        )
        self.ambient_intensity = data.get("ambient_intensity", 0.1)
        if "shadow_settings" in data:
            ss = self.shadow_settings
            ss.load_from_data(data["shadow_settings"])
            self.shadow_settings = ss

    def destroy(self) -> None:
        """Release all resources."""
        self.tc_scene = None
        self._tc_lighting = None
