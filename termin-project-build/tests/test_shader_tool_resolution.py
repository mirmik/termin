import os
from pathlib import Path

from termin.project_build import runtime_package_exporter


def _executable_name(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def _write_tool(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)


def test_runtime_package_exporter_resolves_sdk_windows_exe_suffix(
    monkeypatch,
    tmp_path: Path,
) -> None:
    sdk = tmp_path / "sdk"
    tool = sdk / "bin" / _executable_name("termin_shaderc")
    _write_tool(tool)

    monkeypatch.setenv("TERMIN_SDK", str(sdk))
    monkeypatch.setenv("PATH", "")

    assert runtime_package_exporter._resolve_shader_compiler(None) == tool.resolve()
