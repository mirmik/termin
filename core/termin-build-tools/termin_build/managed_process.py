"""POSIX process-group ownership for repository process-smoke commands."""

from __future__ import annotations

from collections.abc import Sequence
import os
import signal
import subprocess
import sys
import threading
import time
from types import FrameType
from typing import Any


DEFAULT_TERMINATE_TIMEOUT_SECONDS = 5.0
DEFAULT_KILL_TIMEOUT_SECONDS = 5.0
_GROUP_POLL_INTERVAL_SECONDS = 0.05
_COMMUNICATE_POLL_INTERVAL_SECONDS = 0.1


class ManagedProcessCleanupError(RuntimeError):
    """Raised when a managed process group cannot be confirmed dead."""


def process_group_exists(process_group_id: int) -> bool:
    """Return whether a POSIX process group still has at least one member."""
    if os.name != "posix":
        raise NotImplementedError("POSIX process groups are unavailable on this host")
    if process_group_id <= 0:
        raise ValueError("process_group_id must be positive")
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError as exc:
        raise ManagedProcessCleanupError(
            f"permission denied while probing process group {process_group_id}"
        ) from exc
    return True


class ManagedProcess:
    """Own one POSIX session and guarantee bounded process-group cleanup."""

    def __init__(
        self,
        process: subprocess.Popen[Any],
        *,
        terminate_timeout_seconds: float,
        kill_timeout_seconds: float,
        handle_signals: bool,
    ) -> None:
        self.process = process
        self.process_group_id = process.pid
        self._terminate_timeout_seconds = terminate_timeout_seconds
        self._kill_timeout_seconds = kill_timeout_seconds
        self._handle_signals = handle_signals
        self._previous_signal_handlers: dict[int, Any] = {}
        self._handling_signal = False

    @classmethod
    def start(
        cls,
        command: Sequence[str],
        *,
        terminate_timeout_seconds: float = DEFAULT_TERMINATE_TIMEOUT_SECONDS,
        kill_timeout_seconds: float = DEFAULT_KILL_TIMEOUT_SECONDS,
        handle_signals: bool = True,
        **popen_options: Any,
    ) -> ManagedProcess:
        """Start ``command`` as the leader of a newly owned POSIX session."""
        if os.name != "posix":
            raise NotImplementedError(
                "ManagedProcess currently requires POSIX process groups"
            )
        if terminate_timeout_seconds < 0:
            raise ValueError("terminate_timeout_seconds must be non-negative")
        if kill_timeout_seconds < 0:
            raise ValueError("kill_timeout_seconds must be non-negative")
        conflicting_options = {"start_new_session", "process_group"} & popen_options.keys()
        if conflicting_options:
            joined = ", ".join(sorted(conflicting_options))
            raise TypeError(f"ManagedProcess owns these Popen options: {joined}")

        process = subprocess.Popen(
            list(command),
            start_new_session=True,
            **popen_options,
        )
        managed = cls(
            process,
            terminate_timeout_seconds=terminate_timeout_seconds,
            kill_timeout_seconds=kill_timeout_seconds,
            handle_signals=handle_signals,
        )
        try:
            managed._install_signal_handlers()
        except BaseException:
            managed.close()
            raise
        return managed

    def __enter__(self) -> ManagedProcess:
        return self

    def __exit__(self, *_exc_info: object) -> bool:
        self.close()
        return False

    def close(self) -> None:
        """Terminate every remaining group member and restore signal handlers."""
        try:
            self._terminate_process_group()
        finally:
            self._restore_signal_handlers()

    def _terminate_process_group(self) -> None:
        self.process.poll()
        if not process_group_exists(self.process_group_id):
            return

        self._send_group_signal(signal.SIGTERM)
        if self._wait_for_group_exit(self._terminate_timeout_seconds):
            return

        self._send_group_signal(signal.SIGKILL)
        if self._wait_for_group_exit(self._kill_timeout_seconds):
            return

        raise ManagedProcessCleanupError(
            f"process group {self.process_group_id} survived SIGTERM and SIGKILL"
        )

    def _send_group_signal(self, signum: int) -> None:
        try:
            os.killpg(self.process_group_id, signum)
        except ProcessLookupError:
            return
        except PermissionError as exc:
            signal_name = signal.Signals(signum).name
            raise ManagedProcessCleanupError(
                f"permission denied sending {signal_name} to process group "
                f"{self.process_group_id}"
            ) from exc

    def _wait_for_group_exit(self, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while True:
            self.process.poll()
            if not process_group_exists(self.process_group_id):
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(_GROUP_POLL_INTERVAL_SECONDS, remaining))

    def _install_signal_handlers(self) -> None:
        if not self._handle_signals:
            return
        if threading.current_thread() is not threading.main_thread():
            return
        try:
            for signum in (signal.SIGINT, signal.SIGTERM):
                self._previous_signal_handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, self._handle_signal)
        except BaseException:
            self._restore_signal_handlers()
            raise

    def _restore_signal_handlers(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            return
        previous_handlers = self._previous_signal_handlers
        self._previous_signal_handlers = {}
        for signum, previous_handler in previous_handlers.items():
            signal.signal(signum, previous_handler)

    def _handle_signal(self, signum: int, frame: FrameType | None) -> None:
        previous_handler = self._previous_signal_handlers.get(signum, signal.SIG_DFL)
        if self._handling_signal:
            self._send_group_signal(signal.SIGKILL)
            return

        self._handling_signal = True
        cleanup_error: BaseException | None = None
        try:
            self.close()
        except BaseException as exc:
            cleanup_error = exc
            signal_name = signal.Signals(signum).name
            print(
                f"ERROR: managed process cleanup failed during {signal_name}: {exc}",
                file=sys.stderr,
                flush=True,
            )

        self._dispatch_previous_signal(previous_handler, signum, frame)
        self._handling_signal = False
        if cleanup_error is not None:
            raise cleanup_error

    @staticmethod
    def _dispatch_previous_signal(
        previous_handler: Any,
        signum: int,
        frame: FrameType | None,
    ) -> None:
        if previous_handler == signal.SIG_IGN:
            return
        if previous_handler == signal.SIG_DFL:
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)
            return
        previous_handler(signum, frame)


