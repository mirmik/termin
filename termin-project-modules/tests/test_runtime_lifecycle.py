from __future__ import annotations

import sys
from pathlib import Path

import pytest

from termin.project_modules.runtime import ProjectModulesRuntime
from termin_modules import module_context


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


def test_failed_python_load_does_not_orphan_imports_or_paths(tmp_path: Path) -> None:
    source_root = _write_python_module(
        tmp_path,
        packages=("sample_module", "missing_sample_module"),
    )
    runtime = ProjectModulesRuntime()
    runtime.set_sync_live_scenes(False)

    assert not runtime.load_project(tmp_path)
    assert "sample_module" not in sys.modules
    assert str(source_root.resolve()) not in sys.path
    assert runtime.close()


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
