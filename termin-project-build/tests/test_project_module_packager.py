from __future__ import annotations

import json
from pathlib import Path

from termin.project_build.project_module_packager import package_project_modules


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_packages_exact_mixed_dependency_closure(tmp_path: Path) -> None:
    project = tmp_path / "Game"
    native_artifact = project / "native" / "build" / "libphysics.so"
    native_artifact.parent.mkdir(parents=True)
    native_artifact.write_bytes(b"native-module")
    _write_json(
        project / "native" / "physics.module",
        {
            "name": "physics",
            "type": "cpp",
            "build": {"command": "build-physics", "output": "build/libphysics.so"},
        },
    )
    _write_json(
        project / "gameplay" / "gameplay.pymodule",
        {
            "name": "gameplay",
            "dependencies": ["physics"],
            "root": "python",
            "packages": ["gameplay"],
            "requirements": ["attrs>=24"],
        },
    )
    package_dir = project / "gameplay" / "python" / "gameplay"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    _write_json(
        project / "unused.pymodule",
        {"name": "unused", "root": ".", "packages": ["unused_package"]},
    )
    (project / "unused_package.py").write_text("UNUSED = True\n", encoding="utf-8")

    result = package_project_modules(project, tmp_path / "bundle" / "modules", ["gameplay"])

    assert result.diagnostics == []
    assert [module.name for module in result.modules] == ["physics", "gameplay"]
    assert result.requirements == ("attrs>=24",)
    assert (result.root_dir / "native" / "libphysics.so").read_bytes() == b"native-module"
    assert (result.root_dir / "python" / "gameplay" / "__init__.py").exists()
    assert not (result.root_dir / "python" / "unused_package.py").exists()
    native_descriptor = json.loads(
        (result.root_dir / "descriptors" / "physics.module").read_text(encoding="utf-8")
    )
    assert native_descriptor["build"] == {
        "command": "",
        "clean_command": "",
        "output": "../native/libphysics.so",
    }
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["roots"] == ["gameplay"]
    assert manifest["closure"] == ["physics", "gameplay"]
    assert [module["kind"] for module in manifest["modules"]] == ["cpp", "python"]


def test_rejects_missing_selected_module(tmp_path: Path) -> None:
    project = tmp_path / "Game"
    project.mkdir()

    result = package_project_modules(project, tmp_path / "bundle" / "modules", ["missing"])

    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].level == "error"
    assert result.diagnostics[0].message == "Selected module not found: missing"
    assert result.modules == []


def test_rejects_duplicate_module_identity(tmp_path: Path) -> None:
    project = tmp_path / "Game"
    _write_json(project / "a.pymodule", {"name": "same", "packages": []})
    _write_json(project / "nested" / "b.pymodule", {"name": "same", "packages": []})

    result = package_project_modules(project, tmp_path / "bundle" / "modules", ["same"])

    assert len(result.diagnostics) == 1
    assert "Duplicate module id 'same'" in result.diagnostics[0].message
    assert "a.pymodule" in result.diagnostics[0].message
    assert "b.pymodule" in result.diagnostics[0].message


def test_rejects_cycle_in_selected_closure(tmp_path: Path) -> None:
    project = tmp_path / "Game"
    _write_json(
        project / "a.pymodule",
        {"name": "a", "dependencies": ["b"], "packages": []},
    )
    _write_json(
        project / "b.pymodule",
        {"name": "b", "dependencies": ["a"], "packages": []},
    )

    result = package_project_modules(project, tmp_path / "bundle" / "modules", ["a"])

    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].message == "Dependency cycle detected: a -> b -> a"
    assert result.modules == []
