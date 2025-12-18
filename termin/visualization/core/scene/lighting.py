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

if TYPE_CHECKING:
    from termin.visualization.core.lighting.light import Light
    from termin.visualization.render.components.light_component import LightComponent


class ShadowSettings:
    """
    Shadow rendering settings.

    Attributes:
        method: Shadow sampling method (0=hard, 1=pcf, 2=poisson)
        softness: Sampling radius multiplier (0=sharp, 1=default, >1=softer)
        bias: Depth bias to prevent shadow acne
    """

    # Method constants
    METHOD_HARD = 0
    METHOD_PCF = 1
    METHOD_POISSON = 2

    METHOD_NAMES = ["Hard", "PCF 5x5", "Poisson"]

    def __init__(self):
        self.method: int = self.METHOD_PCF
        self.softness: float = 1.0
        self.bias: float = 0.005

    def serialize(self) -> dict:
        return {
            "method": self.method,
            "softness": self.softness,
            "bias": self.bias,
        }

    def load_from_data(self, data: dict) -> None:
        self.method = data.get("method", self.METHOD_PCF)
        self.softness = data.get("softness", 1.0)
        self.bias = data.get("bias", 0.005)


class LightingManager:
    """
    Manages scene lighting including directional light and ambient settings.

    Handles:
    - Global directional light (direction + color)
    - Ambient light (color + intensity)
    - Collection of dynamic LightComponents
    - Shadow settings
    """

    def __init__(self):
        # Default light direction: slightly tilted forward (+Y) and down (-Z)
        # In Y-forward Z-up: [0.3, 1.0, -0.5] means tilted right, forward, and down
        self.light_direction = np.array([0.3, 1.0, -0.5], dtype=np.float32)
        self.light_color = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        self.ambient_color = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        self.ambient_intensity = 0.1

        self.light_components: List["LightComponent"] = []
        self.lights: List["Light"] = []

        self.shadow_settings = ShadowSettings()

    def register_light_component(self, component: "LightComponent") -> None:
        """Register a light component."""
        self.light_components.append(component)

    def unregister_light_component(self, component: "LightComponent") -> None:
        """Unregister a light component."""
        if component in self.light_components:
            self.light_components.remove(component)

    def build_lights(self) -> List["Light"]:
        """
        Build world-space light parameters from all light components.

        Transforms local +Y axis to world space through entity rotation:
        dir_world = R * (0, 1, 0)

        Convention: Y-forward, Z-up. Light points along local +Y.
        """
        lights: List[Light] = []
        # Local forward direction: +Y in Y-forward Z-up convention
        forward_local = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        for comp in self.light_components:
            if not comp.enabled:
                continue
            if comp.entity is None:
                continue

            ent = comp.entity
            pose = ent.transform.global_pose()
            rotation = pose.rotation_matrix()

            position = np.asarray(pose.lin, dtype=np.float32)
            forward_world = np.asarray(rotation @ forward_local, dtype=np.float32)

            light = comp.to_light()
            light.position = position
            light.direction = forward_world
            lights.append(light)

        self.lights = lights
        return lights

    def serialize(self) -> dict:
        """Serialize lighting settings."""
        return {
            "light_direction": list(self.light_direction),
            "light_color": list(self.light_color),
            "ambient_color": list(self.ambient_color),
            "ambient_intensity": self.ambient_intensity,
            "shadow_settings": self.shadow_settings.serialize(),
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
            self.shadow_settings.load_from_data(data["shadow_settings"])
