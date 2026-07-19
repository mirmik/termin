"""Main-thread SIGINT ownership for the interactive editor host."""

from __future__ import annotations

import logging
import signal
from collections.abc import Callable
from types import FrameType


_logger = logging.getLogger(__name__)
SignalHandler = Callable[[int, FrameType | None], None]


class TerminalInterruptController:
    """Turn SIGINT into a polled shutdown request without raising in callbacks."""

    def __init__(self) -> None:
        self._requested = False
        self._installed_handler: SignalHandler = self._handle_sigint
        self._previous_handler: signal.Handlers | SignalHandler | int | None = None
        self._installed = False

    def install(self) -> None:
        if self._installed:
            raise RuntimeError("terminal interrupt controller is already installed")
        self._previous_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._installed_handler)
        self._installed = True

    def consume(self) -> bool:
        requested = self._requested
        self._requested = False
        return requested

    def close(self) -> None:
        if not self._installed:
            return
        current = signal.getsignal(signal.SIGINT)
        if current is self._installed_handler:
            signal.signal(signal.SIGINT, self._previous_handler)
        else:
            _logger.warning(
                "SIGINT handler ownership changed while the editor was running; "
                "leaving the replacement handler intact"
            )
        self._installed = False
        self._previous_handler = None

    def _handle_sigint(self, signum: int, frame: FrameType | None) -> None:
        del frame
        if signum == signal.SIGINT:
            self._requested = True

