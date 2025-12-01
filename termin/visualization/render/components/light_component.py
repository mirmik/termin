from __future__ import annotations

import numpy as np

from termin.visualization.core.entity import Component
from termin.visualization.core.lighting.light import LightType


class LightComponent(Component):
    """
    Простейший компонент источника света.
    Пока хранит только тип, цвет и интенсивность.
    """

    def __init__(
        self,
        light_type: LightType = LightType.DIRECTIONAL,
        color=(1.0, 1.0, 1.0),
        intensity: float = 1.0,
        enabled: bool = True,
    ):
        super().__init__(enabled=enabled)
        self.light_type = light_type
        self.color = np.asarray(color, dtype=np.float32)
        self.intensity = float(intensity)
