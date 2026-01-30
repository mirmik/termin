"""Scene module - container for entities and scene configuration."""

from ._scene import Scene, get_current_scene
from .lighting import LightingManager, ShadowSettings

__all__ = ["Scene", "get_current_scene", "LightingManager", "ShadowSettings"]
