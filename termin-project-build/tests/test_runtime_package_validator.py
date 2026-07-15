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


def _write_shader_resource(package_dir: Path, shader_uuid: str = "shader-uuid") -> None:
    _write_json(
        package_dir / "shaders" / f"{shader_uuid}.shader.json",
        {
            "uuid": shader_uuid,
            "vertex_source_path": f"shaders/vulkan/{shader_uuid}.vert.slang",
            "fragment_source_path": f"shaders/vulkan/{shader_uuid}.frag.slang",
            "artifacts": {
                "vulkan": {
                    "vertex": f"shaders/vulkan/{shader_uuid}.vert.spv",
                    "fragment": f"shaders/vulkan/{shader_uuid}.frag.spv",
                },
                "opengl": {
                    "vertex": f"shaders/opengl/{shader_uuid}.vert.glsl",
                    "fragment": f"shaders/opengl/{shader_uuid}.frag.glsl",
                },
            },
        },
    )
    (package_dir / "shaders" / "vulkan").mkdir(parents=True, exist_ok=True)
    (package_dir / "shaders" / "vulkan" / f"{shader_uuid}.vert.slang").write_text(
        "void main() {}",
        encoding="utf-8",
    )
    (package_dir / "shaders" / "vulkan" / f"{shader_uuid}.frag.slang").write_text(
        "void main() {}",
        encoding="utf-8",
    )
    (package_dir / "shaders" / "vulkan" / f"{shader_uuid}.vert.spv").write_bytes(b"VERT")
    (package_dir / "shaders" / "vulkan" / f"{shader_uuid}.frag.spv").write_bytes(b"FRAG")
    (package_dir / "shaders" / "opengl").mkdir(parents=True, exist_ok=True)
    (package_dir / "shaders" / "opengl" / f"{shader_uuid}.vert.glsl").write_text(
        "void main() {}",
        encoding="utf-8",
    )
    (package_dir / "shaders" / "opengl" / f"{shader_uuid}.frag.glsl").write_text(
        "void main() {}",
        encoding="utf-8",
    )


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
    _write_json(
        package_dir / "materials" / "mesh-uuid.tmat.json",
        {
            "uuid": "mesh-uuid",
            "phases": [
                {
                    "mark": "opaque",
                    "shader": "shader-uuid",
                    "priority": 0,
                }
            ],
        },
    )
    _write_shader_resource(package_dir)
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
                {
                    "type": "shader",
                    "uuid": "shader-uuid",
                    "path": "shaders/shader-uuid.shader.json",
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
    _write_shader_resource(package_dir)
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
    (package_dir / "shaders" / "vulkan").mkdir(parents=True)
    (package_dir / "shaders" / "vulkan" / "shader-uuid.vert.slang").write_text(
        "void main() {}",
        encoding="utf-8",
    )
    (package_dir / "shaders" / "vulkan" / "shader-uuid.frag.slang").write_text(
        "void main() {}",
        encoding="utf-8",
    )
    _write_json(
        package_dir / "shaders" / "shader-uuid.shader.json",
        {
            "uuid": "shader-uuid",
            "vertex_source_path": "shaders/vulkan/shader-uuid.vert.slang",
            "fragment_source_path": "shaders/vulkan/shader-uuid.frag.slang",
            "artifacts": {
                "vulkan": {
                    "fragment": "shaders/vulkan/shader-uuid.frag.spv",
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
            "shaders/vulkan/shader-uuid.frag.spv",
            "Runtime package path does not exist: shaders/vulkan/shader-uuid.frag.spv",
        ),
        (
            "error",
            "shaders/vulkan/shader-uuid.vert.spv",
            "Runtime package path does not exist: shaders/vulkan/shader-uuid.vert.spv",
        ),
    ]


def test_validate_runtime_package_reports_scene_missing_material_resource(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_json(
        package_dir / "scene.json",
        {
            "uuid": "scene",
            "entities": [
                {
                    "components": [
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "material": {
                                    "type": "uuid",
                                    "uuid": "missing-material",
                                    "name": "Missing Material",
                                    "kind": "tc_material",
                                }
                            },
                        }
                    ]
                }
            ],
        },
    )

    diagnostics = validate_runtime_package(package_dir)

    assert [(diagnostic.level, diagnostic.path, diagnostic.message) for diagnostic in diagnostics] == [
        (
            "error",
            "scene.entities[0].components[0].data.material",
            "Runtime package references missing material resource uuid 'missing-material'",
        )
    ]


def test_validate_runtime_package_rejects_legacy_scene_resource_ref(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_json(
        package_dir / "scene.json",
        {
            "uuid": "scene",
            "entities": [
                {
                    "components": [
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "material": {
                                    "type": "uuid",
                                    "uuid": "missing-material",
                                    "name": "Missing Material",
                                }
                            },
                        }
                    ]
                }
            ],
        },
    )

    diagnostics = validate_runtime_package(package_dir)

    assert [(diagnostic.level, diagnostic.path, diagnostic.message) for diagnostic in diagnostics] == [
        (
            "error",
            "scene.entities[0].components[0].data.material",
            "Runtime package rejected legacy material resource ref from legacy field name; "
            "add kind='tc_material' or role='material' to the uuid ref",
        )
    ]


def test_validate_runtime_package_reports_material_phase_missing_shader(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_json(
        package_dir / "materials" / "material-uuid.tmat.json",
        {
            "uuid": "material-uuid",
            "phases": [
                {
                    "mark": "opaque",
                    "shader": "missing-shader",
                    "priority": 0,
                }
            ],
        },
    )
    _write_json(
        package_dir / "manifest.json",
        {
            "version": 1,
            "scene": "scene.json",
            "resources": [
                {
                    "type": "material",
                    "uuid": "material-uuid",
                    "path": "materials/material-uuid.tmat.json",
                }
            ],
        },
    )

    diagnostics = validate_runtime_package(package_dir)

    assert [(diagnostic.level, diagnostic.path, diagnostic.message) for diagnostic in diagnostics] == [
        (
            "error",
            "materials/material-uuid.tmat.json:phases[0].shader",
            "Runtime package references missing shader resource uuid 'missing-shader'",
        )
    ]


def test_validate_runtime_package_checks_texture_resource_and_material_reference(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_json(
        package_dir / "materials" / "material-uuid.tmat.json",
        {
            "uuid": "material-uuid",
            "phases": [{"mark": "opaque", "shader": "shader-uuid", "priority": 0}],
            "textures": {
                "u_albedo": {"kind": "asset", "uuid": "texture-uuid", "name": "Albedo"},
            },
        },
    )
    _write_shader_resource(package_dir)
    _write_json(
        package_dir / "textures" / "texture-uuid.texture.json",
        {
            "uuid": "texture-uuid",
            "name": "Albedo",
            "source_path": "textures/texture-uuid.png",
            "import_settings": {"flip_x": False, "flip_y": True, "transpose": False},
        },
    )
    (package_dir / "textures" / "texture-uuid.png").write_bytes(b"PNG")
    _write_json(
        package_dir / "manifest.json",
        {
            "version": 1,
            "scene": "scene.json",
            "resources": [
                {"type": "shader", "uuid": "shader-uuid", "path": "shaders/shader-uuid.shader.json"},
                {"type": "material", "uuid": "material-uuid", "path": "materials/material-uuid.tmat.json"},
                {"type": "texture", "uuid": "texture-uuid", "path": "textures/texture-uuid.texture.json"},
            ],
        },
    )

    assert validate_runtime_package(package_dir) == []

    (package_dir / "textures" / "texture-uuid.png").unlink()
    diagnostics = validate_runtime_package(package_dir)

    assert [(diagnostic.level, diagnostic.path, diagnostic.message) for diagnostic in diagnostics] == [
        (
            "error",
            "textures/texture-uuid.png",
            "Runtime package path does not exist: textures/texture-uuid.png",
        )
    ]


def test_validate_runtime_package_reports_pipeline_missing_shader_resource(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_json(
        package_dir / "pipelines" / "pipeline-uuid.pipeline.json",
        {
            "uuid": "pipeline-uuid",
            "phases": [
                {
                    "mark": "opaque",
                    "shader": "missing-shader",
                }
            ],
        },
    )
    _write_json(
        package_dir / "manifest.json",
        {
            "version": 1,
            "scene": "scene.json",
            "resources": [
                {
                    "type": "pipeline",
                    "uuid": "pipeline-uuid",
                    "path": "pipelines/pipeline-uuid.pipeline.json",
                }
            ],
        },
    )

    diagnostics = validate_runtime_package(package_dir)

    assert [(diagnostic.level, diagnostic.path, diagnostic.message) for diagnostic in diagnostics] == [
        (
            "error",
            "pipelines/pipeline-uuid.pipeline.json:phases[0].shader",
            "Runtime package references missing shader resource uuid 'missing-shader'",
        )
    ]


def test_validate_runtime_package_reports_required_shader_target_missing(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_shader_resource(package_dir)
    shader_spec_path = package_dir / "shaders" / "shader-uuid.shader.json"
    shader_spec = json.loads(shader_spec_path.read_text(encoding="utf-8"))
    del shader_spec["artifacts"]["opengl"]
    _write_json(shader_spec_path, shader_spec)
    _write_json(
        package_dir / "manifest.json",
        {
            "version": 1,
            "scene": "scene.json",
            "target_requirements": {
                "shader_targets": ["vulkan", "opengl"],
            },
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
            "shaders/shader-uuid.shader.json",
            "Runtime shader 'shader-uuid' is missing required target artifacts: opengl",
        )
    ]
