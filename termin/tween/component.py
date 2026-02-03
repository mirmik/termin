"""TweenManagerComponent - Component wrapper for TweenManager."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from termin.visualization.core.python_component import PythonComponent
from termin.visualization.core.scene import get_current_scene
from termin.tween.manager import TweenManager
from termin.tween.ease import Ease
from termin.tween.tween import Tween, MoveTween, RotateTween, ScaleTween

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.entity import Entity
    from termin.kinematic.general_transform import GeneralTransform3


class TweenManagerComponent(PythonComponent):
    """
    Component that provides tweening functionality to a scene.

    Add this component to any entity in the scene. It will automatically:
    - Update all tweens each frame
    - Kill tweens when their target entity is removed from scene

    Usage:
        # Setup
        tween_entity = Entity(name="TweenManager")
        tween_comp = TweenManagerComponent()
        tween_entity.add_component(tween_comp)
        scene.add(tween_entity)

        # Create tweens
        tween_comp.move(some_entity.transform, target_pos, 1.0, ease=Ease.OUT_QUAD)
        tween_comp.rotate(some_entity.transform, target_quat, 0.5)
    """

    def __init__(self):
        super().__init__(enabled=True)
        self._manager = TweenManager()
        self._scene: Scene | None = None

    @property
    def manager(self) -> TweenManager:
        """Access the underlying TweenManager."""
        return self._manager

    def start(self) -> None:
        super().start()
        self._scene = get_current_scene()

    def on_removed(self) -> None:
        super().on_removed()
        if self._scene is not None:
            self._scene = None
        self._manager.clear()

    def update(self, dt: float) -> None:
        """Update all tweens."""
        self._manager.update(dt)

    # Delegate factory methods to manager

    def add(self, tween: Tween) -> Tween:
        """Add a custom tween."""
        return self._manager.add(tween)

    def move(
        self,
        transform: "GeneralTransform3",
        target: np.ndarray,
        duration: float,
        ease: Ease = Ease.LINEAR,
        delay: float = 0.0,
    ) -> MoveTween:
        """Create a position tween."""
        return self._manager.move(transform, target, duration, ease, delay)

    def rotate(
        self,
        transform: "GeneralTransform3",
        target: np.ndarray,
        duration: float,
        ease: Ease = Ease.LINEAR,
        delay: float = 0.0,
    ) -> RotateTween:
        """Create a rotation tween."""
        return self._manager.rotate(transform, target, duration, ease, delay)

    def scale(
        self,
        transform: "GeneralTransform3",
        target: np.ndarray | float,
        duration: float,
        ease: Ease = Ease.LINEAR,
        delay: float = 0.0,
    ) -> ScaleTween:
        """Create a scale tween."""
        return self._manager.scale(transform, target, duration, ease, delay)

    def kill_all(self, transform: "GeneralTransform3 | None" = None) -> int:
        """Kill all tweens, optionally filtered by transform."""
        return self._manager.kill_all(transform)

    def kill_entity(self, entity: "Entity") -> int:
        """Kill all tweens targeting entity's transform."""
        return self._manager.kill_entity(entity)

    def pause_all(self, transform: "GeneralTransform3 | None" = None) -> int:
        """Pause all tweens."""
        return self._manager.pause_all(transform)

    def resume_all(self, transform: "GeneralTransform3 | None" = None) -> int:
        """Resume all paused tweens."""
        return self._manager.resume_all(transform)

    @property
    def count(self) -> int:
        """Number of active tweens."""
        return self._manager.count

    def clear(self) -> None:
        """Remove all tweens."""
        self._manager.clear()
