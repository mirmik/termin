"""Readiness relay tests use a real socket, without a device or spacenavd."""

import ctypes
import queue
import socket
import threading

import pytest

from termin.editor_core import spacemouse_controller as module


class SocketSpnav:
    def __init__(self):
        self.reader, self.writer = socket.socketpair()
        self.reader.setblocking(False)
        self.poll_threads = []
        self.closed = False
        self.poll_error = False

    def spnav_open(self):
        return 0

    def spnav_fd(self):
        return self.reader.fileno()

    def spnav_close(self):
        self.closed = True
        self.reader.close()

    def spnav_poll_event(self, pointer):
        self.poll_threads.append(threading.get_ident())
        if self.poll_error:
            return -1
        try:
            data = self.reader.recv(1)
        except BlockingIOError:
            return 0
        if not data:
            return 0  # Some library versions leave EOF descriptors open.
        event = ctypes.cast(pointer, ctypes.POINTER(module._SpnavEvent)).contents
        event.type = module.SPNAV_EVENT_BUTTON
        event.button.press = 0
        return 1


@pytest.fixture
def controller(monkeypatch):
    lib = SocketSpnav()
    monkeypatch.setattr(module, "_get_libspnav", lambda: lib)
    mouse = module.SpaceMouseController()
    try:
        yield mouse, lib
    finally:
        mouse.close()
        lib.reader.close()
        lib.writer.close()


def test_input_wakes_once_until_owner_drains_and_rearms(controller):
    mouse, lib = controller
    notifications = queue.Queue()
    mouse.set_wakeup(lambda: notifications.put(threading.get_ident()))
    assert mouse.open(None, lambda: None)
    owner = threading.get_ident()
    lib.writer.sendall(b"abc")
    assert notifications.get(timeout=2) != owner
    assert lib.poll_threads == []
    with pytest.raises(queue.Empty):
        notifications.get(timeout=0.05)
    mouse.poll()
    assert lib.poll_threads and set(lib.poll_threads) == {owner}
    lib.writer.sendall(b"d")
    assert notifications.get(timeout=2) != owner
    mouse.poll()


@pytest.mark.parametrize("pending", [False, True])
def test_close_stops_relay_waiting_on_socket_or_owner_ack(controller, pending):
    mouse, lib = controller
    notified = threading.Event()
    mouse.set_wakeup(notified.set)
    mouse.open(None, lambda: None)
    relay = mouse._wake_thread
    if pending:
        lib.writer.sendall(b"x")
        assert notified.wait(2)
    mouse.close()
    assert not relay.is_alive()
    assert lib.closed
    assert not mouse.is_open
    mouse.close()


def test_daemon_eof_wakes_owner_and_closes_without_readiness_spin(controller):
    mouse, lib = controller
    notified = threading.Event()
    mouse.set_wakeup(notified.set)
    mouse.open(None, lambda: None)
    relay = mouse._wake_thread
    lib.writer.close()
    assert notified.wait(2)
    relay.join(timeout=2)
    assert not relay.is_alive()
    assert lib.poll_threads == []
    mouse.poll()
    assert not mouse.is_open
    assert lib.closed


def test_negative_poll_result_closes_connection(controller):
    mouse, lib = controller
    mouse.open(None, lambda: None)
    lib.poll_error = True
    mouse.poll()
    assert len(lib.poll_threads) == 1
    assert not mouse.is_open
    assert lib.closed


def test_relay_setup_failure_rolls_back_open_connection(controller, monkeypatch):
    mouse, lib = controller
    mouse.set_wakeup(lambda: None)

    def fail_socketpair():
        raise OSError("test socket allocation failure")

    monkeypatch.setattr(module.socket, "socketpair", fail_socketpair)
    with pytest.raises(OSError, match="allocation failure"):
        mouse.open(None, lambda: None)
    assert not mouse.is_open
    assert lib.closed
    assert mouse._device_socket is None
    assert mouse._wake_thread is None
