"""
MyComponent component.
"""

from __future__ import annotations

from termin.visualization.core.python_component import PythonComponent

print("Loading MyComponent from my_component.py")

class MyComponent(PythonComponent):
    """
    Custom component.

    Attributes:
        speed: Movement speed.
    """

    def __init__(self, speed: float = 1.0):
        super().__init__()
        self.speed = speed

    def start(self) -> None:
        """Called when the component is first activated."""
        super().start()

    def update(self, dt: float) -> None:
        """Called every frame.

        Args:
            dt: Delta time in seconds.
        """
        pass
