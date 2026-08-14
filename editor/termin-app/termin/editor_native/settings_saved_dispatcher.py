"""Failure-isolated fan-out for native editor settings updates."""

from __future__ import annotations

import logging
from collections.abc import Callable


_logger = logging.getLogger(__name__)


class SettingsSavedDispatcher:
    def __init__(self) -> None:
        self.handlers: list[Callable[[], None]] = []

    def notify(self, _snapshot: object) -> None:
        for handler in tuple(self.handlers):
            try:
                handler()
            except Exception:
                _logger.exception("Editor settings change handler failed")
