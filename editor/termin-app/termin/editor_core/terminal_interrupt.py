"""Main-thread SIGINT ownership for the interactive editor host."""

from __future__ import annotations

import logging
import signal
import socket
import threading
from collections.abc import Callable
from types import FrameType


_logger = logging.getLogger(__name__)
SignalHandler = Callable[[int, FrameType | None], None]


class TerminalInterruptController:
    """Turn SIGINT into a polled shutdown request without raising in callbacks."""

    def __init__(self, wake: Callable[[], None] | None = None) -> None:
        self._requested = False
        self._installed_handler: SignalHandler = self._handle_sigint
        self._previous_handler: signal.Handlers | SignalHandler | int | None = None
        self._installed = False
        self._wake = wake
        self._signal_reader: socket.socket | None = None
        self._signal_writer: socket.socket | None = None
        self._signal_thread: threading.Thread | None = None
        self._previous_wakeup_fd = -1

    def _relay_signals(self) -> None:
        reader = self._signal_reader
        assert reader is not None
        try:
            while True:
                signals = reader.recv(128)
                if not signals or 0 in signals:
                    return
                if self._wake is not None:
                    self._wake()
        except Exception:
            _logger.exception("Editor signal wake relay failed")

    def install(self) -> None:
        if self._installed:
            raise RuntimeError("terminal interrupt controller is already installed")
        self._previous_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._installed_handler)
        if self._wake is not None:
            reader = writer = None
            wakeup_installed = False
            try:
                reader, writer = socket.socketpair()
                writer.setblocking(False)
                self._previous_wakeup_fd = signal.set_wakeup_fd(writer.fileno())
                wakeup_installed = True
                self._signal_reader, self._signal_writer = reader, writer
                self._signal_thread = threading.Thread(
                    target=self._relay_signals, name="editor-signal-wake", daemon=True,
                )
                self._signal_thread.start()
            except Exception:
                signal.signal(signal.SIGINT, self._previous_handler)
                if wakeup_installed:
                    signal.set_wakeup_fd(self._previous_wakeup_fd)
                if reader is not None:
                    reader.close()
                if writer is not None:
                    writer.close()
                self._signal_reader = self._signal_writer = None
                self._signal_thread = None
                _logger.exception("Failed to install editor signal wake relay")
                raise
        self._installed = True

    def consume(self) -> bool:
        requested = self._requested
        self._requested = False
        return requested

    def close(self) -> None:
        if not self._installed:
            return
        if self._signal_writer is not None:
            signal.set_wakeup_fd(self._previous_wakeup_fd)
            # Shutdown the stream instead of writing a sentinel into a possibly
            # full nonblocking signal socket. The reader wakes on EOF.
            self._signal_writer.shutdown(socket.SHUT_WR)
            if self._signal_thread is not None:
                self._signal_thread.join()
            self._signal_writer.close()
            self._signal_reader.close()
            self._signal_writer = self._signal_reader = None
            self._signal_thread = None
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

