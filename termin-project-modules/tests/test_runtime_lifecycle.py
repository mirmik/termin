from __future__ import annotations

import sys
from pathlib import Path

from termin.project_modules.runtime import ProjectModulesRuntime


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
