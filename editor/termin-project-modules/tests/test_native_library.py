"""Real native/Python cascade reload, including retained stale Python references."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from termin.project_modules import runtime as runtime_module
from termin_modules import ModuleState
from termin_nanobind.runtime import find_sdk


@dataclass
class _NativeProject:
    runtime: runtime_module.ProjectModulesRuntime
    artifact: Path
    source: Path
    build_marker: Path
    compile_version: Callable[[int], None]


@pytest.fixture
def native_project(tmp_path: Path, monkeypatch):
    sdk = find_sdk()
    assert sdk is not None
    (tmp_path / "Game.terminproj").write_text("{}", encoding="utf-8")
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
    build_marker = tmp_path / "runtime-build.marker"
    (tmp_path / "runtime-build.cmake").write_text(
        'file(APPEND "runtime-build.marker" "built\\n")\n'
        f'file(TOUCH "{artifact.name}")\n'
    )
    (tmp_path / "probe.module").write_text(json.dumps({
        "name": "probe", "build": {
            "output": artifact.name, "command": "cmake -P runtime-build.cmake",
        }
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
        yield _NativeProject(runtime, artifact, source / "probe.cpp", build_marker, compile_version)
    finally:
        assert runtime.close()


def test_native_binding_follows_dependency_reload(native_project):
    runtime = native_project.runtime
    artifact = native_project.artifact
    try:
        old_module = sys.modules["native_client"]
        old_function = old_module.api.probe_value
        assert old_module.value == old_function() == 11
        with pytest.raises(RuntimeError, match="Native symbol not found"):
            _ = old_module.api.missing_symbol
        with pytest.raises(RuntimeError, match="Native module is not loaded"):
            runtime.bind_native_library("client")

        for version in (22, 33):
            native_project.compile_version(version)
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


@pytest.mark.parametrize("preserve_timestamp", [False, True])
def test_external_native_build_is_loaded_before_play(native_project, preserve_timestamp):
    runtime = native_project.runtime
    old_module = sys.modules["native_client"]
    old_function = old_module.api.probe_value
    assert old_module.value == old_function() == 11
    assert not native_project.build_marker.exists()
    assert runtime.dirty_modules() == {}
    assert runtime.changed_modules() == []
    assert not runtime.needs_reload("probe")

    artifact_stat = native_project.artifact.stat()
    source_stat = native_project.source.stat()
    native_project.compile_version(22)
    if preserve_timestamp:
        # Publishing a binary may preserve its timestamp; neither mtime nor size
        # identifies the executable generation currently loaded by the editor.
        os.utime(native_project.source, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
        os.utime(native_project.artifact, ns=(artifact_stat.st_atime_ns, artifact_stat.st_mtime_ns))

    assert runtime.dirty_modules() == {}
    assert not runtime.needs_rebuild("probe")
    assert runtime.needs_reload("probe")
    assert runtime.changed_modules() == ["probe"]
    assert runtime.prepare_changed_modules_for_play(), runtime.last_error
    current = sys.modules["native_client"]
    assert current is not old_module
    assert current.value == current.api.probe_value() == 22
    assert not old_module.api.valid
    with pytest.raises(RuntimeError, match="has been unloaded"):
        old_function()
    assert not native_project.build_marker.exists()
    assert not runtime.needs_reload("probe")
    assert runtime.changed_modules() == []

    # Re-entering Play and touching byte-identical output must keep bindings alive.
    assert runtime.prepare_changed_modules_for_play(), runtime.last_error
    assert sys.modules["native_client"] is current
    os.utime(native_project.artifact, None)
    assert not runtime.needs_reload("probe")
    assert runtime.changed_modules() == []
    assert runtime.prepare_changed_modules_for_play(), runtime.last_error
    assert sys.modules["native_client"] is current
    assert current.api.valid
    assert not native_project.build_marker.exists()


def test_failed_external_native_reload_remains_pending(native_project):
    runtime = native_project.runtime
    old_module = sys.modules["native_client"]
    native_project.artifact.write_bytes(b"not a shared library")
    assert runtime.dirty_modules() == {}
    assert not runtime.needs_rebuild("probe")
    assert runtime.needs_reload("probe")
    assert not runtime.prepare_changed_modules_for_play()
    assert runtime.last_error
    assert runtime.find("probe").state == ModuleState.Failed
    assert runtime.needs_reload("probe")
    assert "probe" in runtime.changed_modules()
    assert not old_module.api.valid
    assert not native_project.build_marker.exists()

    native_project.compile_version(22)
    assert runtime.prepare_changed_modules_for_play(), runtime.last_error
    assert sys.modules["native_client"].value == 22
    assert sys.modules["native_client"].api.probe_value() == 22
    assert not runtime.needs_reload("probe")
    assert runtime.changed_modules() == []
    assert not native_project.build_marker.exists()


@pytest.mark.parametrize("source_change", ["edited", "deleted", "preserved_timestamp"])
def test_dirty_native_source_still_builds_before_play(native_project, source_change):
    runtime = native_project.runtime
    old_module = sys.modules["native_client"]
    source_stat = native_project.source.stat()
    if source_change == "deleted":
        native_project.source.unlink()
    else:
        native_project.source.write_text(native_project.source.read_text() + "\n// source changed\n")
        if source_change == "preserved_timestamp":
            os.utime(native_project.source, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
    runtime.mark_modules_dirty_for_path(native_project.source)
    assert "probe" in runtime.dirty_modules()
    assert runtime.needs_rebuild("probe")
    assert runtime.prepare_changed_modules_for_play(), runtime.last_error
    assert native_project.build_marker.exists()
    assert runtime.dirty_modules() == {}
    assert not runtime.needs_rebuild("probe")
    assert runtime.changed_modules() == []
    assert sys.modules["native_client"] is not old_module
    assert sys.modules["native_client"].value == 11


def test_external_build_satisfies_observed_native_source_change(native_project):
    runtime = native_project.runtime
    old_module = sys.modules["native_client"]
    native_project.source.write_text(native_project.source.read_text() + "\n// source changed\n")
    assert runtime.mark_modules_dirty_for_path(native_project.source) == ["probe"]
    assert runtime.needs_rebuild("probe")

    native_project.compile_version(22)
    assert "probe" in runtime.dirty_modules()
    assert not runtime.needs_rebuild("probe")
    assert runtime.needs_reload("probe")
    assert runtime.prepare_changed_modules_for_play(), runtime.last_error
    assert sys.modules["native_client"] is not old_module
    assert sys.modules["native_client"].value == 22
    assert not old_module.api.valid
    assert not native_project.build_marker.exists()
    assert runtime.dirty_modules() == {}
    assert runtime.changed_modules() == []


def test_failed_build_keeps_deleted_source_change_pending(native_project):
    runtime = native_project.runtime
    build_script = native_project.artifact.parent / "runtime-build.cmake"
    script_contents = build_script.read_text()
    script_stat = build_script.stat()
    build_script.write_text('message(FATAL_ERROR "deliberate build failure")\n')
    os.utime(build_script, ns=(script_stat.st_atime_ns, script_stat.st_mtime_ns))
    native_project.source.unlink()
    assert runtime.mark_modules_dirty_for_path(native_project.source) == ["probe"]
    assert runtime.needs_rebuild("probe")
    assert not runtime.prepare_changed_modules_for_play()
    assert runtime.last_error
    assert runtime.find("probe").state == ModuleState.Failed
    assert "probe" in runtime.dirty_modules()
    assert runtime.needs_rebuild("probe")
    assert "probe" in runtime.changed_modules()
    assert not native_project.build_marker.exists()

    # No remaining input has a newer timestamp. The unsuccessful build must
    # preserve the observed deletion until a later build succeeds.
    build_script.write_text(script_contents)
    os.utime(build_script, ns=(script_stat.st_atime_ns, script_stat.st_mtime_ns))
    assert runtime.needs_rebuild("probe")
    assert runtime.prepare_changed_modules_for_play(), runtime.last_error
    assert native_project.build_marker.read_text().splitlines() == ["built"]
    assert sys.modules["native_client"].value == 11
    assert runtime.dirty_modules() == {}
    assert runtime.changed_modules() == []


def test_explicit_native_commands_run_with_unchanged_artifact(native_project):
    runtime = native_project.runtime
    old_module = sys.modules["native_client"]
    old_function = old_module.api.probe_value
    assert not runtime.needs_rebuild("probe")
    assert not runtime.needs_reload("probe")

    for count in (1, 2):
        assert runtime.build_module("probe"), runtime.last_error
        assert native_project.build_marker.read_text().splitlines() == ["built"] * count
        assert not runtime.needs_rebuild("probe")
        assert not runtime.needs_reload("probe")
        assert sys.modules["native_client"] is old_module
        assert old_function() == 11

    assert runtime.reload_module("probe"), runtime.last_error
    current = sys.modules["native_client"]
    assert current is not old_module
    assert current.value == current.api.probe_value() == 11
    assert not old_module.api.valid
    with pytest.raises(RuntimeError, match="has been unloaded"):
        old_function()
    assert native_project.build_marker.read_text().splitlines() == ["built", "built"]
    assert runtime.changed_modules() == []


def test_isolated_build_preserves_loaded_generation_until_success(native_project):
    runtime = native_project.runtime
    old_module = sys.modules["native_client"]
    old_function = old_module.api.probe_value
    build_script = native_project.artifact.parent / "runtime-build.cmake"
    script_contents = build_script.read_text()
    script_stat = build_script.stat()
    build_script.write_text('message(FATAL_ERROR "deliberate isolated build failure")\n')
    os.utime(build_script, ns=(script_stat.st_atime_ns, script_stat.st_mtime_ns))
    native_project.source.unlink()
    assert runtime.mark_modules_dirty_for_path(native_project.source) == ["probe"]
    assert runtime.needs_rebuild("probe")

    assert not runtime.prepare_module_artifacts()
    assert runtime.last_error
    assert runtime.find("probe").state == ModuleState.Loaded
    assert runtime.find("client").state == ModuleState.Loaded
    assert sys.modules["native_client"] is old_module
    assert old_module.api.valid
    assert old_function() == 11
    assert "probe" in runtime.dirty_modules()
    assert runtime.needs_rebuild("probe")
    assert not native_project.build_marker.exists()

    build_script.write_text(script_contents)
    os.utime(build_script, ns=(script_stat.st_atime_ns, script_stat.st_mtime_ns))
    assert runtime.prepare_module_artifacts(), runtime.last_error
    assert native_project.build_marker.read_text().splitlines() == ["built"]
    assert not runtime.needs_rebuild("probe")
    assert runtime.find("probe").state == ModuleState.Loaded
    assert runtime.find("client").state == ModuleState.Loaded
    assert sys.modules["native_client"] is old_module
    assert old_module.api.valid
    assert old_function() == 11

    assert runtime.prepare_changed_modules_for_play(), runtime.last_error
    current = sys.modules["native_client"]
    assert current is not old_module
    assert current.value == current.api.probe_value() == 11
    assert not old_module.api.valid
    with pytest.raises(RuntimeError, match="has been unloaded"):
        old_function()
    assert native_project.build_marker.read_text().splitlines() == ["built"]
    assert runtime.dirty_modules() == {}
    assert runtime.changed_modules() == []
