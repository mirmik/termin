"""
TweenTest.py component.
"""

from __future__ import annotations

from termin.visualization.core.component import Component
from termin.visualization.core.scene import get_current_scene
from termin.geombase import Vec3
from termin.tween.ease import Ease


class TweenTest(Component):
    """
    Custom component.

    Attributes:
        speed: Movement speed.
    """

    def __init__(self, speed: float = 1.0):
        super().__init__()
        self.speed = speed
        self.tween_manager = None  # Placeholder for a tween manager

    def start(self) -> None:
        """Called when the component is first activated."""
        scene = get_current_scene()
        self.tween_manager = scene.find_component_by_name("TweenManagerComponent") if scene else None
        if self.tween_manager is None:
            return
        target = self.entity.transform.local_pose().lin + Vec3(0, 0, 5)
        self.tween_manager.move(self.entity.transform, target, 5.0, ease=Ease.IN_OUT_QUAD)
        
    def update(self, dt: float) -> None:
        pass
