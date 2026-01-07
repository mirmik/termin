"""
ActionServerComponent - manages active action state.

Place on scene to enable action system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin._native import log
from termin.visualization.core.python_component import PythonComponent

if TYPE_CHECKING:
    from .action_component import ActionComponent, ActionSpec, ClickInfo


class ActionServerComponent(PythonComponent):
    """
    Component that manages the currently active action.

    Must be present in scene for action system to work.
    ActionComponents find this component and use it to activate/apply actions.
    """

    _instance: ActionServerComponent | None = None

    @classmethod
    def instance(cls) -> ActionServerComponent | None:
        return cls._instance

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)
        self._current_action: ActionComponent | None = None

    def start(self) -> None:
        ActionServerComponent._instance = self
        log.info("[ActionServerComponent] Started")

    def on_destroy(self) -> None:
        if ActionServerComponent._instance is self:
            ActionServerComponent._instance = None
        log.info("[ActionServerComponent] Destroyed")

    @property
    def current_action(self) -> ActionComponent | None:
        return self._current_action

    @property
    def current_spec(self) -> ActionSpec | None:
        if self._current_action is None:
            return None
        return self._current_action.get_spec()

    def is_charged(self) -> bool:
        return self._current_action is not None

    def charge(self, action: ActionComponent) -> None:
        """Set active action. Cancels previous if any."""
        if self._current_action is not None and self._current_action is not action:
            self._current_action.cancel()
        self._current_action = action

    def discharge(self) -> None:
        """Clear active action."""
        self._current_action = None

    def apply_click(self, click: ClickInfo) -> bool:
        """Apply click to current action."""
        if self._current_action is None:
            return False

        action = self._current_action
        success = action.on_apply(click)

        # Always cancel after apply
        action.cancel()

        return success
