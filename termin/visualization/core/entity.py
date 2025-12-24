"""Scene entity - re-export from termin.entity."""

from termin._native.entity import Entity
from termin.visualization.core.component import Component, InputComponent

__all__ = ["Entity", "Component", "InputComponent"]
