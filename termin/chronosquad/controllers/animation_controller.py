"""AnimationController - controls animation based on timeline time."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from termin._native import log
from termin.visualization.core.python_component import PythonComponent
from termin.chronosquad.core import AnimationType, AnimatronicAnimationTask

if TYPE_CHECKING:
    from termin.visualization.animation.player import AnimationPlayer
    from .object_controller import ObjectController


class AnimationController(PythonComponent):
    """
    Controls animation playback based on timeline time.

    Works together with ObjectController:
    - Gets chrono object from ObjectController
    - Converts timeline time to local time
    - Gets animation tasks from chrono object
    - Sets AnimationPlayer time directly (external time control)
    """

    # Animation name mapping
    ANIMATION_NAMES: Dict[AnimationType, str] = {
        AnimationType.IDLE: "Idle",
        AnimationType.WALK: "Walk",
        AnimationType.RUN: "Run",
        AnimationType.DEATH: "Death",
    }

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)
        self._object_controller: ObjectController | None = None
        self._animation_player: AnimationPlayer | None = None
        self._current_animation_type: AnimationType | None = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Find ObjectController and AnimationPlayer if not yet initialized."""
        if self._initialized:
            return
        self._initialized = True
        self._find_object_controller()
        self._find_animation_player()

    def _find_object_controller(self) -> None:
        """Find ObjectController on same entity."""
        if self.entity is None:
            return

        from .object_controller import ObjectController

        self._object_controller = self.entity.get_component(ObjectController)

    def _find_animation_player(self) -> None:
        """Find AnimationPlayer on Model child entity."""
        if self.entity is None:
            return

        from termin.visualization.animation.player import AnimationPlayer

        # Look for "Model" child
        model = self.entity.find_child("Model")
        if not model.valid:
            return

        # Get AnimationPlayer component
        self._animation_player = model.get_component(AnimationPlayer)
        if self._animation_player is not None:
            # Disable automatic time update - we control time externally
            self._animation_player.playing = False

    def update(self, dt: float) -> None:
        """Update animation based on timeline time."""
        self._ensure_initialized()

        if self._object_controller is None or self._animation_player is None:
            log.warning(f"[AnimationController] Missing: objctr={self._object_controller}, player={self._animation_player}")
            return

        # Get chrono object from ObjectController
        chrono_obj = self._object_controller.chrono_object
        if chrono_obj is None:
            log.warning(f"[AnimationController] No chrono object for '{self.entity.name}', timeline={self._object_controller.timeline}")
            return

        # Get timeline time
        timeline = chrono_obj.timeline
        if timeline is None:
            log.warning(f"[AnimationController] Chrono object '{chrono_obj.name}' has no timeline")
            return

        timeline_time = timeline.current_time

        # Convert to local time
        local_time = chrono_obj.local_time_real_time(timeline_time)

        # Get animation tasks
        tasks = chrono_obj.animations(local_time)

        if tasks:
            # Use the first (most recent) task
            # TODO: Implement blending with multiple tasks
            task = tasks[0]
        else:
            # No animatronics - default to Idle
            task = AnimatronicAnimationTask(
                animation_type=AnimationType.IDLE,
                animation_time=local_time,
                coeff=1.0,
                loop=True,
                animation_booster=1.0,
            )

        self._apply_animation_task(task)

    def _apply_animation_task(self, task: AnimatronicAnimationTask) -> None:
        """Apply animation task to AnimationPlayer."""
        if self._animation_player is None:
            return

        # Get animation name
        anim_name = self.ANIMATION_NAMES.get(task.animation_type)
        if anim_name is None:
            log.warning(f"[AnimationController] Unknown animation type: {task.animation_type}")
            return

        # Check if animation exists
        clips_map = self._animation_player.clips_map
        if anim_name not in clips_map:
            log.warning(f"[AnimationController] Animation '{anim_name}' not found in AnimationPlayer")
            return

        # Switch clip if type changed
        if task.animation_type != self._current_animation_type:
            self._current_animation_type = task.animation_type
            self._animation_player.set_current(anim_name)

        # Set animation time directly
        # Handle looping
        if task.loop and self._animation_player.current is not None:
            clip_duration = self._animation_player.current.duration
            if clip_duration > 0:
                # Loop time within clip duration
                anim_time = task.animation_time % clip_duration
            else:
                anim_time = task.animation_time
        else:
            anim_time = task.animation_time

        # Update bones at calculated time (with booster)
        final_time = anim_time * task.animation_booster
        self._animation_player.update_bones_at_time(final_time)
