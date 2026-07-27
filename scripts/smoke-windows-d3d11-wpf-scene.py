#!/usr/bin/env python3
"""Build and run the C# WPF scene host through its D3D11 D3DImage path."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    if os.name != "nt":
        print("WPF D3D11 scene smoke is Windows-only", file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parents[1]
    project = root / "termin-csharp" / "examples" / "SceneApp" / "SceneApp.csproj"
    build = subprocess.run(
        [
            "dotnet",
            "build",
            str(project),
            "--configuration",
            "Release",
            "--no-restore",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=120,
    )
    if build.returncode != 0:
        sys.stderr.write(build.stdout)
        sys.stderr.write(build.stderr)
        return build.returncode

    executable = (
        project.parent / "bin" / "Release" / "net8.0-windows" / "SceneApp.exe"
    )
    if not executable.is_file():
        print(f"WPF scene executable was not produced: {executable}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["TERMIN_D3D11_DEBUG"] = "1"
    env["TERMIN_WPF_PLOT_TRACE"] = "1"
    try:
        run = subprocess.run(
            [str(executable), "--smoke"],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            timeout=45,
        )
    except subprocess.TimeoutExpired as error:
        print("WPF D3D11 scene smoke exceeded 45 seconds", file=sys.stderr)
        if error.stdout:
            sys.stderr.write(error.stdout)
        if error.stderr:
            sys.stderr.write(error.stderr)
        return 1

    output = run.stdout + "\n" + run.stderr
    if run.returncode != 0:
        sys.stderr.write(output)
        return run.returncode
    if "SCENEAPP_D3D11_SMOKE_OK" not in output:
        sys.stderr.write(output)
        print("WPF scene did not report successful D3D11 presentation", file=sys.stderr)
        return 1

    rejected = (
        "D3D11 ERROR:",
        "ID3D11InfoQueue: error",
        "tc_display_new_d3d11_offscreen_current:",
        "D3D11 display presentation failed",
        "SCENEAPP_D3D11_SMOKE_FAILED",
    )
    found = [pattern for pattern in rejected if pattern.lower() in output.lower()]
    if found:
        sys.stderr.write(output)
        print(
            "WPF scene reported forbidden diagnostics: " + ", ".join(found),
            file=sys.stderr,
        )
        return 1

    print("WPF D3D11 scene smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
