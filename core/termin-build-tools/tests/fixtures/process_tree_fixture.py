#!/usr/bin/env python3
"""Real wrapper/grandchild tree used by managed-process regression tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


STATE_ENVIRONMENT_VARIABLE = "TERMIN_PROCESS_TREE_STATE"


def _write_state(path: Path, grandchild_pid: int) -> None:
    path.write_text(
        json.dumps(
            {
                "wrapper_pid": os.getpid(),
                "grandchild_pid": grandchild_pid,
                "process_group_id": os.getpgrp(),
            }
        ),
        encoding="utf-8",
    )


def _run_grandchild(*, ignore_sigterm: bool) -> int:
    if ignore_sigterm:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        signal.pause()


def _run_wrapper(
    state_path: Path,
    *,
    ignore_grandchild_sigterm: bool,
    exit_after_start: bool,
) -> int:
    command = [sys.executable, str(Path(__file__).resolve()), "grandchild"]
    if ignore_grandchild_sigterm:
        command.append("--ignore-sigterm")
    grandchild = subprocess.Popen(command)
    _write_state(state_path, grandchild.pid)
    print("PROCESS_TREE_READY", flush=True)
    if exit_after_start:
        return 0
    return grandchild.wait()


def _wait_for_state(path: Path) -> None:
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(0.02)
            continue
        return
    raise RuntimeError(f"timed out waiting for process-tree state: {path}")


def _run_supervisor(state_path: Path) -> int:
    build_tools_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(build_tools_root))
    from termin_build.managed_process import ManagedProcess

    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "wrapper",
        str(state_path),
    ]
    with ManagedProcess.start(
        command,
        terminate_timeout_seconds=0.5,
        kill_timeout_seconds=2.0,
    ):
        _wait_for_state(state_path)
        state_path.with_suffix(".ready").write_text("ready\n", encoding="utf-8")
        while True:
            signal.pause()


def main() -> int:
    if len(sys.argv) == 1:
        raw_state_path = os.environ.get(STATE_ENVIRONMENT_VARIABLE)
        if not raw_state_path:
            raise RuntimeError(f"{STATE_ENVIRONMENT_VARIABLE} is required")
        return _run_wrapper(
            Path(raw_state_path),
            ignore_grandchild_sigterm=False,
            exit_after_start=False,
        )

    mode = sys.argv[1]
    if mode == "grandchild":
        return _run_grandchild(ignore_sigterm="--ignore-sigterm" in sys.argv[2:])
    if mode == "wrapper":
        return _run_wrapper(
            Path(sys.argv[2]),
            ignore_grandchild_sigterm="--ignore-sigterm" in sys.argv[3:],
            exit_after_start="--exit-after-start" in sys.argv[3:],
        )
    if mode == "supervisor":
        return _run_supervisor(Path(sys.argv[2]))
    raise RuntimeError(f"unknown fixture mode: {mode}")


if __name__ == "__main__":
    raise SystemExit(main())
