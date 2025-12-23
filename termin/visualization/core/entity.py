"""Scene entity - re-export from C++ implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Re-export Entity from C++ implementation
from termin.entity import Entity

# Re-export Component classes from component module for backwards compatibility
from termin.visualization.core.component import Component, InputComponent

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene

__all__ = ["Entity", "Component", "InputComponent"]
