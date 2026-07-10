"""Toolkit-neutral draft model for navigation project settings."""

from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from typing import Callable

from termin.navmesh.settings import (
    NAVMESH_AREA_COUNT,
    AgentType,
    NavigationSettingsManager,
)


@dataclass(frozen=True)
class NavigationAgentSnapshot:
    name: str
    radius: float
    height: float
    max_slope: float
    step_height: float


@dataclass(frozen=True)
class NavigationSettingsSnapshot:
    agents: tuple[NavigationAgentSnapshot, ...]
    area_names: tuple[str, ...]


def _agent_snapshot(agent: AgentType) -> NavigationAgentSnapshot:
    return NavigationAgentSnapshot(
        name=str(agent.name),
        radius=float(agent.radius),
        height=float(agent.height),
        max_slope=float(agent.max_slope),
        step_height=float(agent.step_height),
    )


class NavigationSettingsController:
    def __init__(
        self,
        manager: NavigationSettingsManager | None = None,
        *,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        self._manager = manager or NavigationSettingsManager.instance()
        self._on_changed = on_changed
        self._draft = self._read_manager()

    @property
    def snapshot(self) -> NavigationSettingsSnapshot:
        return self._draft

    def revert(self) -> NavigationSettingsSnapshot:
        self._draft = self._read_manager()
        return self._draft

    def update_agent(self, index: int, agent: NavigationAgentSnapshot) -> NavigationSettingsSnapshot:
        if not 0 <= index < len(self._draft.agents):
            raise IndexError("navigation agent index is out of range")
        validated = self.validate_agent(agent)
        agents = list(self._draft.agents)
        agents[index] = validated
        self._draft = NavigationSettingsSnapshot(tuple(agents), self._draft.area_names)
        return self._draft

    def add_agent(self) -> tuple[int, NavigationSettingsSnapshot]:
        existing = {agent.name for agent in self._draft.agents}
        name = "New Agent"
        suffix = 1
        while name in existing:
            name = f"New Agent {suffix}"
            suffix += 1
        agents = self._draft.agents + (NavigationAgentSnapshot(name, 0.5, 2.0, 45.0, 0.4),)
        self._draft = NavigationSettingsSnapshot(agents, self._draft.area_names)
        return len(agents) - 1, self._draft

    def remove_agent(self, index: int) -> NavigationSettingsSnapshot:
        if len(self._draft.agents) <= 1:
            raise ValueError("at least one navigation agent type must exist")
        if not 0 <= index < len(self._draft.agents):
            raise IndexError("navigation agent index is out of range")
        agents = list(self._draft.agents)
        del agents[index]
        self._draft = NavigationSettingsSnapshot(tuple(agents), self._draft.area_names)
        return self._draft

    def set_area_names(self, names: tuple[str, ...]) -> NavigationSettingsSnapshot:
        if len(names) != NAVMESH_AREA_COUNT:
            raise ValueError("navigation area names must contain exactly 64 values")
        normalized = tuple(str(name).strip()[:64] for name in names)
        self._draft = NavigationSettingsSnapshot(self._draft.agents, normalized)
        return self._draft

    def save(self) -> NavigationSettingsSnapshot:
        previous = deepcopy(self._manager.settings)
        try:
            for index, agent in enumerate(self._draft.agents):
                value = AgentType(
                    name=agent.name,
                    radius=agent.radius,
                    height=agent.height,
                    max_slope=agent.max_slope,
                    step_height=agent.step_height,
                )
                if index < len(self._manager.settings.agent_types):
                    self._manager.update_agent_type(index, value)
                else:
                    self._manager.add_agent_type(value)
            while len(self._manager.settings.agent_types) > len(self._draft.agents):
                self._manager.remove_agent_type(len(self._manager.settings.agent_types) - 1)
            for index, name in enumerate(self._draft.area_names):
                self._manager.set_navmesh_area_name(index, name)
            if not self._manager.save():
                raise RuntimeError("failed to save navigation settings")
        except Exception:
            self._manager.settings = previous
            raise
        self._draft = self._read_manager()
        if self._on_changed is not None:
            self._on_changed()
        return self._draft

    @staticmethod
    def validate_agent(agent: NavigationAgentSnapshot) -> NavigationAgentSnapshot:
        name = agent.name.strip()
        radius = float(agent.radius)
        height = float(agent.height)
        max_slope = float(agent.max_slope)
        step_height = float(agent.step_height)
        if not name:
            raise ValueError("navigation agent name must not be empty")
        if not 0.1 <= radius <= 10.0:
            raise ValueError("navigation agent radius must be in range 0.1..10")
        if not 0.1 <= height <= 20.0:
            raise ValueError("navigation agent height must be in range 0.1..20")
        if not 0.0 <= max_slope <= 90.0:
            raise ValueError("navigation agent max slope must be in range 0..90")
        if not 0.0 <= step_height <= 5.0:
            raise ValueError("navigation agent step height must be in range 0..5")
        return NavigationAgentSnapshot(name, radius, height, max_slope, step_height)

    def _read_manager(self) -> NavigationSettingsSnapshot:
        settings = self._manager.settings
        area_names = tuple(str(name) for name in settings.navmesh_area_names)
        if len(area_names) != NAVMESH_AREA_COUNT:
            raise RuntimeError("navigation settings contain an invalid area-name table")
        agents = tuple(_agent_snapshot(agent) for agent in settings.agent_types)
        if not agents:
            raise RuntimeError("navigation settings contain no agent types")
        return NavigationSettingsSnapshot(agents, area_names)


__all__ = [
    "NavigationAgentSnapshot",
    "NavigationSettingsController",
    "NavigationSettingsSnapshot",
]
