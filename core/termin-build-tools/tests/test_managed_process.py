from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from termin_build.managed_process import (
    ManagedProcess,
    process_group_exists,
    run_managed_process,
)


pytestmark = pytest.mark.skipif(
    os.name != "posix",
    reason="managed process groups currently require POSIX",
)

FIXTURE = Path(__file__).with_name("fixtures") / "process_tree_fixture.py"


def _fixture_command(state_path: Path, *options: str) -> list[str]:
    return [
        sys.executable,
        str(FIXTURE),
        "wrapper",
        str(state_path),
        *options,
    ]


def _wait_for_json(path: Path, timeout: float = 5.0) -> dict[str, int]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(0.02)
            continue
        return {key: int(value) for key, value in payload.items()}
    raise AssertionError(f"timed out waiting for process-tree state: {path}")


def _wait_for_path(path: Path, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not path.exists():
        raise AssertionError(f"timed out waiting for path: {path}")


def _wait_for_group_exit(process_group_id: int, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while process_group_exists(process_group_id) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not process_group_exists(process_group_id)


@contextmanager
def _emergency_group_cleanup(state_path: Path):
    try:
        yield
    finally:
        try:
            state = _wait_for_json(state_path, timeout=0.1)
        except AssertionError:
            state = None
        if state is not None:
            process_group_id = state["process_group_id"]
            if process_group_exists(process_group_id):
                os.killpg(process_group_id, signal.SIGKILL)
                _wait_for_group_exit(process_group_id)


def test_context_exception_cleans_wrapper_and_grandchild(tmp_path: Path) -> None:
    state_path = tmp_path / "exception-tree.json"
    state: dict[str, int]

    with _emergency_group_cleanup(state_path):
        with pytest.raises(RuntimeError, match="forced managed-process failure"):
            with ManagedProcess.start(
                _fixture_command(state_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            ):
                state = _wait_for_json(state_path)
                raise RuntimeError("forced managed-process failure")

        _wait_for_group_exit(state["process_group_id"])


def test_timeout_cleans_tree_and_preserves_captured_output(tmp_path: Path) -> None:
    state_path = tmp_path / "timeout-tree.json"

    with _emergency_group_cleanup(state_path):
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
        _wait_for_group_exit(state["process_group_id"])


def test_normal_wrapper_exit_still_cleans_grandchild(tmp_path: Path) -> None:
    state_path = tmp_path / "exited-wrapper-tree.json"

    with _emergency_group_cleanup(state_path):
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
        _wait_for_group_exit(state["process_group_id"])


def test_cleanup_escalates_when_grandchild_ignores_sigterm(tmp_path: Path) -> None:
    state_path = tmp_path / "stubborn-tree.json"

    with _emergency_group_cleanup(state_path):
        with ManagedProcess.start(
            _fixture_command(state_path, "--ignore-sigterm"),
            terminate_timeout_seconds=0.1,
            kill_timeout_seconds=2.0,
        ) as managed:
            state = _wait_for_json(state_path)

        assert managed.process.returncode == -signal.SIGTERM
        _wait_for_group_exit(state["process_group_id"])


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_parent_signal_cleans_managed_tree(tmp_path: Path, signum: int) -> None:
    state_path = tmp_path / f"signal-{signum}-tree.json"
    ready_path = state_path.with_suffix(".ready")
    supervisor = subprocess.Popen(
        [sys.executable, str(FIXTURE), "supervisor", str(state_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    with _emergency_group_cleanup(state_path):
        try:
            _wait_for_path(ready_path)
            state = _wait_for_json(state_path)
            supervisor.send_signal(signum)
            output, _ = supervisor.communicate(timeout=10.0)
        finally:
            if supervisor.poll() is None:
                supervisor.kill()
                supervisor.wait(timeout=5.0)

        assert supervisor.returncode != 0, output
        _wait_for_group_exit(state["process_group_id"])
