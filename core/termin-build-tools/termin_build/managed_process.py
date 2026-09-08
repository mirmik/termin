"""Cross-platform process-tree ownership for repository smoke commands."""

from __future__ import annotations

from collections.abc import Sequence
import os
import signal
import subprocess
import sys
import threading
import time
from types import FrameType
from typing import Any, Protocol


DEFAULT_TERMINATE_TIMEOUT_SECONDS = 5.0
DEFAULT_KILL_TIMEOUT_SECONDS = 5.0
_GROUP_POLL_INTERVAL_SECONDS = 0.05
_COMMUNICATE_POLL_INTERVAL_SECONDS = 0.1


class ManagedProcessCleanupError(RuntimeError):
    """Raised when a managed process tree cannot be confirmed dead."""


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


class _ProcessTreeOwner(Protocol):
    def close(self) -> None: ...

    def force_kill(self) -> None: ...


class _PosixProcessGroupOwner:
    def __init__(
        self,
        process: subprocess.Popen[Any],
        *,
        terminate_timeout_seconds: float,
        kill_timeout_seconds: float,
    ) -> None:
        self.process = process
        self.process_group_id = process.pid
        self._terminate_timeout_seconds = terminate_timeout_seconds
        self._kill_timeout_seconds = kill_timeout_seconds

    def close(self) -> None:
        self.process.poll()
        if not process_group_exists(self.process_group_id):
            return

        self._send_signal(signal.SIGTERM)
        if self._wait_for_exit(self._terminate_timeout_seconds):
            return

        self.force_kill()
        if self._wait_for_exit(self._kill_timeout_seconds):
            return

        raise ManagedProcessCleanupError(
            f"process group {self.process_group_id} survived SIGTERM and SIGKILL"
        )

    def force_kill(self) -> None:
        self._send_signal(signal.SIGKILL)

    def _send_signal(self, signum: int) -> None:
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

    def _wait_for_exit(self, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while True:
            self.process.poll()
            if not process_group_exists(self.process_group_id):
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(_GROUP_POLL_INTERVAL_SECONDS, remaining))


class _WindowsJobApi(Protocol):
    def create_kill_on_close_job(self) -> int: ...

    def assign_process(self, job_handle: int, process_handle: int) -> None: ...

    def resume_process(self, process_id: int) -> None: ...

    def active_process_count(self, job_handle: int) -> int: ...

    def terminate_job(self, job_handle: int, exit_code: int) -> None: ...

    def terminate_process(self, process_handle: int, exit_code: int) -> None: ...

    def close_handle(self, handle: int) -> None: ...


class _WindowsJobOwner:
    _TERMINATION_EXIT_CODE = 1

    def __init__(
        self,
        process: subprocess.Popen[Any],
        job_handle: int,
        api: _WindowsJobApi,
        *,
        kill_timeout_seconds: float,
    ) -> None:
        self.process = process
        self._job_handle: int | None = job_handle
        self._api = api
        self._kill_timeout_seconds = kill_timeout_seconds

    @classmethod
    def start(
        cls,
        command: Sequence[str],
        *,
        kill_timeout_seconds: float,
        api: _WindowsJobApi,
        popen_factory: Any = subprocess.Popen,
        **popen_options: Any,
    ) -> tuple[subprocess.Popen[Any], _WindowsJobOwner]:
        from .windows_job import CREATE_SUSPENDED

        creationflags = int(popen_options.pop("creationflags", 0))
        job_handle = api.create_kill_on_close_job()
        process: subprocess.Popen[Any] | None = None
        assigned = False
        try:
            process = popen_factory(
                list(command),
                creationflags=creationflags | CREATE_SUSPENDED,
                **popen_options,
            )
            process_handle = int(process._handle)  # type: ignore[attr-defined]
            api.assign_process(job_handle, process_handle)
            assigned = True
            api.resume_process(process.pid)
        except BaseException as launch_error:
            cleanup_error: BaseException | None = None
            if process is not None:
                try:
                    if assigned:
                        api.terminate_job(job_handle, cls._TERMINATION_EXIT_CODE)
                    else:
                        process_handle = int(process._handle)  # type: ignore[attr-defined]
                        api.terminate_process(
                            process_handle,
                            cls._TERMINATION_EXIT_CODE,
                        )
                    process.wait(timeout=kill_timeout_seconds)
                except BaseException as exc:
                    cleanup_error = exc
            try:
                api.close_handle(job_handle)
            except BaseException as exc:
                cleanup_error = cleanup_error or exc
            if cleanup_error is not None:
                print(
                    "ERROR: Windows managed-process launch cleanup failed: "
                    f"{cleanup_error}",
                    file=sys.stderr,
                    flush=True,
                )
                raise ManagedProcessCleanupError(
                    "Windows managed-process launch failed and cleanup could "
                    f"not be confirmed: {cleanup_error}"
                ) from launch_error
            raise
        return process, cls(
            process,
            job_handle,
            api,
            kill_timeout_seconds=kill_timeout_seconds,
        )

    def close(self) -> None:
        job_handle = self._job_handle
        if job_handle is None:
            return
        cleanup_error: BaseException | None = None
        try:
            if self._api.active_process_count(job_handle) != 0:
                self._api.terminate_job(job_handle, self._TERMINATION_EXIT_CODE)
                if not self._wait_for_exit(job_handle):
                    raise ManagedProcessCleanupError(
                        f"Windows Job Object {job_handle} remained active after "
                        "TerminateJobObject"
                    )
        except BaseException as exc:
            cleanup_error = exc
        try:
            # KILL_ON_JOB_CLOSE is both the crash-safety guarantee and the final
            # fallback if the accounting query or explicit termination failed.
            self._api.close_handle(job_handle)
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
        self._job_handle = None
        self.process.poll()
        if cleanup_error is not None:
            if isinstance(cleanup_error, ManagedProcessCleanupError):
                raise cleanup_error
            raise ManagedProcessCleanupError(
                f"Windows Job Object cleanup failed: {cleanup_error}"
            ) from cleanup_error

    def force_kill(self) -> None:
        job_handle = self._job_handle
        if job_handle is not None:
            self._api.terminate_job(job_handle, self._TERMINATION_EXIT_CODE)

    def _wait_for_exit(self, job_handle: int) -> bool:
        deadline = time.monotonic() + self._kill_timeout_seconds
        while True:
            self.process.poll()
            if self._api.active_process_count(job_handle) == 0:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(_GROUP_POLL_INTERVAL_SECONDS, remaining))


