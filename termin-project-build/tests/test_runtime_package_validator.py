import json
import struct
from pathlib import Path

import pytest

from termin.project_build.runtime_package_validator import validate_runtime_package


SCENE_IDENTITY = "Scenes/Main.scene"
SCENE_PATH = "scenes/Scenes/Main.scene.json"


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _scene_manifest(
    *,
    identity: str = SCENE_IDENTITY,
    path: str = SCENE_PATH,
) -> dict[str, object]:
    return {
        "version": 2,
        "entry_scene": identity,
        "scenes": [{"identity": identity, "path": path}],
    }


def _write_valid_package(tmp_path: Path) -> Path:
    package_dir = tmp_path / "package"
    _write_json(package_dir / SCENE_PATH, {"uuid": "scene"})
    _write_json(package_dir / "meshes" / "mesh-uuid.tmesh.json", {"uuid": "mesh-uuid"})
    _write_json(
        package_dir / "manifest.json",
        {
            **_scene_manifest(),
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


def _write_shader_program_resource(package_dir: Path, schema_version: int = 1) -> None:
    _write_json(
        package_dir / "shaders" / "program-uuid.shader-program.json",
        {
            "schema_version": schema_version,
            "uuid": "program-uuid",
            "name": "Program",
            "language": "slang",
            "features": 0,
            "properties": [],
            "phases": [
                {
                    "phase_mark": "opaque",
                    "priority": 0,
                    "shader": "shader-uuid",
                    "state": {},
                }
            ],
        },
    )


def _pipeline_template_payload(*, dependency_pass_index: int = 0) -> bytes:
    payload = bytearray(b"TPLT")

    def u32(value: int) -> None:
        payload.extend(struct.pack("<I", value))

    def i32(value: int) -> None:
        payload.extend(struct.pack("<i", value))

    def f32(value: float) -> None:
        payload.extend(struct.pack("<f", value))

    def text(value: str) -> None:
        encoded = value.encode("utf-8")
        u32(len(encoded))
        payload.extend(encoded)

    u32(1)  # binary version
    u32(1)  # descriptor version
    text("Compiled Pipeline")
    u32(1)  # passes
    u32(1)  # resources
    u32(1)  # dependencies
    u32(1)  # targets
    text("ColorPass")
    text("color")
    text('{"phase_mark":"opaque"}')
    text("main")
    text("OUTPUT")
    text("external_color")
    text("")
    text("main")
    i32(0)
    i32(0)
    f32(1.0)
    u32(1)
    u32(0)
    u32(dependency_pass_index)
    text("OUTPUT")
    u32(2)
    text("main")
    text("final-color")
    i32(0)
    i32(0)
    return bytes(payload)


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
            **_scene_manifest(path="../scene.json"),
            "resources": [],
        },
    )

    diagnostics = validate_runtime_package(package_dir)

    assert [(diagnostic.level, diagnostic.path, diagnostic.message) for diagnostic in diagnostics] == [
        (
            "error",
            "scenes[0].path",
            "Runtime package path escapes package root: ../scene.json",
        )
    ]


