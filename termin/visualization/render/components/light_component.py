from __future__ import annotations

from typing import Optional

import numpy as np

from termin.visualization.core.component import Component
from termin.editor.inspect_field import InspectField
from termin.lighting import LightType, Light, LightShadowParams


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
            ],
            setter=lambda self, v: setattr(self, 'light_type', v if isinstance(v, LightType) else LightType(v)),
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
            path="shadows_enabled",
            label="Cast Shadows",
            kind="bool",
        ),
        "shadows_map_resolution": InspectField(
            path="shadows_map_resolution",
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
        super().__init__()
        self.enabled = enabled
        self.light_type = light_type
        self.color = np.asarray(color, dtype=np.float32)
        self.intensity = float(intensity)
        self._shadows = shadows if shadows is not None else LightShadowParams()

    @property
    def shadows_enabled(self) -> bool:
        return self._shadows.enabled

    @shadows_enabled.setter
    def shadows_enabled(self, value: bool):
        self._shadows.enabled = value

    @property
    def shadows_map_resolution(self) -> int:
        return self._shadows.map_resolution

    @shadows_map_resolution.setter
    def shadows_map_resolution(self, value: int):
        self._shadows.map_resolution = int(value)

    @property
    def shadows(self) -> LightShadowParams:
        return self._shadows

    def to_light(self) -> Light:
        """Преобразовать в объект Light для рендеринга."""
        return Light(
            type=self.light_type,
            color=self.color,
            intensity=self.intensity,
            shadows=self._shadows,
        )
