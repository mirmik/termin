from __future__ import annotations

import sys
import threading
import types
from pathlib import Path

import pytest

from termin.project_modules.runtime import ProjectModulesRuntime
from termin_modules import (
    ModuleEnvironment,
    ModuleRuntime,
    PythonModuleBackend,
    module_context,
)


def _write_python_module(
    project_root: Path,
    *,
    packages: tuple[str, ...] = ("sample_module",),
) -> Path:
    source_root = project_root / "Scripts"
    package = source_root / "sample_module"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("VALUE = 42\n", encoding="utf-8")
    descriptor = project_root / "sample.pymodule"
    package_list = ", ".join(packages)
    descriptor.write_text(
        "name: sample\n"
        "root: Scripts\n"
        f"packages: [{package_list}]\n",
        encoding="utf-8",
    )
    return source_root


def test_project_runtime_close_removes_python_modules_and_paths(tmp_path: Path) -> None:
    source_root = _write_python_module(tmp_path)
    runtime = ProjectModulesRuntime()
    runtime.set_sync_live_scenes(False)

    assert runtime.load_project(tmp_path)
    assert "sample_module" in sys.modules
    assert str(source_root.resolve()) in sys.path

    assert runtime.close()
    assert runtime.closed
    assert "sample_module" not in sys.modules
    assert str(source_root.resolve()) not in sys.path


def test_pymodule_component_uses_owner_load_reload_unload_protocol(tmp_path: Path) -> None:
    from termin.scene import ComponentRegistry

    source_root = tmp_path / "Scripts"
    package = source_root / "owned_components"
    package.mkdir(parents=True)
    descriptor = tmp_path / "components.pymodule"
    descriptor.write_text(
        "name: components\nroot: Scripts\npackages: [owned_components]\n",
        encoding="utf-8",
    )

    def write_component(version: int) -> None:
        (package / "__init__.py").write_text(
            "from termin.scene import PythonComponent\n"
            "class OwnedLifecycleComponent(PythonComponent):\n"
            f"    version = {version}\n",
            encoding="utf-8",
        )

    registry = ComponentRegistry.instance()
    registry.unregister_python("OwnedLifecycleComponent")
    runtime = ProjectModulesRuntime()
    runtime.set_sync_live_scenes(False)
    try:
        write_component(1)
        assert runtime.load_project(tmp_path)
        first_class = sys.modules["owned_components"].OwnedLifecycleComponent
        assert registry.has("OwnedLifecycleComponent")
        assert first_class.version == 1

        write_component(2)
        assert runtime.reload_module("components")
        second_class = sys.modules["owned_components"].OwnedLifecycleComponent
        assert registry.has("OwnedLifecycleComponent")
        assert second_class is not first_class
        assert second_class.version == 2

        assert runtime.unload_module("components")
        assert not registry.has("OwnedLifecycleComponent")
        assert "owned_components" not in sys.modules
    finally:
        runtime.close()
        registry.unregister_python("OwnedLifecycleComponent")


def test_failed_python_load_does_not_orphan_imports_or_paths(tmp_path: Path) -> None:
    source_root = _write_python_module(
        tmp_path,
        packages=("sample_module", "missing_sample_module"),
    )
    runtime = ProjectModulesRuntime()
    runtime.set_sync_live_scenes(False)

    assert not runtime.load_project(tmp_path)
    assert "sample_module" not in sys.modules
    assert str(source_root.resolve()) in sys.path
    assert runtime.close()
    assert str(source_root.resolve()) not in sys.path


