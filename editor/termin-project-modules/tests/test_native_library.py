"""Real native/Python cascade reload, including retained stale Python references."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from termin.project_modules import runtime as runtime_module
from termin_nanobind.runtime import find_sdk


def test_native_binding_follows_dependency_reload(tmp_path: Path, monkeypatch):
    sdk = find_sdk()
    assert sdk is not None
    source = tmp_path / "native"
    source.mkdir()
    (source / "CMakeLists.txt").write_text(
        'cmake_minimum_required(VERSION 3.16)\nproject(probe LANGUAGES CXX)\n'
        'add_library(probe SHARED probe.cpp)\n'
        'target_include_directories(probe PRIVATE "${SDK_INCLUDE}")\n'
    )
    artifact = tmp_path / ("probe.dll" if sys.platform == "win32" else "libprobe.so")
    if sys.platform == "darwin":
        artifact = tmp_path / "libprobe.dylib"
    (tmp_path / "probe.module").write_text(json.dumps({
        "name": "probe", "build": {"output": artifact.name}
    }))
    build = source / "build"

    def compile_version(version):
        (source / "probe.cpp").write_text(
            '#include <termin_modules/native_module_abi.h>\n'
            'static int32_t init(const termin_native_module_host_v1*, termin_native_module_error*) { return 0; }\n'
            'static int32_t stop(const termin_native_module_host_v1*, termin_native_module_error*) { return 0; }\n'
            'TERMIN_NATIVE_MODULE_DESCRIPTOR_V1("probe", "1", "test", 0, init, stop);\n'
            f'extern "C" TERMIN_NATIVE_MODULE_EXPORT int probe_value() {{ return {version}; }}\n'
        )
        subprocess.run(["cmake", "-S", str(source), "-B", str(build),
                        f"-DSDK_INCLUDE={sdk / 'include'}"], check=True, capture_output=True)
        subprocess.run(["cmake", "--build", str(build), "--config", "Release"],
                       check=True, capture_output=True)
        built = next(build.rglob(artifact.name))
        shutil.copy2(built, artifact)

    # No Python module should directly open artifact or retain its OS handle.
    package = tmp_path / "scripts" / "native_client"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        'from termin.project_modules.runtime import get_project_modules_runtime\n'
        'api = get_project_modules_runtime().bind_native_library("probe")\n'
        'api.probe_value.argtypes = []\n'
        'value = api.probe_value()\n'
    )
    (tmp_path / "client.pymodule").write_text(json.dumps({
        "name": "client", "root": "scripts", "packages": ["native_client"],
        "dependencies": ["probe"]
    }))
    runtime = runtime_module.ProjectModulesRuntime(use_project_venv=False)
    runtime.set_sync_live_scenes(False)
    monkeypatch.setattr(runtime_module, "_instance", runtime)
    try:
        compile_version(11)
        assert runtime.load_project(tmp_path), runtime.last_error
        old_module = sys.modules["native_client"]
        old_function = old_module.api.probe_value
        assert old_module.value == old_function() == 11
        with pytest.raises(RuntimeError, match="Native symbol not found"):
            _ = old_module.api.missing_symbol
        with pytest.raises(RuntimeError, match="Native module is not loaded"):
            runtime.bind_native_library("client")

        for version in (22, 33):
            compile_version(version)
            assert runtime.reload_module("probe"), runtime.last_error
            current = sys.modules["native_client"]
            assert current is not old_module
            assert current.value == current.api.probe_value() == version
            assert not old_module.api.valid
            with pytest.raises(RuntimeError, match="has been unloaded"):
                old_function()
            if sys.platform == "linux":
                maps = Path("/proc/self/maps").read_text()
                assert str(artifact) not in maps
                # One executable generation, even with old Python references held.
                assert sum("r-xp" in line and artifact.name in line
                           for line in maps.splitlines()) == 1
        last_api = current.api
        # A native call may be active on another free-threaded Python thread.
        symbols = runtime._runtime.native_symbols("probe")
        call = symbols.acquire("probe_value")
        assert runtime._runtime.unload_module("client")
        assert not runtime._runtime.unload_module("probe")
        assert "active bound calls" in runtime._runtime.last_error
        call.release()
        assert runtime._runtime.unload_module("probe")
    finally:
        assert runtime.close()
    assert not last_api.valid
    with pytest.raises(RuntimeError, match="has been unloaded"):
        last_api.probe_value()
