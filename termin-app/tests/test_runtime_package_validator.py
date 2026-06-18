import json
from pathlib import Path

from termin.project_build.runtime_package_validator import validate_runtime_package


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_valid_package(tmp_path: Path) -> Path:
    package_dir = tmp_path / "package"
    _write_json(package_dir / "scene.json", {"uuid": "scene"})
    _write_json(package_dir / "meshes" / "mesh-uuid.tmesh.json", {"uuid": "mesh-uuid"})
    _write_json(
        package_dir / "manifest.json",
        {
            "version": 1,
            "scene": "scene.json",
            "resources": [
                {
                    "type": "mesh",
                    "uuid": "mesh-uuid",
                    "path": "meshes/mesh-uuid.tmesh.json",
                }
            ],
        },
    )
    return package_dir


def test_validate_runtime_package_accepts_valid_package(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)

    assert validate_runtime_package(package_dir) == []


def test_validate_runtime_package_reports_missing_resource_file(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    (package_dir / "meshes" / "mesh-uuid.tmesh.json").unlink()

    diagnostics = validate_runtime_package(package_dir)

    assert [(diagnostic.level, diagnostic.path, diagnostic.message) for diagnostic in diagnostics] == [
        (
            "error",
            "meshes/mesh-uuid.tmesh.json",
            "Runtime package path does not exist: meshes/mesh-uuid.tmesh.json",
        )
    ]


def test_validate_runtime_package_rejects_path_escape(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_json(
        package_dir / "manifest.json",
        {
            "version": 1,
            "scene": "../scene.json",
            "resources": [],
        },
    )

    diagnostics = validate_runtime_package(package_dir)

    assert [(diagnostic.level, diagnostic.path, diagnostic.message) for diagnostic in diagnostics] == [
        (
            "error",
            "scene",
            "Runtime package path escapes package root: ../scene.json",
        )
    ]


def test_validate_runtime_package_rejects_duplicate_resource_uuid(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_json(package_dir / "materials" / "mesh-uuid.tmat.json", {"uuid": "mesh-uuid"})
    _write_json(
        package_dir / "manifest.json",
        {
            "version": 1,
            "scene": "scene.json",
            "resources": [
                {
                    "type": "mesh",
                    "uuid": "mesh-uuid",
                    "path": "meshes/mesh-uuid.tmesh.json",
                },
                {
                    "type": "material",
                    "uuid": "mesh-uuid",
                    "path": "materials/mesh-uuid.tmat.json",
                },
            ],
        },
    )

    diagnostics = validate_runtime_package(package_dir)

    assert [(diagnostic.level, diagnostic.path, diagnostic.message) for diagnostic in diagnostics] == [
        (
            "error",
            "resources[1]",
            "Duplicate runtime package resource uuid 'mesh-uuid' also declared at resources[0]",
        )
    ]