def test_python_session_paths_survive_module_unload_and_reload(tmp_path: Path) -> None:
    first_root = _write_python_module(tmp_path)
    second_root = tmp_path / "SecondScripts"
    second_package = second_root / "second_module"
    second_package.mkdir(parents=True)
    (second_package / "__init__.py").write_text("VALUE = 84\n", encoding="utf-8")
    (tmp_path / "second.pymodule").write_text(
        "name: second\nroot: SecondScripts\npackages: [second_module]\n",
        encoding="utf-8",
    )

    runtime = ProjectModulesRuntime()
    runtime.set_sync_live_scenes(False)
    assert runtime.load_project(tmp_path)

    first_path = str(first_root.resolve())
    second_path = str(second_root.resolve())
    assert sys.path.count(first_path) == 1
    assert sys.path.count(second_path) == 1

    assert runtime.unload_module("sample")
    assert first_path in sys.path
    assert second_path in sys.path
    assert runtime.load_module("sample")
    assert runtime.reload_module("sample")
    assert sys.path.count(first_path) == 1
    assert sys.path.count(second_path) == 1

    assert runtime.close()
    assert first_path not in sys.path
    assert second_path not in sys.path


def test_python_session_does_not_claim_preexisting_equal_path(tmp_path: Path) -> None:
    source_root = _write_python_module(tmp_path)
    source_path = str(source_root.resolve())
    sys.path.insert(0, source_path)
    runtime = ProjectModulesRuntime()
    runtime.set_sync_live_scenes(False)
    try:
        assert runtime.load_project(tmp_path)
        assert sys.path.count(source_path) == 1
        assert runtime.close()
        assert sys.path.count(source_path) == 1
    finally:
        if not runtime.closed:
            runtime.close()
        sys.path.remove(source_path)
        sys.modules.pop("sample_module", None)


