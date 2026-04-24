"""
lll component.
"""

from __future__ import annotations

from termin.visualization.core.component import Component


class lll(Component):
    """
    Custom component.

    Attributes:
        speed: Movement speed.
    """

    def __init__(self, speed: float = 1.0):
        super().__init__()
        self.speed = speed

    def on_start(self) -> None:
        """Called when the component is first activated."""
        pass

    def on_update(self, dt: float) -> None:
        """Called every frame.

        Args:
            dt: Delta time in seconds.
        """
        pass

    def on_destroy(self) -> None:
        """Called when the component is destroyed."""
        pass
