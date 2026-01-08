"""ChronosphereController - main game driver."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin._native import log
from termin.visualization.core.python_component import PythonComponent
from termin.chronosquad.core import ChronoSphere, Timeline

if TYPE_CHECKING:
    from .timeline_controller import TimelineController
    from .timeline_initializer import TimelineInitializer


class ChronosphereController(PythonComponent):
    """
    Main driver for ChronoSquad game logic.

    Single control point:
    - Owns ChronoSphere (collection of timelines)
    - In start(), finds TimelineInitializer and creates original timeline
    - Finds TimelineController and binds it
    - Drives time updates each frame
    - Handles timeline switching
    """

    _instance: ChronosphereController | None = None

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)
        self._chronosphere = ChronoSphere()
        self._timeline_controller: TimelineController | None = None
        self._initialized = False
        ChronosphereController._instance = self

    @classmethod
    def instance(cls) -> ChronosphereController | None:
        """Get singleton instance of ChronosphereController."""
        return cls._instance

    @property
    def chronosphere(self) -> ChronoSphere:
        return self._chronosphere

    @property
    def current_timeline(self) -> Timeline | None:
        return self._chronosphere.current_timeline

    @property
    def timeline_controller(self) -> TimelineController | None:
        return self._timeline_controller

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def start(self) -> None:
        """Initialize everything on start."""
        if self._initialized:
            return

        log.info("[ChronosphereController] Starting initialization...")
        self._initialize()
        self._initialized = True
        log.info("[ChronosphereController] Initialization complete")

    def _initialize(self) -> None:
        """Find components and create original timeline."""
        from .timeline_initializer import TimelineInitializer
        from .timeline_controller import TimelineController

        if self._scene is None:
            log.warning("[ChronosphereController] No scene available")
            return

        # Find TimelineInitializer
        log.info("[ChronosphereController] Looking for TimelineInitializer...")
        initializer = self._find_component(TimelineInitializer)
        if initializer is None:
            log.warning("[ChronosphereController] TimelineInitializer not found")
            return
        log.info(f"[ChronosphereController] Found TimelineInitializer on entity '{initializer.entity.name}'")

        # Find TimelineController
        log.info("[ChronosphereController] Looking for TimelineController...")
        self._timeline_controller = self._find_component(TimelineController)
        if self._timeline_controller is not None:
            log.info(f"[ChronosphereController] Found TimelineController on entity '{self._timeline_controller.entity.name}'")
        else:
            log.warning("[ChronosphereController] TimelineController not found")

        # Create timeline from scene
        log.info("[ChronosphereController] Creating timeline from scene...")
        timeline = initializer.create_timeline(self._scene)
        log.info(f"[ChronosphereController] Created timeline '{timeline.name}' with {len(timeline.objects)} objects")

        # Register in chronosphere
        log.info("[ChronosphereController] Registering timeline in ChronoSphere...")
        self._chronosphere.add_timeline(timeline)
        self._chronosphere.set_current_timeline(timeline)
        log.info(f"[ChronosphereController] Timeline '{timeline.name}' set as current")

        # Bind callbacks
        self._chronosphere.on_current_changed(self._on_current_timeline_changed)

        # Bind timeline controller
        if self._timeline_controller is not None:
            log.info("[ChronosphereController] Binding TimelineController to timeline...")
            self._timeline_controller.bind(timeline)
            log.info("[ChronosphereController] TimelineController bound")

    def _find_component(self, component_type: type):
        """Find component of given type in scene."""
        for entity in self._scene.entities:
            comp = entity.get_component(component_type)
            if comp is not None:
                return comp
        return None

    def _on_current_timeline_changed(self, timeline: Timeline) -> None:
        """Handle timeline switch - rebind controller."""
        if self._timeline_controller is not None:
            self._timeline_controller.rebind(timeline)

    # =========================================================================
    # Runtime
    # =========================================================================

    def update(self, dt: float) -> None:
        """Main update - drives time forward."""
        self._chronosphere.update(dt)

    # =========================================================================
    # Time control
    # =========================================================================

    def pause(self) -> None:
        """Toggle pause."""
        self._chronosphere.pause()

    def set_pause(self, paused: bool) -> None:
        """Set pause state."""
        self._chronosphere.set_pause(paused)

    def set_time_multiplier(self, multiplier: float) -> None:
        """Set time speed (1.0 = normal, -1.0 = reverse)."""
        self._chronosphere.set_target_time_multiplier(multiplier)

    def time_reverse(self) -> None:
        """Reverse time direction."""
        self._chronosphere.time_reverse_immediate()

    # =========================================================================
    # Timeline management
    # =========================================================================

    def create_branch(self, name: str | None = None) -> Timeline:
        """
        Create a branch (copy) of current timeline.

        The new timeline becomes current, and TimelineController rebinds.
        """
        new_timeline = self._chronosphere.create_copy_of_current(name)
        self._chronosphere.set_current_timeline(new_timeline)
        return new_timeline

    def switch_timeline(self, timeline: Timeline) -> None:
        """Switch to a different timeline."""
        self._chronosphere.set_current_timeline(timeline)

    def switch_timeline_by_name(self, name: str) -> None:
        """Switch to timeline by name."""
        self._chronosphere.set_current_by_name(name)
