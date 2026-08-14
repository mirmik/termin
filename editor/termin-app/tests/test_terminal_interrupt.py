from __future__ import annotations

import signal

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