def run_managed_process(
    command: Sequence[str],
    *,
    timeout: float | None = None,
    check: bool = False,
    terminate_timeout_seconds: float = DEFAULT_TERMINATE_TIMEOUT_SECONDS,
    kill_timeout_seconds: float = DEFAULT_KILL_TIMEOUT_SECONDS,
    **popen_options: Any,
) -> subprocess.CompletedProcess[Any]:
    """Run a command with ``subprocess.run``-like captured-output semantics."""
    with ManagedProcess.start(
        command,
        terminate_timeout_seconds=terminate_timeout_seconds,
        kill_timeout_seconds=kill_timeout_seconds,
        **popen_options,
    ) as managed:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            if managed.process.poll() is not None:
                managed.close()
                stdout, stderr = managed.process.communicate()
                break

            remaining = (
                None if deadline is None else deadline - time.monotonic()
            )
            if remaining is not None and remaining <= 0:
                managed.close()
                stdout, stderr = managed.process.communicate()
                raise subprocess.TimeoutExpired(
                    list(command),
                    timeout,
                    output=stdout,
                    stderr=stderr,
                ) from None

            poll_timeout = _COMMUNICATE_POLL_INTERVAL_SECONDS
            if remaining is not None:
                poll_timeout = min(poll_timeout, remaining)
            try:
                stdout, stderr = managed.process.communicate(timeout=poll_timeout)
                break
            except subprocess.TimeoutExpired:
                continue
        return_code = managed.process.returncode
        if return_code is None:
            raise RuntimeError("managed process did not publish a return code")
        result = subprocess.CompletedProcess(
            list(command),
            return_code,
            stdout,
            stderr,
        )

    if check:
        result.check_returncode()
    return result
