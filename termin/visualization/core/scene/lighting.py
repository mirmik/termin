"""Lighting configuration and management for Scene."""

from __future__ import annotations

from typing import List, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from termin.visualization.core.lighting.light import Light
    from termin.visualization.render.components.light_component import LightComponent


class LightingManager:
    """
    Manages scene lighting including directional light and ambient settings.

    Handles:
    - Global directional light (direction + color)
    - Ambient light (color + intensity)
    - Collection of dynamic LightComponents
    """

    def __init__(self):
        self.light_direction = np.array([-0.5, -1.0, -0.3], dtype=np.float32)
        self.light_color = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        self.ambient_color = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        self.ambient_intensity = 0.1

        self.light_components: List["LightComponent"] = []
        self.lights: List["Light"] = []

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

        Transforms local -Z axis to world space through entity rotation:
        dir_world = R * (0, 0, -1)
        """
        lights: List[Light] = []
        forward_local = np.array([0.0, 0.0, -1.0], dtype=np.float32)

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
        }

    def load_from_data(self, data: dict) -> None:
        """Load lighting settings from serialized data."""
        self.light_direction = np.asarray(
            data.get("light_direction", [-0.5, -1.0, -0.3]),
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
