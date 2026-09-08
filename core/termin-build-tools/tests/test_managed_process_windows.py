from __future__ import annotations

from contextlib import contextmanager
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any

import pytest

from termin_build.managed_process import (
    ManagedProcess,
    ManagedProcessCleanupError,
    _WindowsJobOwner,
    run_managed_process,
)
from termin_build.windows_job import CREATE_SUSPENDED


FIXTURE = Path(__file__).with_name("fixtures") / "process_tree_fixture.py"


class _FakeProcess:
    pid = 42
    _handle = 84
    returncode: int | None = None

    def __init__(self, events: list[object]) -> None:
        self._events = events

    def poll(self) -> int | None:
        self._events.append("poll")
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self._events.append(("wait", timeout))
        self.returncode = 1
        return self.returncode


class _FakeWindowsJobApi:
    def __init__(self, events: list[object], *, active_counts: list[int] | None = None) -> None:
        self.events = events
        self.active_counts = list(active_counts or [0])
        self.assign_error: BaseException | None = None
        self.resume_error: BaseException | None = None

    def create_kill_on_close_job(self) -> int:
        self.events.append("create-kill-on-close-job")
        return 21

    def assign_process(self, job_handle: int, process_handle: int) -> None:
        self.events.append(("assign", job_handle, process_handle))
        if self.assign_error is not None:
            raise self.assign_error

    def resume_process(self, process_id: int) -> None:
        self.events.append(("resume", process_id))
        if self.resume_error is not None:
            raise self.resume_error

    def active_process_count(self, job_handle: int) -> int:
        self.events.append(("active", job_handle))
        if len(self.active_counts) > 1:
            return self.active_counts.pop(0)
        return self.active_counts[0]

    def terminate_job(self, job_handle: int, exit_code: int) -> None:
        self.events.append(("terminate-job", job_handle, exit_code))

    def terminate_process(self, process_handle: int, exit_code: int) -> None:
        self.events.append(("terminate-process", process_handle, exit_code))

    def close_handle(self, handle: int) -> None:
        self.events.append(("close", handle))


def _start_fake_windows_job(
    api: _FakeWindowsJobApi,
    events: list[object],
    **popen_options: Any,
) -> tuple[_FakeProcess, _WindowsJobOwner]:
    def fake_popen(command: list[str], **options: object) -> _FakeProcess:
        events.append(("popen", command, options))
        return _FakeProcess(events)

    process, owner = _WindowsJobOwner.start(
        ["wrapper.exe"],
        kill_timeout_seconds=0.0,
        api=api,
        popen_factory=fake_popen,
        **popen_options,
    )
    return process, owner


def test_windows_job_assigns_suspended_process_before_resume() -> None:
    events: list[object] = []
    api = _FakeWindowsJobApi(events, active_counts=[1, 0])

    process, owner = _start_fake_windows_job(
        api,
        events,
        creationflags=0x08000000,
        cwd=Path("workspace"),
    )
    owner.close()

    popen_event = events[1]
    assert popen_event[0] == "popen"
    assert popen_event[2]["creationflags"] == 0x08000000 | CREATE_SUSPENDED
    assert events.index(("assign", 21, 84)) < events.index(("resume", 42))
    assert ("terminate-job", 21, 1) in events
    assert events[-2:] == [("close", 21), "poll"]
    assert process.returncode is None


def test_windows_job_assignment_failure_kills_suspended_leader() -> None:
    events: list[object] = []
    api = _FakeWindowsJobApi(events)
    api.assign_error = OSError("assignment rejected")

    with pytest.raises(OSError, match="assignment rejected"):
        _start_fake_windows_job(api, events)

    assert ("resume", 42) not in events
    assert ("terminate-process", 84, 1) in events
    assert ("close", 21) in events


def test_windows_job_resume_failure_terminates_assigned_tree() -> None:
    events: list[object] = []
    api = _FakeWindowsJobApi(events)
    api.resume_error = OSError("resume rejected")

    with pytest.raises(OSError, match="resume rejected"):
        _start_fake_windows_job(api, events)

    assert ("terminate-job", 21, 1) in events
    assert ("terminate-process", 84, 1) not in events
    assert ("close", 21) in events


def test_windows_job_cleanup_failure_is_logged_and_raised(capsys) -> None:
    events: list[object] = []
    api = _FakeWindowsJobApi(events, active_counts=[1, 1])
    process, owner = _start_fake_windows_job(api, events)
    managed = ManagedProcess(
        process,
        owner=owner,
        process_group_id=None,
        handle_signals=False,
    )

    with pytest.raises(ManagedProcessCleanupError, match="remained active"):
        managed.close()

    assert "ERROR: managed process cleanup failed" in capsys.readouterr().err
    assert ("close", 21) in events