def test_validate_runtime_package_rejects_missing_entry_and_duplicate_scene_identity(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_json(package_dir / "scenes/Scenes/Menu.scene.json", {"uuid": "menu"})
    _write_json(
        package_dir / "manifest.json",
        {
            "version": 2,
            "entry_scene": "Scenes/Missing.scene",
            "scenes": [
                {"identity": SCENE_IDENTITY, "path": SCENE_PATH},
                {
                    "identity": SCENE_IDENTITY,
                    "path": "scenes/Scenes/Menu.scene.json",
                },
            ],
            "resources": [],
        },
    )

    diagnostics = validate_runtime_package(package_dir)

    assert [(diagnostic.path, diagnostic.message) for diagnostic in diagnostics] == [
        ("scenes[1].identity", f"Duplicate runtime scene identity '{SCENE_IDENTITY}'"),
        (
            "entry_scene",
            "Runtime package entry scene 'Scenes/Missing.scene' is absent from the scene table",
        ),
    ]


@pytest.mark.parametrize(
    "identity",
    ["../Main.scene", "Scenes\\Main.scene", "C:/Scenes/Main.scene"],
)
def test_validate_runtime_package_rejects_non_portable_scene_identity(
    tmp_path: Path,
    identity: str,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_json(
        package_dir / "manifest.json",
        {
            **_scene_manifest(identity=identity),
            "resources": [],
        },
    )

    diagnostics = validate_runtime_package(package_dir)

    assert diagnostics[0].path == "scenes[0].identity"
    assert diagnostics[0].message == (
        "Runtime package scene identity must be a normalized project-relative .scene path: "
        f"{identity}"
    )


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
            **_scene_manifest(),
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
            **_scene_manifest(),
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


def test_validate_runtime_package_accepts_versioned_shader_program(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_shader_resource(package_dir)
    _write_shader_program_resource(package_dir)
    _write_json(
        package_dir / "manifest.json",
        {
            **_scene_manifest(),
            "resources": [
                {
                    "type": "shader",
                    "uuid": "shader-uuid",
                    "path": "shaders/shader-uuid.shader.json",
                },
                {
                    "type": "shader_program",
                    "uuid": "program-uuid",
                    "path": "shaders/program-uuid.shader-program.json",
                },
            ],
        },
    )

    assert validate_runtime_package(package_dir) == []


def test_validate_runtime_package_rejects_incompatible_shader_program_schema(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_shader_resource(package_dir)
    _write_shader_program_resource(package_dir, schema_version=99)
    _write_json(
        package_dir / "manifest.json",
        {
            **_scene_manifest(),
            "resources": [
                {
                    "type": "shader",
                    "uuid": "shader-uuid",
                    "path": "shaders/shader-uuid.shader.json",
                },
                {
                    "type": "shader_program",
                    "uuid": "program-uuid",
                    "path": "shaders/program-uuid.shader-program.json",
                },
            ],
        },
    )

    diagnostics = validate_runtime_package(package_dir)
    assert any(
        diagnostic.path == "shaders/program-uuid.shader-program.json"
        and diagnostic.message == "Runtime shader program spec requires schema_version 1"
        for diagnostic in diagnostics
    )


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
            **_scene_manifest(),
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
        package_dir / SCENE_PATH,
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
                f"scenes[{SCENE_IDENTITY}].entities[0].components[0].data.material",
            "Runtime package references missing material resource uuid 'missing-material'",
        )
    ]


def test_validate_runtime_package_rejects_legacy_scene_resource_ref(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_json(
        package_dir / SCENE_PATH,
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
                f"scenes[{SCENE_IDENTITY}].entities[0].components[0].data.material",
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
            **_scene_manifest(),
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
            **_scene_manifest(),
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


def test_validate_runtime_package_accepts_compiled_pipeline_template(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    pipeline_path = package_dir / "pipelines" / "pipeline-uuid.pipeline-template"
    pipeline_path.parent.mkdir(parents=True, exist_ok=True)
    pipeline_path.write_bytes(_pipeline_template_payload())
    _write_json(
        package_dir / "manifest.json",
        {
            **_scene_manifest(),
            "resources": [
                {
                    "type": "pipeline",
                    "uuid": "pipeline-uuid",
                    "path": "pipelines/pipeline-uuid.pipeline-template",
                }
            ],
        },
    )

    assert validate_runtime_package(package_dir) == []


def test_validate_runtime_package_checks_canonical_scene_pipeline_template_ref(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_json(
        package_dir / SCENE_PATH,
        {
            "uuid": "scene",
            "extensions": {
                "render_mount": {
                    "pipeline_templates": [{"uuid": "missing-pipeline"}]
                }
            },
        },
    )

    diagnostics = validate_runtime_package(package_dir)
    assert len(diagnostics) == 1
    assert diagnostics[0].path.endswith("pipeline_templates[0].uuid")
    assert "missing pipeline resource uuid 'missing-pipeline'" in diagnostics[0].message


def test_validate_runtime_package_rejects_authored_or_malformed_pipeline_payload(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    pipeline_path = package_dir / "pipelines" / "pipeline-uuid.pipeline-template"
    pipeline_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(pipeline_path, {"passes": [], "nodes": []})
    _write_json(
        package_dir / "manifest.json",
        {
            **_scene_manifest(),
            "resources": [
                {
                    "type": "pipeline",
                    "uuid": "pipeline-uuid",
                    "path": "pipelines/pipeline-uuid.pipeline-template",
                }
            ],
        },
    )

    diagnostics = validate_runtime_package(package_dir)
    assert [(diagnostic.level, diagnostic.path, diagnostic.message) for diagnostic in diagnostics] == [
        (
            "error",
            "pipelines/pipeline-uuid.pipeline-template",
            "Runtime pipeline template descriptor is invalid: descriptor magic must be TPLT",
        )
    ]

    pipeline_path.write_bytes(_pipeline_template_payload(dependency_pass_index=7))
    diagnostics = validate_runtime_package(package_dir)
    assert len(diagnostics) == 1
    assert "dependency 0 references missing pass 7" in diagnostics[0].message


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
            **_scene_manifest(),
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
