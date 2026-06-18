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


def test_validate_runtime_package_accepts_shader_artifacts(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_json(
        package_dir / "shaders" / "shader-uuid.shader.json",
        {
            "uuid": "shader-uuid",
            "artifacts": {
                "vulkan": {
                    "vertex": "shaders/vulkan/shader-uuid.vert.spv",
                    "fragment": "shaders/vulkan/shader-uuid.frag.spv",
                },
                "opengl": {
                    "vertex": "shaders/opengl/shader-uuid.vert.glsl",
                    "fragment": "shaders/opengl/shader-uuid.frag.glsl",
                },
            },
        },
    )
    (package_dir / "shaders" / "vulkan").mkdir(parents=True)
    (package_dir / "shaders" / "vulkan" / "shader-uuid.vert.spv").write_bytes(b"VERT")
    (package_dir / "shaders" / "vulkan" / "shader-uuid.frag.spv").write_bytes(b"FRAG")
    (package_dir / "shaders" / "opengl").mkdir(parents=True)
    (package_dir / "shaders" / "opengl" / "shader-uuid.vert.glsl").write_text("void main() {}", encoding="utf-8")
    (package_dir / "shaders" / "opengl" / "shader-uuid.frag.glsl").write_text("void main() {}", encoding="utf-8")
    _write_json(
        package_dir / "manifest.json",
        {
            "version": 1,
            "scene": "scene.json",
            "resources": [
                {
                    "type": "shader",
                    "uuid": "shader-uuid",
                    "path": "shaders/shader-uuid.shader.json",
                }
            ],
        },
    )

    assert validate_runtime_package(package_dir) == []


def test_validate_runtime_package_reports_missing_shader_artifact(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_json(
        package_dir / "shaders" / "shader-uuid.shader.json",
        {
            "uuid": "shader-uuid",
            "artifacts": {
                "vulkan": {
                    "vertex": "shaders/vulkan/shader-uuid.vert.spv",
                }
            },
        },
    )
    _write_json(
        package_dir / "manifest.json",
        {
            "version": 1,
            "scene": "scene.json",
            "resources": [
                {
                    "type": "shader",
                    "uuid": "shader-uuid",
                    "path": "shaders/shader-uuid.shader.json",
                }
            ],
        },
    )

    diagnostics = validate_runtime_package(package_dir)

    assert [(diagnostic.level, diagnostic.path, diagnostic.message) for diagnostic in diagnostics] == [
        (
            "error",
            "shaders/vulkan/shader-uuid.vert.spv",
            "Runtime package path does not exist: shaders/vulkan/shader-uuid.vert.spv",
        )
    ]
