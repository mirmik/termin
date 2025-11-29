"""Примитивы источников света для forward-рендеринга."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np

from .attenuation import AttenuationCoefficients


class LightType(str, Enum):
    """Поддерживаемые типы источников."""

    DIRECTIONAL = "directional"
    POINT = "point"
    SPOT = "spot"
    AMBIENT = "ambient"


@dataclass
class LightShadowParams:
    """Настройки теневой карты для источника света."""

    enabled: bool = False
    bias: float = 0.001
    normal_bias: float = 0.0
    map_resolution: int = 1024


@dataclass
class LightSample:
    """Результат оценки вклада света в точке поверхности.

    Выходящая радиансная составляющая:
    ``L_o = attenuation * intensity_rgb``. Вектор ``L`` направлен от точки
    поверхности к источнику (используется в скалярных произведениях вида
    ``max(dot(N, L), 0)``).
    """

    L: np.ndarray
    distance: float
    attenuation: float
    radiance: np.ndarray


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


@dataclass
class Light:
    """Один источник света с классическими параметрами.

    ``direction`` — продольная ось источника (из источника в сцену). В шейдерах
    используем ``-direction`` как входящее направление для направленного света.
    """

    type: LightType
    color: np.ndarray = field(default_factory=lambda: np.ones(3, dtype=np.float32))
    intensity: float = 1.0
    direction: Optional[np.ndarray] = None
    position: Optional[np.ndarray] = None
    range: Optional[float] = None
    inner_angle: float = np.deg2rad(15.0)
    outer_angle: float = np.deg2rad(30.0)
    attenuation: AttenuationCoefficients = field(default_factory=AttenuationCoefficients)
    shadows: LightShadowParams = field(default_factory=LightShadowParams)
    name: Optional[str] = None

    def __post_init__(self):
        self.color = np.asarray(self.color, dtype=np.float32)
        if self.color.shape != (3,):
            raise ValueError("Light color must be an RGB triplet.")

        if self.direction is None:
            self.direction = np.array([0.0, -1.0, 0.0], dtype=np.float32)
        else:
            self.direction = _normalize(np.asarray(self.direction, dtype=np.float32))

        if self.position is None:
            self.position = np.zeros(3, dtype=np.float32)
        else:
            self.position = np.asarray(self.position, dtype=np.float32)

        if self.outer_angle < self.inner_angle:
            self.outer_angle = self.inner_angle

    @property
    def intensity_rgb(self) -> np.ndarray:
        """Вектор интенсивности излучения ``I = intensity * color``."""
        return self.color * float(self.intensity)

    def _distance_weight(self, distance: float) -> float:
        weight = self.attenuation.evaluate(distance)
        if self.range is not None and distance > self.range:
            weight = 0.0
        return weight

    def _spot_weight(self, L: np.ndarray) -> float:
        """Плавный вес прожектора по углу между осью и ``-L``.

        Косинусная формула прожектора:
        ``w = clamp((cos(theta) - cos_o) / (cos_i - cos_o), 0, 1)``, где
        ``theta`` — угол между осью прожектора и направлением к точке.
        """
        cos_theta = np.dot(self.direction, -L)
        cos_outer = np.cos(self.outer_angle)
        cos_inner = np.cos(self.inner_angle)

        if cos_theta <= cos_outer:
            return 0.0
        if cos_theta >= cos_inner:
            return 1.0

        t = (cos_theta - cos_outer) / (cos_inner - cos_outer)
        return t * t * (3.0 - 2.0 * t)  # smoothstep

    def sample(self, point: np.ndarray) -> LightSample:
        """Оценить вклад света в точке ``point`` (мировое пространство)."""
        if self.type == LightType.AMBIENT:
            return LightSample(
                L=np.zeros(3, dtype=np.float32),
                distance=np.inf,
                attenuation=1.0,
                radiance=self.intensity_rgb,
            )

        if self.type == LightType.DIRECTIONAL:
            incoming = -_normalize(self.direction)
            return LightSample(
                L=incoming,
                distance=np.inf,
                attenuation=1.0,
                radiance=self.intensity_rgb,
            )

        to_light = np.asarray(self.position - point, dtype=np.float32)
        distance = float(np.linalg.norm(to_light))
        if distance <= 1e-6:
            L = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        else:
            L = to_light / distance

        attenuation = self._distance_weight(distance)
        if self.type == LightType.SPOT:
            attenuation *= self._spot_weight(L)

        return LightSample(
            L=L,
            distance=distance,
            attenuation=attenuation,
            radiance=self.intensity_rgb * attenuation,
        )

    def to_uniform_dict(self) -> dict:
        """Упаковать параметры в словарь для загрузки в uniform-пакеты."""
        return {
            "type": self.type.value,
            "color": self.color.tolist(),
            "intensity": float(self.intensity),
            "direction": _normalize(self.direction).tolist(),
            "position": self.position.tolist(),
            "range": None if self.range is None else float(self.range),
            "inner_angle": float(self.inner_angle),
            "outer_angle": float(self.outer_angle),
            "attenuation": {
                "constant": float(self.attenuation.constant),
                "linear": float(self.attenuation.linear),
                "quadratic": float(self.attenuation.quadratic),
            },
            "shadows": {
                "enabled": bool(self.shadows.enabled),
                "bias": float(self.shadows.bias),
                "normal_bias": float(self.shadows.normal_bias),
                "map_resolution": int(self.shadows.map_resolution),
            },
            "name": self.name,
        }
