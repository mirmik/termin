"""Утилиты группировки источников света для forward-проходов."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from termin.visualization.core.lighting.light import Light, LightType


@dataclass
class LightBudget:
    """Жёсткие лимиты на количество источников одного прохода."""

    directional: int = 2
    point: int = 16
    spot: int = 8

    def fits(self, light: Light, counts: dict[LightType, int]) -> bool:
        match light.type:
            case LightType.DIRECTIONAL:
                return counts[LightType.DIRECTIONAL] < self.directional
            case LightType.POINT:
                return counts[LightType.POINT] < self.point
            case LightType.SPOT:
                return counts[LightType.SPOT] < self.spot
        return False


class LightSetup:
    """Container that groups lights and enforces a budget."""

    def __init__(self, budget: LightBudget | None = None):
        self.budget = budget or LightBudget()
        self._lights: List[Light] = []
        self._counts = {
            LightType.DIRECTIONAL: 0,
            LightType.POINT: 0,
            LightType.SPOT: 0,
        }

    def add_light(self, light: Light) -> bool:
        """Insert light if it fits within the budget."""
        if not self.budget.fits(light, self._counts):
            return False
        self._lights.append(light)
        self._counts[light.type] += 1
        return True

    def clear(self):
        self._lights.clear()
        for key in self._counts:
            self._counts[key] = 0

    def lights(self) -> Iterable[Light]:
        return list(self._lights)

    def forward_payload(self) -> dict:
        """Pack lights into buckets consumable by a forward renderer."""
        payload = {
            "directional": [],
            "point": [],
            "spot": [],
        }
        for light in self._lights:
            payload[light.type.value].append(light.to_uniform_dict())
        return payload
