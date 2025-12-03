from __future__ import annotations

from typing import Optional

import numpy as np

from termin.visualization.core.entity import Component
from termin.editor.inspect_field import InspectField
from termin.visualization.core.lighting.light import LightType, Light, LightShadowParams


class LightComponent(Component):
    """
    Простейший компонент источника света.
    Хранит тип, цвет, интенсивность и параметры теней.
    """

    inspect_fields = {
        "light_type": InspectField(
            path="light_type",
            label="Light Type",
            kind="enum",
            choices=[
                (LightType.DIRECTIONAL, "Directional"),
                (LightType.POINT, "Point"),
                (LightType.SPOT, "Spot"),
                (LightType.AMBIENT, "Ambient"),
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