def test_repeated_project_runtimes_own_independent_path_lifecycles(tmp_path: Path) -> None:
    source_root = _write_python_module(tmp_path)
    source_path = str(source_root.resolve())

    for _ in range(2):
        runtime = ProjectModulesRuntime()
        runtime.set_sync_live_scenes(False)
        assert runtime.load_project(tmp_path)
        assert sys.path.count(source_path) == 1
        assert runtime.close()
        assert source_path not in sys.path
        assert "sample_module" not in sys.modules

    venv_python = tmp_path / ".venv" / (
        "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    )
    assert venv_python.is_file()


def test_python_environment_setup_failure_prevents_import_and_leaves_no_paths(
    tmp_path: Path,
) -> None:
    source_root = _write_python_module(tmp_path)
    incomplete_venv = tmp_path / ".venv"
    incomplete_venv.mkdir()
    environment = ModuleEnvironment()
    environment.python_executable = sys.executable
    environment.project_root = str(tmp_path)
    environment.project_venv_path = str(incomplete_venv)
    environment.use_project_venv = True

    runtime = ModuleRuntime()
    runtime.set_environment(environment)
    runtime.register_python_backend(PythonModuleBackend())

    assert not runtime.discover(tmp_path)
    assert "Project venv is incomplete" in runtime.last_error
    assert str(source_root.resolve()) not in sys.path
    assert "sample_module" not in sys.modules
    assert runtime.shutdown()


def test_preimported_package_survives_failed_load_and_unload(tmp_path: Path) -> None:
    source_root = _write_python_module(
        tmp_path,
        packages=("sample_module", "missing_sample_module"),
    )
    source_path = str(source_root.resolve())
    sys.path.insert(0, source_path)
    __import__("sample_module")
    original = sys.modules["sample_module"]
    try:
        failed_runtime = ProjectModulesRuntime()
        failed_runtime.set_sync_live_scenes(False)
        assert not failed_runtime.load_project(tmp_path)
        assert sys.modules["sample_module"] is original
        assert failed_runtime.close()
        assert sys.modules["sample_module"] is original

        (tmp_path / "sample.pymodule").write_text(
            "name: sample\nroot: Scripts\npackages: [sample_module]\n",
            encoding="utf-8",
        )
        runtime = ProjectModulesRuntime()
        runtime.set_sync_live_scenes(False)
        assert runtime.load_project(tmp_path)
        assert runtime.unload_module("sample")
        assert sys.modules["sample_module"] is original
        assert runtime.close()
        assert sys.modules["sample_module"] is original
    finally:
        sys.modules.pop("sample_module", None)
        sys.path.remove(source_path)


def test_overlapping_python_package_claims_fail_before_import(tmp_path: Path) -> None:
    source_root = tmp_path / "Scripts"
    package = source_root / "shared_package"
    child = package / "child"
    child.mkdir(parents=True)
    (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (child / "__init__.py").write_text("VALUE = 2\n", encoding="utf-8")
    (tmp_path / "first.pymodule").write_text(
        "name: first\nroot: Scripts\npackages: [shared_package]\n",
        encoding="utf-8",
    )
    (tmp_path / "second.pymodule").write_text(
        "name: second\nroot: Scripts\npackages: [shared_package.child]\n",
        encoding="utf-8",
    )

    runtime = ProjectModulesRuntime()
    runtime.set_sync_live_scenes(False)
    assert not runtime.load_project(tmp_path)
    assert "Python package namespace overlap" in runtime.last_error
    assert "first" in runtime.last_error
    assert "second" in runtime.last_error
    assert "shared_package" not in sys.modules
    assert str(source_root.resolve()) not in sys.path
    assert runtime.close()


def test_partial_python_import_evicts_only_transaction_modules(tmp_path: Path) -> None:
    source_root = tmp_path / "Scripts"
    package = source_root / "broken_package"
    package.mkdir(parents=True)
    (package / "child.py").write_text("VALUE = 42\n", encoding="utf-8")
    (package / "__init__.py").write_text(
        "from . import child\nraise RuntimeError('injected partial import failure')\n",
        encoding="utf-8",
    )
    (tmp_path / "broken.pymodule").write_text(
        "name: broken\nroot: Scripts\npackages: [broken_package]\n",
        encoding="utf-8",
    )

    runtime = ProjectModulesRuntime()
    runtime.set_sync_live_scenes(False)
    assert not runtime.load_project(tmp_path)
    assert "injected partial import failure" in runtime.last_error
    assert "broken_package" not in sys.modules
    assert "broken_package.child" not in sys.modules
    assert runtime.close()


def test_unload_preserves_replaced_sys_modules_mapping(tmp_path: Path) -> None:
    _write_python_module(tmp_path)
    runtime = ProjectModulesRuntime()
    runtime.set_sync_live_scenes(False)
    assert runtime.load_project(tmp_path)
    original = sys.modules["sample_module"]
    replacement = types.ModuleType("sample_module")
    sys.modules["sample_module"] = replacement

    assert runtime.unload_module("sample")
    assert sys.modules["sample_module"] is replacement
    assert original is not replacement
    assert runtime.close()
    assert sys.modules["sample_module"] is replacement
    sys.modules.pop("sample_module", None)


def test_python_reload_publishes_new_namespace_and_keeps_old_references(
    tmp_path: Path,
) -> None:
    source_root = _write_python_module(tmp_path)
    runtime = ProjectModulesRuntime()
    runtime.set_sync_live_scenes(False)
    assert runtime.load_project(tmp_path)
    old_module = sys.modules["sample_module"]
    assert old_module.VALUE == 42

    (source_root / "sample_module" / "__init__.py").write_text(
        "VALUE = 840\n",
        encoding="utf-8",
    )
    assert runtime.reload_module("sample")
    new_module = sys.modules["sample_module"]
    assert new_module is not old_module
    assert new_module.VALUE == 840
    assert old_module.VALUE == 42
    assert runtime.close()
    assert "sample_module" not in sys.modules


def test_loading_new_descriptor_rebuilds_runtime_without_orphaning_handles(
    tmp_path: Path,
) -> None:
    _write_python_module(tmp_path)
    runtime = ProjectModulesRuntime()
    runtime.set_sync_live_scenes(False)
    assert runtime.load_project(tmp_path)

    second_package = tmp_path / "Scripts" / "second_module"
    second_package.mkdir()
    (second_package / "__init__.py").write_text("VALUE = 84\n", encoding="utf-8")
    second_descriptor = tmp_path / "second.pymodule"
    second_descriptor.write_text(
        "name: second\nroot: Scripts\npackages: [second_module]\n",
        encoding="utf-8",
    )

    assert runtime.load_descriptor(second_descriptor)
    assert runtime.find("sample") is not None
    assert runtime.find("second") is not None
    assert "sample_module" in sys.modules
    assert "second_module" in sys.modules

    assert runtime.close()
    assert "sample_module" not in sys.modules
    assert "second_module" not in sys.modules


def test_invalid_descriptor_reload_keeps_module_loaded_and_dirty(tmp_path: Path) -> None:
    _write_python_module(tmp_path)
    descriptor = tmp_path / "sample.pymodule"
    runtime = ProjectModulesRuntime()
    runtime.set_sync_live_scenes(False)
    assert runtime.load_project(tmp_path)

    assert runtime.mark_modules_dirty_for_path(descriptor) == ["sample"]
    descriptor.write_text("name: sample\npackages: [\n", encoding="utf-8")

    assert not runtime.reload_dirty_modules()
    assert "sample" in runtime.dirty_modules()
    assert "sample_module" in sys.modules
    assert str(descriptor) in runtime.last_error

    descriptor.write_text(
        "name: sample\nroot: Scripts\npackages: [sample_module]\n",
        encoding="utf-8",
    )
    assert runtime.close()
    assert "sample_module" not in sys.modules


def test_module_registration_commit_failure_is_propagated_and_retryable() -> None:
    module_id = "registration_commit_failure_probe"
    module_context.begin_module_import(module_id)
    module_context.record_component("RegistrationCommitFailureProbe")
    module_context.end_module_import(module_id)

    original_cleanup = module_context._unregister_python_component_classes

    def fail_cleanup(registrations: module_context.ModuleOwnedRegistrations) -> None:
        del registrations
        raise RuntimeError("injected registration cleanup failure")

    module_context._unregister_python_component_classes = fail_cleanup
    try:
        with pytest.raises(RuntimeError, match="injected registration cleanup failure"):
            module_context.unregister_module_owner(module_id)
        assert module_context.registrations_for_owner(module_id).components == {
            "RegistrationCommitFailureProbe"
        }
    finally:
        module_context._unregister_python_component_classes = original_cleanup

    module_context.unregister_module_owner(module_id)
    assert module_context.registrations_for_owner(module_id).components == set()


def test_python_backend_commit_failure_keeps_sys_modules_and_loaded_handle(
    tmp_path: Path,
) -> None:
    _write_python_module(tmp_path)
    runtime = ProjectModulesRuntime()
    runtime.set_sync_live_scenes(False)
    assert runtime.load_project(tmp_path)

    original_cleanup = module_context._unregister_python_component_classes

    def fail_cleanup(registrations: module_context.ModuleOwnedRegistrations) -> None:
        del registrations
        raise RuntimeError("injected backend registration commit failure")

    module_context._unregister_python_component_classes = fail_cleanup
    try:
        assert not runtime.unload_module("sample")
        assert "injected backend registration commit failure" in runtime.last_error
        assert "sample_module" in sys.modules
        record = runtime.find("sample")
        assert record is not None
        assert record.state.name == "Loaded"
    finally:
        module_context._unregister_python_component_classes = original_cleanup

    assert runtime.unload_module("sample")
    assert "sample_module" not in sys.modules
    assert runtime.close()


def test_artifact_preparation_runs_isolated_from_live_runtime(tmp_path: Path) -> None:
    (tmp_path / "Game.terminproj").write_text("{}", encoding="utf-8")
    _write_python_module(tmp_path)
    runtime = ProjectModulesRuntime()
    assert runtime.discover_project(tmp_path)
    assert runtime.find("sample") is not None
    assert "sample_module" not in sys.modules

    result: list[bool] = []
    worker = threading.Thread(
        target=lambda: result.append(runtime.prepare_module_artifacts()),
        name="artifact-preparation-test",
    )
    worker.start()
    worker.join(timeout=20.0)

    assert not worker.is_alive()
    assert result == [True]
    assert runtime.prepare_module_artifacts(operation="build", module_id="sample")
    assert "sample_module" not in sys.modules
    record = runtime.find("sample")
    assert record is not None
    assert record.state.name == "Discovered"
    assert runtime.close()
