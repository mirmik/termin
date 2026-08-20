import json
import struct
from pathlib import Path

import pytest

from termin.project_build import runtime_package_resource_validator
from termin.project_build.runtime_package_resource_validator import (
    SceneComponentFactoryPolicy,
)
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
        "version": 3,
        "entry_scene": identity,
        "world_controller": None,
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


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (False, "must be null or an object"),
        ({}, "requires exactly module and type"),
        ({"module": "game", "type": "Director", "extra": True}, "requires exactly"),
        ({"module": " game ", "type": "Director"}, "must be a non-empty trimmed string"),
        ({"module": "game", "type": ""}, "must be a non-empty trimmed string"),
    ],
)
def test_validate_runtime_package_rejects_invalid_world_controller(
    tmp_path: Path,
    value: object,
    message: str,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    manifest_path = package_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["world_controller"] = value
    _write_json(manifest_path, manifest)

    diagnostics = validate_runtime_package(package_dir)

    assert any(
        diagnostic.path.startswith("world_controller")
        and message in diagnostic.message
        for diagnostic in diagnostics
    )


def test_validate_runtime_package_requires_explicit_world_controller_and_v3(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    manifest_path = package_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("world_controller")
    manifest["version"] = 2
    _write_json(manifest_path, manifest)

    diagnostics = validate_runtime_package(package_dir)

    assert any("supported version is 3" in item.message for item in diagnostics)
    assert any(
        item.path == "world_controller" and "explicitly define" in item.message
        for item in diagnostics
    )


def _write_shader_resource(package_dir: Path, shader_uuid: str = "shader-uuid") -> None:
    _write_json(
        package_dir / "shaders" / f"{shader_uuid}.shader.json",
        {
            "uuid": shader_uuid,
            "language": "slang",
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


def _write_builtin_shader_contract(package_dir: Path) -> None:
    manifest_path = package_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["target_requirements"] = {"backends": ["vulkan"]}
    manifest["builtin_shader_contract"] = {
        "version": 1,
        "catalog": "builtin_shaders/engine-shader-catalog.json",
        "shaders": [
            {
                "uuid": "termin-engine-test",
                "artifacts": {
                    "vulkan": {
                        "fragment": "shaders/vulkan/termin-engine-test.frag.spv",
                    }
                },
            }
        ],
    }
    _write_json(manifest_path, manifest)
    _write_json(
        package_dir / "builtin_shaders" / "engine-shader-catalog.json",
        {
            "version": 1,
            "shaders": [
                {
                    "uuid": "termin-engine-test",
                    "name": "TestFS",
                    "language": "slang",
                    "runtime_sources": ["termin-engine-test.frag.slang"],
                    "stages": {
                        "fragment": {
                            "path": "termin-engine-test.frag.slang",
                            "entry": "fs_main",
                        }
                    },
                }
            ],
        },
    )
    artifact = package_dir / "shaders" / "vulkan" / "termin-engine-test.frag.spv"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"SPIR-V")
    (
        package_dir
        / "builtin_shaders"
        / "termin-engine-test.frag.slang"
    ).write_text("// runtime source\n", encoding="utf-8")


def _pipeline_template_payload(
    *,
    binary_version: int = 4,
    descriptor_version: int = 4,
    dependency_pass_index: int = 0,
    target_color_content: int = 1,
) -> bytes:
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

    u32(binary_version)
    u32(descriptor_version)
    u32(1)  # single-view execution model
    text("Compiled Pipeline")
    u32(1)  # passes
    u32(1)  # resources
    u32(1)  # dependencies
    u32(1)  # targets
    u32(0)  # resource views
    u32(0)  # FBO compositions
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
    u32(1)
    u32(0)
    u32(dependency_pass_index)
    text("OUTPUT")
    u32(2)
    text("main")
    text("final-color")
    u32(target_color_content)
    i32(0)
    i32(0)
    return bytes(payload)


def test_pipeline_template_decoder_accepts_complete_v4_target_layout() -> None:
    decoded = runtime_package_resource_validator._decode_pipeline_template(
        _pipeline_template_payload(target_color_content=2)
    )

    assert decoded["binary_version"] == 4
    assert decoded["descriptor_version"] == 4
    assert decoded["targets"] == [
        {
            "viewport_name": "main",
            "export_name": "final-color",
            "color_content": 2,
            "width": 0,
            "height": 0,
        }
    ]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (_pipeline_template_payload(binary_version=5), "unsupported binary version 5"),
        (
            _pipeline_template_payload(descriptor_version=5),
            "unsupported descriptor version 5",
        ),
        (
            _pipeline_template_payload(target_color_content=3),
            "target 0 has invalid color content 3",
        ),
        (_pipeline_template_payload()[:-1], "descriptor is truncated"),
        (_pipeline_template_payload() + b"\x00", "descriptor contains trailing data"),
    ],
)
def test_pipeline_template_decoder_strictly_rejects_invalid_v4_payloads(
    payload: bytes,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        runtime_package_resource_validator._decode_pipeline_template(payload)


def test_validate_runtime_package_accepts_valid_package(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)

    assert validate_runtime_package(package_dir) == []


def _add_ui_document(
    package_dir: Path,
    *,
    type_name: str = "termin.gui.Label",
) -> None:
    ui_path = "ui/native-hud.ui-document.json"
    _write_json(
        package_dir / ui_path,
        {
            "ui_document_asset": 1,
            "uuid": "native-hud",
            "name": "Native HUD",
            "source_identity": "UI/native-hud.uiscript",
            "revision": 1,
            "type_dependencies": [type_name],
            "recipe": {
                "uiscript": 2,
                "root": {
                    "type": type_name,
                    "name": "root",
                    "children": [],
                },
            },
        },
    )
    manifest_path = package_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["resources"].append(
        {
            "type": "ui_document",
            "uuid": "native-hud",
            "path": ui_path,
        }
    )
    _write_json(manifest_path, manifest)


def test_validate_runtime_package_accepts_native_ui_factory_contract(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _add_ui_document(package_dir)
    ui_path = package_dir / "ui/native-hud.ui-document.json"
    payload = json.loads(ui_path.read_text(encoding="utf-8"))
    payload["type_dependencies"] = [
        "termin.gui.ScrollArea",
        "termin.gui.GridLayout",
        "termin.gui.Panel",
    ]
    payload["recipe"]["root"] = {
        "type": "termin.gui.ScrollArea",
        "name": "root",
        "children": [
            {
                "type": "termin.gui.GridLayout",
                "columns": [{"policy": "stretch"}],
                "rows": [{"policy": "stretch"}],
                "children": [
                    {
                        "type": "termin.gui.Panel",
                        "row": 0,
                        "column": 0,
                        "children": [],
                    }
                ],
            }
        ],
    }
    _write_json(ui_path, payload)

    assert validate_runtime_package(package_dir) == []


def test_validate_runtime_package_rejects_missing_native_ui_factory(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _add_ui_document(package_dir, type_name="termin.gui.MissingWidget")

    diagnostics = validate_runtime_package(package_dir)

    assert any(
        diagnostic.level == "error"
        and "factory is not registered" in diagnostic.message
        and "termin.gui.MissingWidget" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_validate_runtime_package_rejects_python_ui_factory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import termin.gui_native

    package_dir = _write_valid_package(tmp_path)
    _add_ui_document(package_dir, type_name="project.PythonWidget")
    native_info = termin.gui_native.widget_type_info

    def widget_type_info(type_name: str):
        if type_name == "project.PythonWidget":
            return {
                "registered": True,
                "language": "python",
                "uiscript": True,
            }
        return native_info(type_name)

    monkeypatch.setattr(termin.gui_native, "widget_type_info", widget_type_info)

    diagnostics = validate_runtime_package(package_dir)

    assert any(
        diagnostic.level == "error"
        and "requires a C++ widget factory" in diagnostic.message
        and "project.PythonWidget" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_validate_runtime_package_rejects_missing_component_factory(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_json(
        package_dir / SCENE_PATH,
        {
            "uuid": "scene",
            "entities": [
                {
                    "uuid": "entity",
                    "components": [
                        {"type": "MissingPackagedComponent", "data": {}},
                    ],
                    "children": [],
                }
            ],
        },
    )

    diagnostics = validate_runtime_package(package_dir)

    assert any(
        diagnostic.level == "error"
        and "factory is not registered" in diagnostic.message
        and "MissingPackagedComponent" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_validate_runtime_package_applies_python_factory_owner_policy(
    tmp_path: Path,
) -> None:
    from termin.bootstrap import bootstrap_player
    from termin.scene import ComponentRegistry, PythonComponent, publish_python_component
    from termin.scene.python_component import unregister_python_component_owner

    bootstrap_player()
    owner = "packaged-gameplay"

    class PackagedPythonProbe(PythonComponent):
        pass

    registry = ComponentRegistry.instance()
    publish_python_component(PackagedPythonProbe, owner=owner)
    package_dir = _write_valid_package(tmp_path)
    _write_json(
        package_dir / SCENE_PATH,
        {
            "uuid": "scene",
            "entities": [
                {
                    "uuid": "entity",
                    "components": [
                        {"type": "PackagedPythonProbe", "data": {}},
                    ],
                    "children": [],
                }
            ],
        },
    )

    try:
        native_only = validate_runtime_package(package_dir)
        assert any(
            diagnostic.level == "error"
            and "does not support python component factory" in diagnostic.message
            for diagnostic in native_only
        )

        wrong_owner = validate_runtime_package(
            package_dir,
            component_factory_policy=SceneComponentFactoryPolicy(
                allowed_kinds=frozenset({"cxx", "python"}),
                allowed_python_owners=frozenset({"another-module"}),
            ),
        )
        assert any(
            diagnostic.level == "error"
            and "owned by unpackaged module" in diagnostic.message
            and owner in diagnostic.message
            for diagnostic in wrong_owner
        )

        allowed = validate_runtime_package(
            package_dir,
            component_factory_policy=SceneComponentFactoryPolicy(
                allowed_kinds=frozenset({"cxx", "python"}),
                allowed_python_owners=frozenset({owner}),
            ),
        )
        assert allowed == []
    finally:
        registry.unregister_python("PackagedPythonProbe")
        unregister_python_component_owner(owner)


def test_validate_runtime_package_accepts_builtin_shader_contract(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_builtin_shader_contract(package_dir)

    assert validate_runtime_package(package_dir) == []


def test_validate_runtime_package_reports_missing_builtin_shader_artifact(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_builtin_shader_contract(package_dir)
    (
        package_dir
        / "shaders"
        / "vulkan"
        / "termin-engine-test.frag.spv"
    ).unlink()

    diagnostics = validate_runtime_package(package_dir)

    assert any(
        diagnostic.level == "error"
        and diagnostic.path == "shaders/vulkan/termin-engine-test.frag.spv"
        and "does not exist" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_validate_runtime_package_reports_missing_builtin_shader_catalog(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_builtin_shader_contract(package_dir)
    (
        package_dir
        / "builtin_shaders"
        / "engine-shader-catalog.json"
    ).unlink()

    diagnostics = validate_runtime_package(package_dir)

    assert any(
        diagnostic.level == "error"
        and diagnostic.path == "builtin_shaders/engine-shader-catalog.json"
        and "does not exist" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_validate_runtime_package_reports_missing_builtin_shader_runtime_source(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_builtin_shader_contract(package_dir)
    (
        package_dir
        / "builtin_shaders"
        / "termin-engine-test.frag.slang"
    ).unlink()

    diagnostics = validate_runtime_package(package_dir)

    assert any(
        diagnostic.level == "error"
        and diagnostic.path == "builtin_shaders/termin-engine-test.frag.slang"
        and "does not exist" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_validate_runtime_package_accepts_bundled_android_smoke_assets() -> None:
    package_dir = (
        Path(__file__).parents[3] / "platform" / "termin-android" / "assets"
    )

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
            "version": 3,
            "entry_scene": "Scenes/Missing.scene",
            "world_controller": None,
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


def test_validate_runtime_package_accepts_fragment_only_shader_artifacts(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_shader_resource(package_dir)
    shader_path = package_dir / "shaders" / "shader-uuid.shader.json"
    shader_spec = json.loads(shader_path.read_text(encoding="utf-8"))
    del shader_spec["vertex_source_path"]
    for artifacts in shader_spec["artifacts"].values():
        del artifacts["vertex"]
    _write_json(shader_path, shader_spec)
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


def test_validate_runtime_package_rejects_artifact_without_stage_source(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_shader_resource(package_dir)
    shader_path = package_dir / "shaders" / "shader-uuid.shader.json"
    shader_spec = json.loads(shader_path.read_text(encoding="utf-8"))
    del shader_spec["vertex_source_path"]
    _write_json(shader_path, shader_spec)
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

    assert any(
        diagnostic.path
        == "shaders/shader-uuid.shader.json:artifacts.vulkan.vertex"
        and "has no corresponding 'vertex_source_path'" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_validate_runtime_package_rejects_stage_source_without_artifact(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_shader_resource(package_dir)
    shader_path = package_dir / "shaders" / "shader-uuid.shader.json"
    shader_spec = json.loads(shader_path.read_text(encoding="utf-8"))
    for artifacts in shader_spec["artifacts"].values():
        del artifacts["vertex"]
    _write_json(shader_path, shader_spec)
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

    assert {
        diagnostic.path
        for diagnostic in diagnostics
        if diagnostic.message
        == "Runtime shader artifact target must contain 'vertex' stage"
    } == {
        "shaders/shader-uuid.shader.json:artifacts.vulkan",
        "shaders/shader-uuid.shader.json:artifacts.opengl",
    }


def test_validate_runtime_package_rejects_shader_without_explicit_language(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_shader_resource(package_dir)
    shader_path = package_dir / "shaders" / "shader-uuid.shader.json"
    shader_spec = json.loads(shader_path.read_text(encoding="utf-8"))
    del shader_spec["language"]
    _write_json(shader_path, shader_spec)
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

    assert any(
        diagnostic.path == "shaders/shader-uuid.shader.json"
        and diagnostic.message
        == "Runtime shader spec must declare supported language: glsl, hlsl, or slang"
        for diagnostic in diagnostics
    )


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


@pytest.mark.parametrize(
    ("properties", "message"),
    [
        (
            [
                {
                    "name": "u_albedo",
                    "property_type": "Texture",
                    "expected_encoding": "display-p3",
                }
            ],
            "Shader program texture property expected_encoding must be 'srgb' or 'linear'",
        ),
        (
            [
                {
                    "name": "u_factor",
                    "property_type": "Float",
                    "expected_encoding": "linear",
                }
            ],
            "Shader program non-texture property must not have expected_encoding",
        ),
        (
            [
                {
                    "name": "u_albedo",
                    "property_type": "Texture",
                    "expected_encoding": "srgb",
                    "default": "checker",
                }
            ],
            "Shader program texture property default must be 'white' or 'normal'",
        ),
        (
            [
                {
                    "name": "u_normal",
                    "property_type": "Texture",
                    "expected_encoding": "srgb",
                    "default": "normal",
                }
            ],
            "Shader program texture property normal default requires linear expected_encoding",
        ),
    ],
)
def test_validate_runtime_package_checks_shader_property_encoding_contract(
    tmp_path: Path,
    properties: list[dict[str, object]],
    message: str,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_shader_resource(package_dir)
    _write_shader_program_resource(package_dir)
    program_path = package_dir / "shaders" / "program-uuid.shader-program.json"
    program = json.loads(program_path.read_text(encoding="utf-8"))
    program["properties"] = properties
    _write_json(program_path, program)
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

    assert any(diagnostic.message == message for diagnostic in diagnostics)


def test_validate_runtime_package_accepts_unconstrained_texture_property(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_shader_resource(package_dir)
    _write_shader_program_resource(package_dir)
    program_path = package_dir / "shaders" / "program-uuid.shader-program.json"
    program = json.loads(program_path.read_text(encoding="utf-8"))
    program["properties"] = [
        {"name": "u_input", "property_type": "Texture", "default": "white"}
    ]
    _write_json(program_path, program)
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

    assert not [diagnostic for diagnostic in diagnostics if diagnostic.level == "error"]


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
            "language": "slang",
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


def test_validate_runtime_package_warns_about_material_texture_encoding_mismatch(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_shader_resource(package_dir)
    _write_shader_program_resource(package_dir)
    program_path = package_dir / "shaders" / "program-uuid.shader-program.json"
    program = json.loads(program_path.read_text(encoding="utf-8"))
    program["properties"] = [
        {
            "name": "u_albedo",
            "property_type": "Texture",
            "expected_encoding": "srgb",
            "default": "white",
        }
    ]
    _write_json(program_path, program)
    _write_json(
        package_dir / "materials" / "material-uuid.tmat.json",
        {
            "uuid": "material-uuid",
            "shader_program": "program-uuid",
            "phases": [{"mark": "opaque", "shader": "shader-uuid", "priority": 0}],
            "textures": {
                "u_albedo": {"kind": "asset", "uuid": "texture-uuid", "name": "Albedo"},
            },
        },
    )
    _write_json(
        package_dir / "textures" / "texture-uuid.texture.json",
        {
            "uuid": "texture-uuid",
            "name": "Albedo",
            "source_path": "textures/texture-uuid.png",
            "import_settings": {
                "encoding": "linear",
                "flip_x": False,
                "flip_y": True,
                "transpose": False,
            },
        },
    )
    (package_dir / "textures" / "texture-uuid.png").write_bytes(b"PNG")
    _write_json(
        package_dir / "manifest.json",
        {
            **_scene_manifest(),
            "resources": [
                {"type": "shader", "uuid": "shader-uuid", "path": "shaders/shader-uuid.shader.json"},
                {
                    "type": "shader_program",
                    "uuid": "program-uuid",
                    "path": "shaders/program-uuid.shader-program.json",
                },
                {"type": "material", "uuid": "material-uuid", "path": "materials/material-uuid.tmat.json"},
                {"type": "texture", "uuid": "texture-uuid", "path": "textures/texture-uuid.texture.json"},
            ],
        },
    )

    diagnostics = validate_runtime_package(package_dir)

    assert any(
        diagnostic.level == "warning"
        and diagnostic.path == "materials/material-uuid.tmat.json:textures.u_albedo"
        and diagnostic.message
        == (
            "Runtime material texture slot expects srgb, but texture "
            "'texture-uuid' is linear; the binding remains renderable"
        )
        for diagnostic in diagnostics
    )


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
                "backends": ["vulkan", "opengl"],
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
            "Runtime shader 'shader-uuid' artifact backends ['vulkan'] do not match "
            "runtime backend order ['vulkan', 'opengl']",
        )
    ]


def test_validate_runtime_package_checks_pipeline_pass_variant_contract(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    _write_shader_resource(package_dir, "shv_surface_forward")
    shader_path = package_dir / "shaders" / "shv_surface_forward.shader.json"
    shader_spec = json.loads(shader_path.read_text(encoding="utf-8"))
    shader_spec["artifact_role"] = "pipeline_variant"
    shader_spec["source_identity"] = "sha256:composed-v1"
    _write_json(shader_path, shader_spec)
    manifest_path = package_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["target_requirements"] = {"backends": ["vulkan", "opengl"]}
    manifest["pipeline_shader_requirements"] = [
        {
            "scene": SCENE_PATH,
            "pipeline": "DeferredPrototype",
            "variants": [
                {
                    "uuid": "shv_surface_forward",
                    "name": "Surface_GBuffer",
                    "path": "shaders/shv_surface_forward.shader.json",
                    "source_identity": "sha256:composed-v1",
                }
            ],
        }
    ]
    _write_json(manifest_path, manifest)

    assert validate_runtime_package(package_dir) == []

    shader_spec["source_identity"] = "sha256:composed-v2"
    _write_json(shader_path, shader_spec)
    diagnostics = validate_runtime_package(package_dir)
    assert any(
        diagnostic.path == "pipeline_shader_requirements[0].variants[0]"
        and "stale composed-source identity" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_validate_runtime_package_reports_missing_pipeline_pass_variant(
    tmp_path: Path,
) -> None:
    package_dir = _write_valid_package(tmp_path)
    manifest_path = package_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["pipeline_shader_requirements"] = [
        {
            "scene": SCENE_PATH,
            "pipeline": "Default",
            "variants": [
                {
                    "uuid": "shv_missing_forward",
                    "name": "Surface_Forward",
                    "path": "shaders/shv_missing_forward.shader.json",
                    "source_identity": "sha256:missing",
                }
            ],
        }
    ]
    _write_json(manifest_path, manifest)

    diagnostics = validate_runtime_package(package_dir)

    assert any(
        diagnostic.path == "pipeline_shader_requirements[0].variants[0]"
        and "Pipeline 'Default' requires missing executable pass variant"
        in diagnostic.message
        for diagnostic in diagnostics
    )


def test_validate_runtime_package_requires_webgpu_layout_sidecars(tmp_path: Path) -> None:
    package_dir = _write_valid_package(tmp_path)
    shader_uuid = "webgpu-shader"
    shader_dir = package_dir / "shaders"
    (shader_dir / "vulkan").mkdir(parents=True, exist_ok=True)
    (shader_dir / "webgpu").mkdir(parents=True, exist_ok=True)
    for stage in ("vert", "frag"):
        (shader_dir / "vulkan" / f"{shader_uuid}.{stage}.slang").write_text(
            "void main() {}\n",
            encoding="utf-8",
        )
        (shader_dir / "webgpu" / f"{shader_uuid}.{stage}.wgsl").write_text(
            "@fragment fn main() {}\n",
            encoding="utf-8",
        )
    _write_json(
        shader_dir / f"{shader_uuid}.shader.json",
        {
            "uuid": shader_uuid,
            "language": "slang",
            "vertex_source_path": f"shaders/vulkan/{shader_uuid}.vert.slang",
            "fragment_source_path": f"shaders/vulkan/{shader_uuid}.frag.slang",
            "artifacts": {
                "webgpu": {
                    "vertex": f"shaders/webgpu/{shader_uuid}.vert.wgsl",
                    "fragment": f"shaders/webgpu/{shader_uuid}.frag.wgsl",
                }
            },
        },
    )
    _write_json(
        Path(str(shader_dir / "webgpu" / f"{shader_uuid}.vert.wgsl") + ".layout.json"),
        {"version": 3, "target": "webgpu", "stage": "vertex", "resources": []},
    )
    manifest_path = package_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["resources"].append(
        {
            "type": "shader",
            "uuid": shader_uuid,
            "path": f"shaders/{shader_uuid}.shader.json",
        }
    )
    _write_json(manifest_path, manifest)

    diagnostics = validate_runtime_package(package_dir)

    assert any(
        diagnostic.path
        == f"shaders/webgpu/{shader_uuid}.frag.wgsl.layout.json"
        and "cannot be read" in diagnostic.message
        for diagnostic in diagnostics
    )
