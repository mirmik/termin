"""Compatibility wrapper for the legacy Qt editor SpaceMouse controller."""

from __future__ import annotations

from termin.editor_core.spacemouse_controller import SpaceMouseController as _CoreSpaceMouseController


class SpaceMouseController(_CoreSpaceMouseController):
    """Qt editor wrapper: keep event-driven QSocketNotifier behavior."""

    def __init__(self):
        super().__init__(use_qt_notifier=True)


__all__ = ["SpaceMouseController"]