def _fixture_command(state_path: Path, *options: str) -> list[str]:
    return [
        sys.executable,
        str(FIXTURE),
        "wrapper",
        str(state_path),
        *options,
    ]


def _wait_for_json(path: Path, timeout: float = 10.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(0.02)
    raise AssertionError(f"timed out waiting for process-tree state: {path}")


def _windows_pid_exists(process_id: int) -> bool:
    synchronize = 0x00100000
    wait_timeout = 0x00000102
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.OpenProcess(synchronize, False, process_id)
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == wait_timeout
    finally:
        kernel32.CloseHandle(handle)


def _wait_for_windows_pid_exit(process_id: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while _windows_pid_exists(process_id) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not _windows_pid_exists(process_id)


@contextmanager
def _emergency_windows_cleanup(state_path: Path):
    try:
        yield
    finally:
        if state_path.is_file():
            state = _wait_for_json(state_path, timeout=0.1)
            wrapper_pid = int(state["wrapper_pid"])
            grandchild_pid = int(state["grandchild_pid"])
            if _windows_pid_exists(wrapper_pid):
                subprocess.run(
                    ["taskkill", "/pid", str(wrapper_pid), "/t", "/f"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif _windows_pid_exists(grandchild_pid):
                subprocess.run(
                    ["taskkill", "/pid", str(grandchild_pid), "/f"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )


@pytest.mark.skipif(os.name != "nt", reason="requires real Windows Job Objects")
def test_windows_exception_cleans_wrapper_and_grandchild(tmp_path: Path) -> None:
    state_path = tmp_path / "exception-tree.json"
    with _emergency_windows_cleanup(state_path):
        with pytest.raises(RuntimeError, match="forced failure"):
            with ManagedProcess.start(_fixture_command(state_path)):
                state = _wait_for_json(state_path)
                raise RuntimeError("forced failure")
        _wait_for_windows_pid_exit(int(state["grandchild_pid"]))


@pytest.mark.skipif(os.name != "nt", reason="requires real Windows Job Objects")
def test_windows_timeout_preserves_output_and_cleans_tree(tmp_path: Path) -> None:
    state_path = tmp_path / "timeout-tree.json"
    with _emergency_windows_cleanup(state_path):
        with pytest.raises(subprocess.TimeoutExpired) as raised:
            run_managed_process(
                _fixture_command(state_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=0.5,
            )
        state = _wait_for_json(state_path)
        assert "PROCESS_TREE_READY" in raised.value.stdout
        _wait_for_windows_pid_exit(int(state["grandchild_pid"]))


@pytest.mark.skipif(os.name != "nt", reason="requires real Windows Job Objects")
def test_windows_leader_exit_still_cleans_grandchild(tmp_path: Path) -> None:
    state_path = tmp_path / "leader-exit-tree.json"
    with _emergency_windows_cleanup(state_path):
        result = run_managed_process(
            _fixture_command(state_path, "--exit-after-start"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5.0,
        )
        state = _wait_for_json(state_path)
        assert result.returncode == 0
        assert "PROCESS_TREE_READY" in result.stdout
        _wait_for_windows_pid_exit(int(state["grandchild_pid"]))


@pytest.mark.skipif(os.name != "nt", reason="requires real Windows Job Objects")
def test_windows_parent_termination_closes_job_and_cleans_tree(tmp_path: Path) -> None:
    state_path = tmp_path / "terminated-supervisor-tree.json"
    ready_path = state_path.with_suffix(".ready")
    supervisor = subprocess.Popen(
        [sys.executable, str(FIXTURE), "supervisor", str(state_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    with _emergency_windows_cleanup(state_path):
        deadline = time.monotonic() + 10.0
        while not ready_path.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready_path.exists()
        state = _wait_for_json(state_path)
        supervisor.terminate()
        supervisor.wait(timeout=10.0)
        _wait_for_windows_pid_exit(int(state["grandchild_pid"]))


@pytest.mark.skipif(os.name != "nt", reason="requires a real Windows console")
def test_windows_console_break_cleans_managed_tree(tmp_path: Path) -> None:
    state_path = tmp_path / "console-break-supervisor-tree.json"
    ready_path = state_path.with_suffix(".ready")
    supervisor = subprocess.Popen(
        [sys.executable, str(FIXTURE), "supervisor", str(state_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    with _emergency_windows_cleanup(state_path):
        deadline = time.monotonic() + 10.0
        while not ready_path.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready_path.exists()
        state = _wait_for_json(state_path)
        supervisor.send_signal(signal.CTRL_BREAK_EVENT)
        output, _ = supervisor.communicate(timeout=10.0)
        assert supervisor.returncode != 0, output
        _wait_for_windows_pid_exit(int(state["grandchild_pid"]))
