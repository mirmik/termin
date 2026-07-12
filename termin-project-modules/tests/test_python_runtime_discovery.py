from __future__ import annotations

from pathlib import Path

from termin.project_modules import runtime


def test_sdk_python_discovery_prefers_venv_capable_windows_runtime(
    tmp_path: Path,
) -> None:
    launcher_name = (
        "termin_python.exe" if runtime.sys.platform == "win32" else "termin_python"
    )
    launcher = tmp_path / "bin" / launcher_name
    launcher.parent.mkdir()
    launcher.touch()

    expected = launcher
    if runtime.sys.platform == "win32":
        expected = tmp_path / "python" / "python.exe"
        expected.parent.mkdir()
        expected.touch()

    assert runtime._sdk_python_executable(tmp_path) == expected
    assert runtime._is_python_executable(launcher)


def test_sdk_python_discovery_does_not_accept_arbitrary_host(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "not-python"
    executable.touch()

    assert not runtime._is_python_executable(executable)
