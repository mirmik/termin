"""
ActionComponent - base class for action components.

Action components are attached to entities with ObjectController.
They provide abilities and handle user input to trigger them.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from termin._native import log
from termin.geombase import Vec3
from termin.visualization.core.python_component import PythonComponent, InputComponent

if TYPE_CHECKING:
    from termin.chronosquad.core import ObjectOfTimeline, Ability
    from .object_controller import ObjectController


class ActionSpecType(Enum):
    """Type of action visualization."""
    LINE = auto()           # Line from actor to target point
    CIRCLE = auto()         # Circle area around target point
    CONE = auto()           # Cone from actor in direction
    PARABOLA = auto()       # Parabolic trajectory (grenades)
    NONE = auto()           # No visualization


@dataclass
class ActionSpec:
    """
    Specification for action visualization.

    Describes what to draw and how.
    """
    spec_type: ActionSpecType = ActionSpecType.LINE

    # Common parameters
    color: tuple[float, float, float, float] = (0.0, 0.5, 1.0, 0.8)  # RGBA
    line_width: float = 0.05

    # For LINE type
    # Start position is taken from actor, end from cursor

    # For CIRCLE type
    radius: float = 1.0

    # For CONE type
    angle: float = 45.0  # degrees
    length: float = 10.0

    # For PARABOLA type
    gravity: float = 9.8
    initial_speed: float = 10.0

    # Constraints
    max_distance: float = 0.0  # 0 = unlimited
    require_navmesh: bool = False  # Target must be on navmesh
    require_line_of_sight: bool = False  # Target must be visible


@dataclass
class ClickInfo:
    """
    Information about a click event.

    Passed to on_apply() when user clicks.
    """
    world_position: Vec3
    screen_position: tuple[float, float] = (0.0, 0.0)
    target_object: ObjectOfTimeline | None = None
    hit_normal: Vec3 = field(default_factory=lambda: Vec3(0, 0, 1))
    frame_name: str = ""  # For ReferencedPoint


class ActionComponent(InputComponent):
    """
    Base class for action components.

    Action components are attached to entities that have ObjectController.
    They:
    1. Create and register an Ability with the ObjectOfTimeline
    2. Handle activation (hotkey/icon click)
    3. Handle apply (click) by executing the ability

    Subclasses must implement:
    - create_ability() - create the Ability instance
    - get_spec() - return visualization spec
    - on_apply() - handle click and execute ability
    """

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)
        self._object_controller: ObjectController | None = None
        self._ability: Ability | None = None
        self._is_active: bool = False

    # =========================================================================
    # Called by ObjectController
    # =========================================================================

    def set_object_controller(self, controller: ObjectController) -> None:
        """Set the ObjectController. Called by ObjectController during initialization."""
        self._object_controller = controller

    def init_ability(self) -> Ability | None:
        """Create and store ability. Called by ObjectController after binding."""
        self._ability = self.create_ability()
        return self._ability

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def object_controller(self) -> ObjectController | None:
        return self._object_controller

    @property
    def chrono_object(self) -> ObjectOfTimeline | None:
        """Get the ObjectOfTimeline this action operates on."""
        if self._object_controller is None:
            return None
        return self._object_controller.chrono_object

    @property
    def ability(self) -> Ability | None:
        return self._ability

    @property
    def is_active(self) -> bool:
        return self._is_active

    # =========================================================================
    # Abstract methods (implement in subclasses)
    # =========================================================================

    @abstractmethod
    def create_ability(self) -> Ability | None:
        """Create the Ability instance for this action."""
        pass

    @abstractmethod
    def get_spec(self) -> ActionSpec:
        """Return visualization spec for this action."""
        pass

    @abstractmethod
    def on_apply(self, click: ClickInfo) -> bool:
        """
        Handle click and execute ability.

        Returns True if action was successfully applied.
        """
        pass

    # =========================================================================
    # Activation/Cancellation
    # =========================================================================

    def can_activate(self) -> bool:
        """Check if action can be activated."""
        if self._ability is None:
            return False
        chrono_obj = self.chrono_object
        if chrono_obj is None:
            return False
        timeline = chrono_obj.timeline
        if timeline is None:
            return False
        return self._ability.can_use(timeline, chrono_obj.ability_list)

    def activate(self) -> None:
        """Activate this action."""
        from .action_server_component import ActionServerComponent

        if not self.can_activate():
            log.info(f"[{self.type_name()}] Cannot activate (on cooldown or no ability)")
            return

        server = ActionServerComponent.instance()
        if server is None:
            log.warning(f"[{self.type_name()}] ActionServerComponent not found")
            return

        self._is_active = True
        server.charge(self)
        log.info(f"[{self.type_name()}] Activated")

    def cancel(self) -> None:
        """Cancel this action."""
        from .action_server_component import ActionServerComponent

        self._is_active = False
        server = ActionServerComponent.instance()
        if server is not None and server.current_action is self:
            server.discharge()
        log.info(f"[{self.type_name()}] Cancelled")

    # =========================================================================
    # UI helpers
    # =========================================================================

    def get_cooldown_percent(self) -> float:
        """Get cooldown progress (0-100)."""
        if self._ability is None:
            return 100.0
        chrono_obj = self.chrono_object
        if chrono_obj is None:
            return 100.0
        return chrono_obj.ability_list.get_cooldown_percent(type(self._ability))

    def get_tooltip(self) -> str:
        """Get tooltip text for UI. Override in subclasses."""
        return ""

    def on_key(self, event) -> None:
        """Called when action icon/key is pressed."""
        print(f"[{self.type_name()}] Action icon/key pressed")
        pass
        
        