class ManagedProcess:
    """Own one process tree and guarantee bounded cleanup."""

    def __init__(
        self,
        process: subprocess.Popen[Any],
        *,
        owner: _ProcessTreeOwner,
        process_group_id: int | None,
        handle_signals: bool,
    ) -> None:
        self.process = process
        self.process_group_id = process_group_id
        self._owner = owner
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
        """Start ``command`` inside a newly owned platform process tree."""
        if terminate_timeout_seconds < 0:
            raise ValueError("terminate_timeout_seconds must be non-negative")
        if kill_timeout_seconds < 0:
            raise ValueError("kill_timeout_seconds must be non-negative")
        conflicting_options = {
            "start_new_session",
            "process_group",
        } & popen_options.keys()
        if conflicting_options:
            joined = ", ".join(sorted(conflicting_options))
            raise TypeError(f"ManagedProcess owns these Popen options: {joined}")

        process_group_id: int | None = None
        if os.name == "posix":
            process = subprocess.Popen(
                list(command),
                start_new_session=True,
                **popen_options,
            )
            owner: _ProcessTreeOwner = _PosixProcessGroupOwner(
                process,
                terminate_timeout_seconds=terminate_timeout_seconds,
                kill_timeout_seconds=kill_timeout_seconds,
            )
            process_group_id = process.pid
        elif os.name == "nt":
            from .windows_job import CtypesWindowsJobApi

            process, owner = _WindowsJobOwner.start(
                command,
                kill_timeout_seconds=kill_timeout_seconds,
                api=CtypesWindowsJobApi(),
                **popen_options,
            )
        else:
            raise NotImplementedError(
                f"ManagedProcess does not support platform os.name={os.name!r}"
            )
        managed = cls(
            process,
            owner=owner,
            process_group_id=process_group_id,
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
        """Terminate every remaining tree member and restore signal handlers."""
        try:
            self._owner.close()
        except BaseException as exc:
            print(
                f"ERROR: managed process cleanup failed: {exc}",
                file=sys.stderr,
                flush=True,
            )
            raise
        finally:
            self._restore_signal_handlers()

    def _install_signal_handlers(self) -> None:
        if not self._handle_signals:
            return
        if threading.current_thread() is not threading.main_thread():
            return
        try:
            handled_signals = [signal.SIGINT, signal.SIGTERM]
            if os.name == "nt":
                handled_signals.append(signal.SIGBREAK)
            for signum in handled_signals:
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
            self._owner.force_kill()
            return

        self._handling_signal = True
        cleanup_error: BaseException | None = None
        try:
            self.close()
        except BaseException as exc:
            cleanup_error = exc

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
