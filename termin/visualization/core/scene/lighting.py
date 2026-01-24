"""
Lighting configuration and management for Scene.

Coordinate convention: Y-forward, Z-up
  - X: right
  - Y: forward (depth)
  - Z: up

Light direction: направление из источника в сцену.
По умолчанию свет направлен в +Y (вперёд).
"""

from __future__ import annotations

from typing import List, TYPE_CHECKING

import numpy as np

from termin.lighting import ShadowSettings
from termin._native.scene import TcSceneLighting

if TYPE_CHECKING:
    from termin.lighting import Light
    from termin.visualization.render.components.light_component import LightComponent


# Add METHOD_NAMES for UI compatibility
ShadowSettings.METHOD_NAMES = ["Hard", "PCF 5x5", "Poisson"]


class LightingManager:
    """
    Manages scene lighting including directional light and ambient settings.

    Handles:
    - Global directional light (direction + color)
    - Ambient light (color + intensity) - stored in tc_scene
    - Dynamic LightComponents (queried from tc_scene)
    - Shadow settings - stored in tc_scene
    """

    tc_scene = None  # Set by Scene after creation
    _tc_lighting: TcSceneLighting | None = None
    lights: List["Light"]

    def __init__(self):
        # Default light direction: slightly tilted forward (+Y) and down (-Z)
        # In Y-forward Z-up: [0.3, 1.0, -0.5] means tilted right, forward, and down
        self.light_direction = np.array([0.3, 1.0, -0.5], dtype=np.float32)
        self.light_color = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        self.lights = []
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

    def build_lights(self) -> List["Light"]:
        """
        Build world-space light parameters from all light components.

        Transforms local +Y axis to world space through entity rotation:
        dir_world = R * (0, 1, 0)

        Convention: Y-forward, Z-up. Light points along local +Y.
        """
        lights: List[Light] = []
        forward_local = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        if self.tc_scene is None:
            self.lights = lights
            return lights

        def process_light(comp):
            if not comp.enabled:
                return True
            if comp.entity is None:
                return True

            ent = comp.entity
            pose = ent.transform.global_pose()
            rotation = pose.rotation_matrix()

            position = np.asarray(pose.lin, dtype=np.float32)
            forward_world = np.asarray(rotation @ forward_local, dtype=np.float32)

            light = comp.to_light()
            light.position = position
            light.direction = forward_world
            lights.append(light)
            return True

        self.tc_scene.foreach_component_of_type("LightComponent", process_light)
        self.lights = lights
        return lights

    def serialize(self) -> dict:
        """Serialize lighting settings."""
        ss = self.shadow_settings
        return {
            "light_direction": list(self.light_direction),
            "light_color": list(self.light_color),
            "ambient_color": list(self.ambient_color),
            "ambient_intensity": self.ambient_intensity,
            "shadow_settings": ss.serialize(),
        }

    def load_from_data(self, data: dict) -> None:
        """Load lighting settings from serialized data."""
        # Default: +Y forward, slightly tilted right and down
        self.light_direction = np.asarray(
            data.get("light_direction", [0.3, 1.0, -0.5]),
            dtype=np.float32
        )
        self.light_color = np.asarray(
            data.get("light_color", [1.0, 1.0, 1.0]),
            dtype=np.float32
        )
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
        self.lights.clear()
        self.tc_scene = None
        self._tc_lighting = None
