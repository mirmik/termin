"""Scene module - container for entities and scene configuration."""

from ._scene import Scene
from .lighting import LightingManager, ShadowSettings

__all__ = ["Scene", "LightingManager", "ShadowSettings"]
