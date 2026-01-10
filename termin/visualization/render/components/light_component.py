from __future__ import annotations

from typing import Optional

import numpy as np

from termin.visualization.core.python_component import PythonComponent
from termin.editor.inspect_field import InspectField
from termin.lighting import LightType, Light, LightShadowParams


class LightComponent(PythonComponent):
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
            setter=lambda self, v: setattr(self, 'light_type', v if isinstance(v, LightType) else LightType(int(v))),
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
        "cascade_count": InspectField(
            path="cascade_count",
            label="Cascade Count",
            kind="int",
            min=1,
            max=4,
            step=1,
        ),
        "max_distance": InspectField(
            path="max_distance",
            label="Max Distance",
            kind="float",
            min=1.0,
            max=1000.0,
            step=10.0,
        ),
        "split_lambda": InspectField(
            path="split_lambda",
            label="Split Lambda",
            kind="float",
            min=0.0,
            max=1.0,
            step=0.1,
        ),
        "cascade_blend": InspectField(
            path="cascade_blend",
            label="Cascade Blend",
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

    @property
    def cascade_count(self) -> int:
        return self._shadows.cascade_count

    @cascade_count.setter
    def cascade_count(self, value: int):
        self._shadows.cascade_count = int(value)

    @property
    def max_distance(self) -> float:
        return self._shadows.max_distance

    @max_distance.setter
    def max_distance(self, value: float):
        self._shadows.max_distance = float(value)

    @property
    def split_lambda(self) -> float:
        return self._shadows.split_lambda

    @split_lambda.setter
    def split_lambda(self, value: float):
        self._shadows.split_lambda = float(value)

    @property
    def cascade_blend(self) -> bool:
        return self._shadows.cascade_blend

    @cascade_blend.setter
    def cascade_blend(self, value: bool):
        self._shadows.cascade_blend = bool(value)

    def to_light(self) -> Light:
        """Преобразовать в объект Light для рендеринга."""
        return Light(
            type=self.light_type,
            color=self.color,
            intensity=self.intensity,
            shadows=self._shadows,
        )
