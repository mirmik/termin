from __future__ import annotations

from typing import Optional

import numpy as np

from termin.visualization.core.component import Component
from termin.visualization.core.serialization import COMPONENT_REGISTRY
from termin.editor.inspect_field import InspectField
from termin.visualization.core.lighting import LightType, Light, LightShadowParams


class LightComponent(Component):
    """
    Простейший компонент источника света.
    Хранит тип, цвет, интенсивность и параметры теней.
    """

    # Используем кастомную сериализацию вместо serializable_fields
    serializable_fields = []

    inspect_fields = {
        "light_type": InspectField(
            path="light_type",
            label="Light Type",
            kind="enum",
            choices=[
                (LightType.DIRECTIONAL, "Directional"),
                (LightType.POINT, "Point"),
                (LightType.SPOT, "Spot"),
            ],
        ),
        "color": InspectField(
            path="color",
            label="Color",
            kind="color",
        ),
        "intensity": InspectField(
            path="intensity",
            label="Intensity",
            kind="float",
        ),
        "shadows_enabled": InspectField(
            path="shadows.enabled",
            label="Cast Shadows",
            kind="bool",
        ),
        "shadows_map_resolution": InspectField(
            path="shadows.map_resolution",
            label="Shadow Resolution",
            kind="int",
            min=256,
            max=4096,
            step=256,
        ),
    }

    def __init__(
        self,
        light_type: LightType = LightType.DIRECTIONAL,
        color=(1.0, 1.0, 1.0),
        intensity: float = 1.0,
        shadows: Optional[LightShadowParams] = None,
        enabled: bool = True,
    ):
        super().__init__(enabled=enabled)
        self.light_type = light_type
        self.color = np.asarray(color, dtype=np.float32)
        self.intensity = float(intensity)
        self.shadows = shadows if shadows is not None else LightShadowParams()

    def to_light(self) -> Light:
        """Преобразовать в объект Light для рендеринга."""
        return Light(
            type=self.light_type,
            color=self.color,
            intensity=self.intensity,
            shadows=self.shadows,
        )

    def serialize_data(self):
        """Сериализует компонент в словарь."""
        return {
            "light_type": self.light_type.value,
            "color": list(self.color),
            "intensity": self.intensity,
            "shadows_enabled": self.shadows.enabled,
            "shadows_map_resolution": self.shadows.map_resolution,
        }

    @classmethod
    def deserialize(cls, data, context=None):
        """Десериализует компонент из словаря."""
        light_type = LightType(data.get("light_type", LightType.DIRECTIONAL.value))
        color = data.get("color", (1.0, 1.0, 1.0))
        intensity = data.get("intensity", 1.0)
        shadows = LightShadowParams(
            enabled=data.get("shadows_enabled", False),
            map_resolution=data.get("shadows_map_resolution", 1024),
        )
        return cls(
            light_type=light_type,
            color=color,
            intensity=intensity,
            shadows=shadows,
        )


# Регистрируем для десериализации
COMPONENT_REGISTRY["LightComponent"] = LightComponent
