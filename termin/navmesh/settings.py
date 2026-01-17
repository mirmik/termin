"""
Navigation settings — project-level configuration for navigation system.

Stores agent types and other navigation parameters.
Settings are saved to project_settings/navigation.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

from termin._native import log


@dataclass
class AgentType:
    """
    Navigation agent type definition.

    Defines physical parameters of an agent for pathfinding:
    - radius: Agent collision radius (affects NavMesh erosion)
    - height: Agent height (for vertical clearance)
    - max_slope: Maximum walkable slope in degrees
    - step_height: Maximum step height agent can climb
    """

    name: str = "Human"
    radius: float = 0.5
    height: float = 2.0
    max_slope: float = 45.0
    step_height: float = 0.4

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "AgentType":
        """Deserialize from dictionary."""
        return AgentType(
            name=data.get("name", "Human"),
            radius=data.get("radius", 0.5),
            height=data.get("height", 2.0),
            max_slope=data.get("max_slope", 45.0),
            step_height=data.get("step_height", 0.4),
        )


@dataclass
class NavigationSettings:
    """
    Project-level navigation settings.

    Contains list of agent types and other global navigation parameters.
    """

    agent_types: List[AgentType] = field(default_factory=lambda: [AgentType()])

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "agent_types": [agent.to_dict() for agent in self.agent_types],
        }

    @staticmethod
    def from_dict(data: dict) -> "NavigationSettings":
        """Deserialize from dictionary."""
        agent_types = [
            AgentType.from_dict(agent_data)
            for agent_data in data.get("agent_types", [])
        ]
        if not agent_types:
            agent_types = [AgentType()]
        return NavigationSettings(agent_types=agent_types)

    def get_agent_type(self, name: str) -> Optional[AgentType]:
        """Get agent type by name."""
        for agent in self.agent_types:
            if agent.name == name:
                return agent
        return None

    def get_agent_type_names(self) -> List[str]:
        """Get list of all agent type names."""
        return [agent.name for agent in self.agent_types]


class NavigationSettingsManager:
    """
    Singleton manager for navigation settings.

    Handles loading/saving settings from project directory.
    """

    _instance: Optional["NavigationSettingsManager"] = None
    _settings: NavigationSettings
    _project_path: Optional[Path] = None

    def __init__(self) -> None:
        self._settings = NavigationSettings()

    @classmethod
    def instance(cls) -> "NavigationSettingsManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = NavigationSettingsManager()
        return cls._instance

    @property
    def settings(self) -> NavigationSettings:
        """Get current navigation settings."""
        return self._settings

    def set_project_path(self, path: Path) -> None:
        """Set project path and load settings."""
        self._project_path = path
        self._load()

    def _get_settings_path(self) -> Optional[Path]:
        """Get path to settings file."""
        if self._project_path is None:
            return None
        settings_dir = self._project_path / "project_settings"
        return settings_dir / "navigation.json"

    def _load(self) -> None:
        """Load settings from file."""
        path = self._get_settings_path()
        if path is None or not path.exists():
            self._settings = NavigationSettings()
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._settings = NavigationSettings.from_dict(data)
            log.info(f"[NavigationSettings] Loaded {len(self._settings.agent_types)} agent types from {path}")
        except Exception as e:
            log.error(f"[NavigationSettings] Failed to load settings: {e}")
            self._settings = NavigationSettings()

    def save(self) -> bool:
        """Save settings to file."""
        path = self._get_settings_path()
        if path is None:
            log.error("[NavigationSettings] No project path set, cannot save")
            return False

        try:
            # Create directory if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._settings.to_dict(), f, indent=2)
            log.info(f"[NavigationSettings] Saved to {path}")
            return True
        except Exception as e:
            log.error(f"[NavigationSettings] Failed to save settings: {e}")
            return False

    def add_agent_type(self, agent: AgentType) -> None:
        """Add new agent type."""
        self._settings.agent_types.append(agent)

    def remove_agent_type(self, index: int) -> None:
        """Remove agent type by index."""
        if 0 <= index < len(self._settings.agent_types):
            del self._settings.agent_types[index]
            # Ensure at least one agent type exists
            if not self._settings.agent_types:
                self._settings.agent_types.append(AgentType())

    def update_agent_type(self, index: int, agent: AgentType) -> None:
        """Update agent type at index."""
        if 0 <= index < len(self._settings.agent_types):
            self._settings.agent_types[index] = agent
