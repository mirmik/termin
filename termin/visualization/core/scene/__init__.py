"""Scene module - container for entities and scene configuration."""

from termin.entity._entity_native import TcScene as Scene, deserialize_scene
from termin.lighting import ShadowSettings

from ._helpers import find_component, find_components, dispatch_input

__all__ = [
    "Scene",
    "ShadowSettings",
    "deserialize_scene",
    "find_component",
    "find_components",
    "dispatch_input",
]
