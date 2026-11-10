from __future__ import annotations

import signal
import socket
import threading

from termin.editor_core.terminal_interrupt import TerminalInterruptController


def test_terminal_interrupt_becomes_consumable_shutdown_request() -> None:
    previous = signal.getsignal(signal.SIGINT)
    controller = TerminalInterruptController()
    controller.install()
    try:
        assert not controller.consume()
        signal.raise_signal(signal.SIGINT)
        assert controller.consume()
        assert not controller.consume()
    finally:
        controller.close()

    assert signal.getsignal(signal.SIGINT) is previous


def test_terminal_interrupt_does_not_overwrite_replacement_handler() -> None:
    previous = signal.getsignal(signal.SIGINT)
    controller = TerminalInterruptController()
    controller.install()

    def replacement(signum, frame) -> None:
        del signum, frame

    try:
        signal.signal(signal.SIGINT, replacement)
        controller.close()
        assert signal.getsignal(signal.SIGINT) is replacement
    finally:
        signal.signal(signal.SIGINT, previous)


def test_terminal_signal_socket_wakes_without_waiting_for_python_handler() -> None:
    wake = threading.Event()
    controller = TerminalInterruptController(wake.set)
    controller.install()
    try:
        # Simulate the low-level signal handler's byte. The relay must wake a
        # blocked owner even before Python gets to invoke _handle_sigint.
        controller._signal_writer.send(bytes([signal.SIGINT]))
        assert wake.wait(timeout=2.0)
        assert not controller.consume()
        wake.clear()
        signal.raise_signal(signal.SIGINT)
        assert wake.wait(timeout=2.0)
        assert controller.consume()
    finally:
        relay = controller._signal_thread
        controller.close()
    assert not relay.is_alive()
    controller.close()


def test_terminal_signal_bridge_restores_previous_wakeup_fd() -> None:
    reader, writer = socket.socketpair()
    writer.setblocking(False)
    previous_fd = signal.set_wakeup_fd(writer.fileno())
    controller = TerminalInterruptController(lambda: None)
    try:
        controller.install()
        controller.close()
        restored = signal.set_wakeup_fd(-1)
        assert restored == writer.fileno()
    finally:
        controller.close()
        signal.set_wakeup_fd(previous_fd)
        reader.close()
        writer.close()

