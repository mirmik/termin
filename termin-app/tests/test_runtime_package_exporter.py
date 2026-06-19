import json
import os
from pathlib import Path

import numpy as np
import pytest

from termin.project_build import android_build, build_desktop_project, export_runtime_package, quest_openxr_build
from termin.project_build.runtime_package_exporter import (
    ENGINE_TEXT3D_SHADER_UUID,
    RuntimePackageExportDiagnostic,
    _default_pipeline_engine_shaders,
    _material_textures_to_json,
)
from termin.player.runtime_package_loader import _material_texture_resources_from_shader_spec


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_fake_shader_compiler(tmp_path: Path) -> Path:
    compiler = tmp_path / "fake_termin_shaderc.py"
    compiler.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
        "out.parent.mkdir(parents=True, exist_ok=True)\n"
        "out.write_bytes(b'SPIRV')\n",
        encoding="utf-8",
    )
    compiler.chmod(0o755)
    return compiler


def _write_fake_desktop_sdk(tmp_path: Path) -> Path:
    sdk = tmp_path / "fake-sdk"
    bin_dir = sdk / "bin"
    lib_dir = sdk / "lib"
    python_home = lib_dir / "python3.10"
    site_packages = python_home / "site-packages"
    python_overlay = lib_dir / "python"
    share_dir = sdk / "share" / "termin" / "builtin_shaders"

    bin_dir.mkdir(parents=True)
    lib_dir.mkdir(parents=True)
    site_packages.mkdir(parents=True)
    share_dir.mkdir(parents=True)

    player = bin_dir / "termin_player"
    player.write_text("#!/bin/sh\n", encoding="utf-8")
    player.chmod(0o755)
    (lib_dir / "libpython3.10.so").write_bytes(b"python")
    (lib_dir / "libtermin_base.so").write_bytes(b"termin")
    (python_home / "os.py").write_text("", encoding="utf-8")
    (site_packages / "termin").mkdir()
    (site_packages / "termin" / "__init__.py").write_text("", encoding="utf-8")
    (python_overlay / "termin" / "player").mkdir(parents=True)
    (python_overlay / "termin" / "player" / "__main__.py").write_text(
        "# fresh player overlay\n",
        encoding="utf-8",
    )
    (share_dir / "termin_prelude.slang").write_text("// prelude\n", encoding="utf-8")
    return sdk


def _write_target_marking_shader_compiler(tmp_path: Path) -> Path:
    compiler = tmp_path / "fake_target_termin_shaderc.py"
    calls_path = tmp_path / "target_shaderc_calls.jsonl"
    compiler.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        f"calls = pathlib.Path({str(calls_path)!r})\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
        "target = sys.argv[sys.argv.index('--target') + 1]\n"
        "out.parent.mkdir(parents=True, exist_ok=True)\n"
        "out.write_bytes(('ARTIFACT-' + target).encode('ascii'))\n"
        "with calls.open('a', encoding='utf-8') as f:\n"
        "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n",
        encoding="utf-8",
    )
    compiler.chmod(0o755)
    return compiler


def test_runtime_shader_layout_collects_material_texture_resources(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    layout_path = package_dir / "shaders" / "vulkan" / "pbr.frag.spv.layout.json"
    _write_json(
        layout_path,
        {
            "resources": [
                {"name": "material", "kind": "constant_buffer", "scope": "material"},
                {"name": "u_albedo_texture", "kind": "texture", "scope": "material"},
                {"name": "u_normal_texture", "kind": "texture", "scope": "material"},
                {"name": "shadow_maps", "kind": "texture", "scope": "pass"},
            ]
        },
    )

    assert _material_texture_resources_from_shader_spec(
        package_dir,
        {"artifacts": {"vulkan": {"fragment": "shaders/vulkan/pbr.frag.spv"}}},
    ) == ("u_albedo_texture", "u_normal_texture")


def test_runtime_material_texture_export_records_builtin_placeholders() -> None:
    class FakeTexture:
        def __init__(self, name: str, uuid: str) -> None:
            self.name = name
            self.uuid = uuid
            self.is_valid = True

    class FakeMaterial:
        textures = {
            "u_albedo_texture": FakeTexture("__white_1x1__", "white-uuid"),
            "u_normal_texture": FakeTexture("__normal_1x1__", "normal-uuid"),
        }

    assert _material_textures_to_json(FakeMaterial()) == {
        "u_albedo_texture": {"kind": "builtin", "name": "white"},
        "u_normal_texture": {"kind": "builtin", "name": "normal"},
    }


def test_default_pipeline_exports_world_text_shader() -> None:
    shader_uuids = {shader.uuid for shader in _default_pipeline_engine_shaders()}

    assert ENGINE_TEXT3D_SHADER_UUID in shader_uuids


def test_export_runtime_package_writes_runtime_contract(tmp_path: Path) -> None:
    project = tmp_path / "RuntimeGame"
    project.mkdir()
    scene_path = project / "Scenes" / "Main.scene"
    _write_json(
        scene_path,
        {
            "version": "1.0",
            "scene": {
                "uuid": "scene-uuid",
                "entities": [
                    {
                        "uuid": "triangle-entity",
                        "name": "Triangle",
                        "components": [
                            {
                                "type": "MeshComponent",
                                "data": {
                                    "mesh": {
                                        "uuid": "mesh-uuid",
                                        "name": "Triangle",
                                        "type": "uuid",
                                    },
                                },
                            },
                            {
                                "type": "MeshRenderer",
                                "data": {
                                    "mesh": {
                                        "uuid": "mesh-uuid",
                                        "name": "Triangle",
                                        "type": "uuid",
                                    },
                                    "material": {
                                        "uuid": "material-uuid",
                                        "name": "Triangle Material",
                                        "type": "uuid",
                                    },
                                },
                            },
                        ],
                    },
                ],
            },
            "editor": {"ignored": True},
        },
    )

    result = export_runtime_package(
        project_root=project,
        entry_scene=Path("Scenes") / "Main.scene",
        output_dir=project / "dist" / "android" / "RuntimeGame" / "package",
        shader_compiler=_write_fake_shader_compiler(tmp_path),
        resource_policy="dev_smoke",
    )

    assert result.manifest_path.exists()
    assert result.scene_path.exists()
    assert (result.package_dir / "meshes" / "mesh-uuid.tmesh.json").exists()
    assert (result.package_dir / "materials" / "material-uuid.tmat.json").exists()
    assert (result.package_dir / "shaders" / "termin-runtime-default-color.shader.json").exists()
    assert (result.package_dir / "shaders" / "vulkan" / "termin-runtime-default-color.vert.spv").exists()
    assert (result.package_dir / "shaders" / "vulkan" / "termin-runtime-default-color.frag.spv").exists()
    default_vertex_source = (
        result.package_dir / "shaders" / "vulkan" / "termin-runtime-default-color.slang"
    ).read_text(encoding="utf-8")
    default_fragment_source = (
        result.package_dir / "shaders" / "vulkan" / "termin-runtime-default-color.slang"
    ).read_text(encoding="utf-8")
    assert "vk::" not in default_vertex_source
    assert "per_frame" in default_vertex_source
    assert "draw_data" in default_vertex_source
    assert "SV_Target0" in default_fragment_source

    scene_data = json.loads(result.scene_path.read_text(encoding="utf-8"))
    assert scene_data["uuid"] == "scene-uuid"
    assert "scene" not in scene_data
    assert "editor" not in scene_data

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["scene"] == "scene.json"
    assert manifest["shader_artifact_root"] == "."
    assert manifest["resources"] == [
        {
            "type": "shader",
            "uuid": "termin-runtime-default-color",
            "path": "shaders/termin-runtime-default-color.shader.json",
        },
        {
            "type": "mesh",
            "uuid": "mesh-uuid",
            "path": "meshes/mesh-uuid.tmesh.json",
        },
        {
            "type": "material",
            "uuid": "material-uuid",
            "path": "materials/material-uuid.tmat.json",
        },
    ]
    assert all(diagnostic["level"] == "warning" for diagnostic in manifest["diagnostics"])
    diagnostic_messages = [diagnostic["message"] for diagnostic in manifest["diagnostics"]]
    assert (
        "Runtime exporter used fallback mesh because registry entry is unavailable"
        in diagnostic_messages
    )
    assert (
        "Runtime exporter used fallback material because registry entry is unavailable"
        in diagnostic_messages
    )


def test_export_runtime_package_includes_project_material_assets(tmp_path: Path) -> None:
    project = tmp_path / "DynamicMaterialGame"
    project.mkdir()
    material_uuid = "dynamic-highlight-material"
    _write_json(project / "Main.scene", {"uuid": "scene-uuid", "entities": []})
    _write_json(
        project / "Materials" / "Highlight.material",
        {
            "uuid": material_uuid,
            "shader": "CookTorrancePBR",
            "uniforms": {
                "u_color": [1.0, 0.9, 0.1, 1.0],
            },
        },
    )

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "desktop" / "DynamicMaterialGame" / "package",
        shader_compiler=_write_fake_shader_compiler(tmp_path),
        resource_policy="dev_smoke",
    )

    assert (result.package_dir / "materials" / f"{material_uuid}.tmat.json").exists()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert {
        "type": "material",
        "uuid": material_uuid,
        "path": f"materials/{material_uuid}.tmat.json",
    } in manifest["resources"]


def test_export_runtime_package_reports_missing_resources_as_errors_by_default(tmp_path: Path) -> None:
    project = tmp_path / "StrictResourceGame"
    project.mkdir()
    _write_json(
        project / "Main.scene",
        {
            "uuid": "scene-uuid",
            "entities": [
                {
                    "uuid": "entity-uuid",
                    "components": [
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "mesh": {
                                    "uuid": "missing-mesh",
                                    "name": "MissingMesh",
                                    "type": "uuid",
                                },
                                "material": {
                                    "uuid": "missing-material",
                                    "name": "MissingMaterial",
                                    "type": "uuid",
                                },
                            },
                        }
                    ],
                }
            ],
        },
    )

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "strict" / "package",
        shader_compiler=_write_fake_shader_compiler(tmp_path),
    )

    assert not (result.package_dir / "meshes" / "missing-mesh.tmesh.json").exists()
    assert not (result.package_dir / "materials" / "missing-material.tmat.json").exists()
    assert {
        "type": "mesh",
        "uuid": "missing-mesh",
        "path": "meshes/missing-mesh.tmesh.json",
    } not in json.loads(result.manifest_path.read_text(encoding="utf-8"))["resources"]
    assert [
        (diagnostic.level, diagnostic.path)
        for diagnostic in result.diagnostics
        if diagnostic.level == "error"
    ] == [
        ("error", "meshes/missing-mesh.tmesh.json"),
        ("error", "materials/missing-material.tmat.json"),
    ]


def test_export_runtime_package_reads_standalone_mesh_asset_by_meta_uuid(tmp_path: Path) -> None:
    project = tmp_path / "MeshAssetGame"
    project.mkdir()
    mesh_uuid = "standalone-mesh-uuid"
    material_uuid = "material-uuid"

    models_dir = project / "Models"
    models_dir.mkdir()
    mesh_path = models_dir / "Triangle.obj"
    mesh_path.write_text(
        "\n".join(
            [
                "v 0 0 0",
                "v 1 0 0",
                "v 0 1 0",
                "f 1 2 3",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_json(
        Path(str(mesh_path) + ".meta"),
        {
            "uuid": mesh_uuid,
            "scale": 1.0,
            "axis_x": "x",
            "axis_y": "y",
            "axis_z": "z",
            "flip_uv_v": False,
        },
    )
    _write_json(
        project / "Main.scene",
        {
            "uuid": "scene-uuid",
            "entities": [
                {
                    "uuid": "entity-uuid",
                    "components": [
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "mesh": {
                                    "uuid": mesh_uuid,
                                    "name": "Triangle",
                                    "type": "uuid",
                                },
                                "material": {
                                    "uuid": material_uuid,
                                    "name": "Triangle Material",
                                    "type": "uuid",
                                },
                            },
                        }
                    ],
                }
            ],
        },
    )

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "desktop" / "MeshAssetGame" / "package",
        shader_compiler=_write_fake_shader_compiler(tmp_path),
    )

    mesh_data = json.loads((result.package_dir / "meshes" / f"{mesh_uuid}.tmesh.json").read_text(encoding="utf-8"))
    assert mesh_data["uuid"] == mesh_uuid
    assert mesh_data["name"] == "Triangle"
    assert mesh_data["vertex_count"] == 3
    assert mesh_data["indices"] == [0, 1, 2]
    attribute_names = [attribute["name"] for attribute in mesh_data["layout"]]
    assert "position" in attribute_names
    assert "normal" in attribute_names
    assert "uv" in attribute_names
    assert "color" not in attribute_names
    diagnostic_messages = [diagnostic.message for diagnostic in result.diagnostics]
    assert "Runtime exporter used fallback mesh because registry entry is unavailable" not in diagnostic_messages


def test_build_desktop_project_writes_bundle_contract(tmp_path: Path) -> None:
    project = tmp_path / "DesktopGame"
    project.mkdir()
    _write_json(project / "DesktopGame.terminproj", {"version": 1, "name": "DesktopGame"})
    _write_json(project / "Main.scene", {"uuid": "desktop-scene", "entities": []})
    _write_json(
        project / "game.pymodule",
        {
            "name": "game",
            "root": ".",
            "packages": [
                "Scripts",
            ],
            "requirements": [
                "python-chess",
            ],
        },
    )
    scripts_dir = project / "Scripts"
    scripts_dir.mkdir()
    (scripts_dir / "__init__.py").write_text("", encoding="utf-8")
    (scripts_dir / "Controller.py").write_text("class Controller:\n    pass\n", encoding="utf-8")
    pycache_dir = scripts_dir / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "Controller.pyc").write_bytes(b"cached")

    legacy_output = project / "dist" / "DesktopGame"
    _write_json(legacy_output / "build.json", {"legacy": True})
    _write_json(legacy_output / "assets" / "manifest.json", {"legacy": True})

    result = build_desktop_project(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=legacy_output,
        shader_compiler=_write_fake_shader_compiler(tmp_path),
        sdk_root=_write_fake_desktop_sdk(tmp_path),
    )

    assert result.dist_dir == legacy_output.resolve()
    assert result.app_manifest_path == result.dist_dir / "app.json"
    assert result.package_result.manifest_path == result.dist_dir / "package" / "manifest.json"
    assert result.package_result.scene_path == result.dist_dir / "package" / "scene.json"
    assert result.python_result.manifest_path == result.dist_dir / "package" / "python" / "modules.json"
    assert result.runtime_result.python_home == result.dist_dir / "lib" / "python3.10"
    assert result.app_manifest_path.exists()
    assert result.package_result.manifest_path.exists()
    assert result.python_result.manifest_path.exists()
    assert not (result.dist_dir / "build.json").exists()
    assert not (result.dist_dir / "assets").exists()
    assert (result.dist_dir / "package" / "python" / "game.pymodule").exists()
    assert (result.dist_dir / "package" / "python" / "Scripts" / "__init__.py").exists()
    assert (result.dist_dir / "package" / "python" / "Scripts" / "Controller.py").exists()
    assert not (result.dist_dir / "package" / "python" / "Scripts" / "__pycache__").exists()
    assert (result.dist_dir / "bin" / "termin_player").exists()
    assert (result.dist_dir / "lib" / "libpython3.10.so").exists()
    assert (result.dist_dir / "lib" / "libtermin_base.so").exists()
    assert (result.dist_dir / "lib" / "python3.10" / "os.py").exists()
    assert (result.dist_dir / "lib" / "python3.10" / "site-packages" / "termin" / "__init__.py").exists()
    assert (
        result.dist_dir
        / "lib"
        / "python3.10"
        / "site-packages"
        / "termin"
        / "player"
        / "__main__.py"
    ).exists()
    assert (result.dist_dir / "share" / "termin" / "builtin_shaders" / "termin_prelude.slang").exists()

    app_manifest_text = result.app_manifest_path.read_text(encoding="utf-8")
    assert str(project.resolve()) not in app_manifest_text
    app_manifest = json.loads(app_manifest_text)
    assert app_manifest == {
        "version": 1,
        "format": "termin.desktop_bundle",
        "target": "desktop",
        "project_name": "DesktopGame",
        "package": {
            "root": "package",
            "manifest": "package/manifest.json",
            "scene": "package/scene.json",
        },
        "runtime": {
            "launcher": "bin/termin_player",
            "python": {
                "enabled": True,
                "home": "lib/python3.10",
                "project_modules": "package/python",
                "module_manifest": "package/python/modules.json",
                "descriptors": [
                    "package/python/game.pymodule",
                ],
            },
            "native_library_dirs": [
                "lib",
            ],
            "mcp": {
                "enabled": False,
                "host": "127.0.0.1",
                "port": 8766,
                "session_file": "/tmp/termin-player-mcp.json",
            },
        },
        "entry": {
            "scene": "package/scene.json",
        },
    }

    package_manifest = json.loads(result.package_result.manifest_path.read_text(encoding="utf-8"))
    assert package_manifest["scene"] == "scene.json"
    assert package_manifest["shader_artifact_root"] == "."
    python_manifest = json.loads(result.python_result.manifest_path.read_text(encoding="utf-8"))
    assert python_manifest == {
        "version": 1,
        "modules": [
            {
                "name": "game",
                "descriptor": "game.pymodule",
                "root": ".",
                "packages": [
                    "Scripts",
                ],
                "requirements": [
                    "python-chess",
                ],
                "files": [
                    "Scripts/Controller.py",
                    "Scripts/__init__.py",
                    "game.pymodule",
                ],
            },
        ],
        "diagnostics": [],
    }


def test_export_runtime_package_writes_builtin_shader_catalog_artifacts(tmp_path: Path) -> None:
    project = tmp_path / "BuiltinShaderCatalogGame"
    project.mkdir()
    _write_json(project / "Main.scene", {"uuid": "root-scene", "entities": []})

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "package",
        shader_compiler=_write_fake_shader_compiler(tmp_path),
    )

    fsq_source = (
        result.package_dir / "shaders" / "vulkan" / "termin-engine-fsq.vert.slang"
    ).read_text(encoding="utf-8")
    assert "vk::" not in fsq_source
    assert "POSITION" in fsq_source
    assert "TEXCOORD0" in fsq_source

    skybox_source = (
        result.package_dir / "shaders" / "vulkan" / "termin-engine-skybox.vert.slang"
    ).read_text(encoding="utf-8")
    assert "MaterialParams" in skybox_source
    assert "u_view" in skybox_source
    assert "u_projection" in skybox_source

    shadow_source = (
        result.package_dir / "shaders" / "vulkan" / "termin-engine-shadow.slang"
    ).read_text(encoding="utf-8")
    assert "vk::" not in shadow_source
    assert "PerFrame" in shadow_source
    assert "ShadowPushData" in shadow_source
    assert "shadow_draw" in shadow_source

    default_source = (
        result.package_dir / "shaders" / "vulkan" / "termin-runtime-default-color.slang"
    ).read_text(encoding="utf-8")
    assert "vk::" not in default_source
    assert "per_frame" in default_source
    assert "draw_data" in default_source

    tonemap_source = (
        result.package_dir / "shaders" / "vulkan" / "termin-engine-tonemap.frag.slang"
    ).read_text(encoding="utf-8")
    assert "TonemapParams" in tonemap_source
    assert "u_input" in tonemap_source

    grayscale_source = (
        result.package_dir / "shaders" / "vulkan" / "termin-engine-grayscale.frag.slang"
    ).read_text(encoding="utf-8")
    assert "GrayscaleParams" in grayscale_source
    assert "u_input" in grayscale_source

    tonemap_layout = json.loads(
        (
            result.package_dir
            / "shaders"
            / "layout"
            / "termin-engine-tonemap.shader-layout.json"
        ).read_text(encoding="utf-8")
    )
    assert tonemap_layout["binding_model"] == "resource_layout"
    assert {
        "name": "u_input",
        "logical_name": "input_texture",
        "kind": "combined_sampler2d",
    } in tonemap_layout["resources"]

    grayscale_layout = json.loads(
        (
            result.package_dir
            / "shaders"
            / "layout"
            / "termin-engine-grayscale.shader-layout.json"
        ).read_text(encoding="utf-8")
    )
    assert grayscale_layout["binding_model"] == "resource_layout"
    assert {
        "name": "u_input",
        "logical_name": "input_texture",
        "kind": "combined_sampler2d",
    } in grayscale_layout["resources"]

    shadow_layout = json.loads(
        (
            result.package_dir
            / "shaders"
            / "layout"
            / "termin-engine-shadow.shader-layout.json"
        ).read_text(encoding="utf-8")
    )
    assert shadow_layout["binding_model"] == "resource_layout"
    assert {
        "name": "per_frame",
        "logical_name": "per_frame",
        "kind": "constant_buffer",
        "scope": "frame",
    } in shadow_layout["resources"]
    assert {
        "name": "shadow_draw",
        "logical_name": "draw",
        "kind": "constant_buffer",
        "scope": "draw",
    } in shadow_layout["resources"]

    skybox_layout = json.loads(
        (
            result.package_dir
            / "shaders"
            / "layout"
            / "termin-engine-skybox.shader-layout.json"
        ).read_text(encoding="utf-8")
    )
    assert skybox_layout["language"] == "slang"
    assert skybox_layout["source_language"] == "shader"
    assert skybox_layout["program"] == {"path": "termin-engine-skybox.shader"}
    assert {
        "name": "MaterialParams",
        "logical_name": "material_params",
        "kind": "constant_buffer",
        "binding": 1,
    } in skybox_layout["resources"]


def test_export_runtime_package_accepts_root_scene_json(tmp_path: Path) -> None:
    project = tmp_path / "RootSceneGame"
    project.mkdir()
    scene_path = project / "Main.scene"
    _write_json(scene_path, {"uuid": "root-scene", "entities": []})

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "android" / "RootSceneGame" / "package",
        shader_compiler=_write_fake_shader_compiler(tmp_path),
    )

    scene_data = json.loads(result.scene_path.read_text(encoding="utf-8"))
    assert scene_data == {"uuid": "root-scene", "entities": []}


def test_export_runtime_package_can_use_slang_default_shader(tmp_path: Path) -> None:
    project = tmp_path / "SlangDefaultGame"
    project.mkdir()
    _write_json(project / "Main.scene", {"uuid": "root-scene", "entities": []})

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "package",
        shader_compiler=_write_target_marking_shader_compiler(tmp_path),
        default_shader_language="slang",
    )

    shader_data = json.loads(
        (result.package_dir / "shaders" / "termin-runtime-default-color.shader.json").read_text(
            encoding="utf-8"
        )
    )
    assert shader_data["language"] == "slang"
    assert shader_data["vertex_source_path"] == (
        "shaders/vulkan/termin-runtime-default-color.slang"
    )
    assert shader_data["fragment_source_path"] == (
        "shaders/vulkan/termin-runtime-default-color.slang"
    )
    assert shader_data["artifacts"] == {
        "vulkan": {
            "vertex": "shaders/vulkan/termin-runtime-default-color.vert.spv",
            "fragment": "shaders/vulkan/termin-runtime-default-color.frag.spv",
        },
        "opengl": {
            "vertex": "shaders/opengl/termin-runtime-default-color.vert.glsl",
            "fragment": "shaders/opengl/termin-runtime-default-color.frag.glsl",
        },
    }
    assert (
        result.package_dir / "shaders" / "vulkan" / "termin-runtime-default-color.vert.spv"
    ).read_bytes() == b"ARTIFACT-vulkan"
    assert (
        result.package_dir / "shaders" / "opengl" / "termin-runtime-default-color.frag.glsl"
    ).read_bytes() == b"ARTIFACT-opengl"
    slang_vertex_source = (
        result.package_dir / "shaders" / "vulkan" / "termin-runtime-default-color.slang"
    ).read_text(encoding="utf-8")
    slang_fragment_source = (
        result.package_dir / "shaders" / "vulkan" / "termin-runtime-default-color.slang"
    ).read_text(encoding="utf-8")
    assert "vk::location" not in slang_vertex_source
    assert "vk::location" not in slang_fragment_source
    assert "POSITION" in slang_vertex_source
    assert "COLOR0" in slang_vertex_source
    assert "SV_Target0" in slang_fragment_source
    assert result.diagnostics == []


def test_export_runtime_package_rejects_glsl_default_shader(tmp_path: Path) -> None:
    project = tmp_path / "GlslDefaultGame"
    project.mkdir()
    _write_json(project / "Main.scene", {"uuid": "root-scene", "entities": []})

    with pytest.raises(ValueError, match="runtime default shader is Slang-only"):
        export_runtime_package(
            project_root=project,
            entry_scene="Main.scene",
            output_dir=project / "dist" / "package",
            shader_compiler=_write_target_marking_shader_compiler(tmp_path),
            default_shader_language="glsl",
        )


def test_export_runtime_package_rejects_unknown_default_shader_language(tmp_path: Path) -> None:
    project = tmp_path / "BadDefaultLanguageGame"
    project.mkdir()
    _write_json(project / "Main.scene", {"uuid": "root-scene", "entities": []})

    with pytest.raises(ValueError, match="Unsupported default shader language"):
        export_runtime_package(
            project_root=project,
            entry_scene="Main.scene",
            output_dir=project / "dist" / "package",
            shader_compiler=_write_target_marking_shader_compiler(tmp_path),
            default_shader_language="hlsl",
        )


def test_export_runtime_package_writes_render_target_pipeline_asset(tmp_path: Path) -> None:
    project = tmp_path / "PipelineGame"
    project.mkdir()
    pipeline_uuid = "pipeline-uuid"

    _write_json(
        project / "Main.scene",
        {
            "scene": {
                "uuid": "scene-uuid",
                "entities": [],
                "render_mount": {
                    "render_target_configs": [
                        {
                            "name": "XRStereoTarget",
                            "kind": "xr_stereo",
                            "pipeline_uuid": pipeline_uuid,
                            "pipeline_name": "VrPipeline",
                            "enabled": True,
                        }
                    ],
                },
            },
        },
    )
    _write_json(
        project / "VrPipeline.pipeline",
        {
            "name": "graph_pipeline",
            "nodes": [
                {"type": "PipelineOutput", "node_type": "pipeline_output"},
            ],
            "connections": [],
        },
    )
    _write_json(project / "VrPipeline.pipeline.meta", {"uuid": pipeline_uuid})

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "quest_openxr" / "PipelineGame" / "package",
        shader_compiler=_write_fake_shader_compiler(tmp_path),
    )

    pipeline_path = result.package_dir / "pipelines" / f"{pipeline_uuid}.pipeline.json"
    assert pipeline_path.exists()
    pipeline_data = json.loads(pipeline_path.read_text(encoding="utf-8"))
    assert pipeline_data["uuid"] == pipeline_uuid
    assert pipeline_data["name"] == "graph_pipeline"

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert {
        "type": "pipeline",
        "uuid": pipeline_uuid,
        "name": "VrPipeline",
        "path": f"pipelines/{pipeline_uuid}.pipeline.json",
    } in manifest["resources"]


def test_export_runtime_package_uses_live_mesh_material_shader(tmp_path: Path) -> None:
    import tgfx
    from termin.materials import TcMaterial
    from termin.geombase import Vec4
    from tmesh import TcAttribType, TcDrawMode, TcMesh, TcVertexLayout

    project = tmp_path / "LiveResourceGame"
    project.mkdir()
    mesh_uuid = "live-mesh-uuid"
    material_uuid = "live-material-uuid"
    shader_uuid = "live-shader-uuid"

    layout = TcVertexLayout()
    layout.add("position", 3, TcAttribType.FLOAT32, 0)
    layout.add("color", 3, TcAttribType.FLOAT32, 1)
    vertices = np.array(
        [
            0.0, 0.5, 0.0, 1.0, 0.0, 0.0,
            -0.5, -0.5, 0.0, 0.0, 1.0, 0.0,
            0.5, -0.5, 0.0, 0.0, 0.0, 1.0,
        ],
        dtype=np.float32,
    )
    indices = np.array([0, 1, 2], dtype=np.uint32)
    mesh = TcMesh.from_interleaved(
        vertices,
        3,
        indices,
        layout,
        "Live Triangle",
        mesh_uuid,
        TcDrawMode.TRIANGLES,
    )
    assert mesh.is_valid

    material = TcMaterial.create("Live Material", material_uuid)
    phase = material.add_phase_from_sources(
        "#version 450\nlayout(location=0) in vec3 in_position;\nvoid main(){gl_Position=vec4(in_position,1.0);}\n",
        "#version 450\nlayout(location=0) out vec4 out_color;\nvoid main(){out_color=vec4(1.0);}\n",
        "",
        "LiveShader",
        "opaque",
        7,
        shader_uuid=shader_uuid,
    )
    assert phase is not None
    shader = tgfx.TcShader.from_uuid(shader_uuid)
    assert shader.is_valid
    shader.set_feature(1)
    material.set_uniform_vec4("u_color", Vec4(0.25, 0.5, 0.75, 1.0))
    material.set_uniform_float("u_roughness", 0.625)

    _write_json(
        project / "Main.scene",
        {
            "uuid": "scene-uuid",
            "entities": [
                {
                    "uuid": "entity-uuid",
                    "components": [
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "mesh": {
                                    "uuid": mesh_uuid,
                                    "name": "Live Triangle",
                                    "type": "uuid",
                                },
                                "material": {
                                    "uuid": material_uuid,
                                    "name": "Live Material",
                                    "type": "uuid",
                                },
                            },
                        }
                    ],
                }
            ],
        },
    )
    compiler = _write_fake_shader_compiler(tmp_path)

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "android" / "LiveResourceGame" / "package",
        shader_compiler=compiler,
    )

    mesh_data = json.loads((result.package_dir / "meshes" / f"{mesh_uuid}.tmesh.json").read_text(encoding="utf-8"))
    material_data = json.loads((result.package_dir / "materials" / f"{material_uuid}.tmat.json").read_text(encoding="utf-8"))
    shader_data = json.loads((result.package_dir / "shaders" / f"{shader_uuid}.shader.json").read_text(encoding="utf-8"))

    assert mesh_data["vertices"] == vertices.astype(float).tolist()
    assert mesh_data["indices"] == [0, 1, 2]
    assert mesh_data["layout"] == [
        {"name": "position", "location": 0, "components": 3, "type": "float32"},
        {"name": "color", "location": 1, "components": 3, "type": "float32"},
    ]
    assert material_data["phases"] == [
        {"mark": "opaque", "shader": shader_uuid, "priority": 7},
    ]
    assert material_data["uniforms"] == {
        "u_color": [0.25, 0.5, 0.75, 1.0],
        "u_roughness": 0.625,
    }
    assert shader_data["uuid"] == shader_uuid
    assert shader_data["language"] == "glsl"
    assert shader_data["features"] == 1
    assert shader_data["artifacts"] == {
        "vulkan": {
            "vertex": f"shaders/vulkan/{shader_uuid}.vert.spv",
            "fragment": f"shaders/vulkan/{shader_uuid}.frag.spv",
        }
    }
    assert (result.package_dir / "shaders" / "vulkan" / f"{shader_uuid}.vert.spv").read_bytes() == b"SPIRV"
    assert (result.package_dir / "shaders" / "vulkan" / f"{shader_uuid}.frag.spv").read_bytes() == b"SPIRV"
    assert result.diagnostics == []


def test_export_runtime_package_records_slang_shader_artifacts(tmp_path: Path) -> None:
    import tgfx
    from termin.materials import TcMaterial

    project = tmp_path / "SlangRuntimeGame"
    project.mkdir()
    material_uuid = "live-slang-material-uuid"
    shader_uuid = "live-slang-shader-uuid"

    material = TcMaterial.create("Live Slang Material", material_uuid)
    phase = material.add_phase_from_sources(
        "[shader(\"vertex\")] void main() {}\n",
        "[shader(\"fragment\")] void main() {}\n",
        "",
        "LiveSlangShader",
        "opaque",
        3,
        shader_uuid=shader_uuid,
    )
    assert phase is not None

    shader = tgfx.TcShader.from_uuid(shader_uuid)
    assert shader.is_valid
    shader.set_language(tgfx.ShaderLanguage.SLANG)
    shader.set_artifact_policy(tgfx.ShaderArtifactPolicy.REQUIRED)

    _write_json(
        project / "Main.scene",
        {
            "uuid": "scene-uuid",
            "entities": [
                {
                    "uuid": "entity-uuid",
                    "components": [
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "material": {
                                    "uuid": material_uuid,
                                    "name": "Live Slang Material",
                                    "type": "uuid",
                                },
                            },
                        }
                    ],
                }
            ],
        },
    )

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "package",
        shader_compiler=_write_target_marking_shader_compiler(tmp_path),
    )

    shader_data = json.loads((result.package_dir / "shaders" / f"{shader_uuid}.shader.json").read_text(encoding="utf-8"))
    assert shader_data["uuid"] == shader_uuid
    assert shader_data["language"] == "slang"
    assert shader_data["vertex_source_path"] == f"shaders/vulkan/{shader_uuid}.vert.slang"
    assert shader_data["fragment_source_path"] == f"shaders/vulkan/{shader_uuid}.frag.slang"
    assert shader_data["artifacts"] == {
        "vulkan": {
            "vertex": f"shaders/vulkan/{shader_uuid}.vert.spv",
            "fragment": f"shaders/vulkan/{shader_uuid}.frag.spv",
        },
        "opengl": {
            "vertex": f"shaders/opengl/{shader_uuid}.vert.glsl",
            "fragment": f"shaders/opengl/{shader_uuid}.frag.glsl",
        },
    }
    assert (result.package_dir / "shaders" / "vulkan" / f"{shader_uuid}.vert.spv").read_bytes() == b"ARTIFACT-vulkan"
    assert (result.package_dir / "shaders" / "opengl" / f"{shader_uuid}.frag.glsl").read_bytes() == b"ARTIFACT-opengl"
    calls = [
        json.loads(line)
        for line in (tmp_path / "target_shaderc_calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert {call[call.index("--target") + 1] for call in calls} == {"vulkan", "opengl"}
    assert all("--layout-scheme" not in call for call in calls)
    assert result.diagnostics == []


def test_export_runtime_package_can_record_d3d11_shader_artifacts(tmp_path: Path) -> None:
    import tgfx
    from termin.materials import TcMaterial

    project = tmp_path / "D3D11RuntimeGame"
    project.mkdir()
    material_uuid = "live-d3d11-material-uuid"
    shader_uuid = "live-d3d11-shader-uuid"

    material = TcMaterial.create("Live D3D11 Material", material_uuid)
    phase = material.add_phase_from_sources(
        "[shader(\"vertex\")] void main() {}\n",
        "[shader(\"fragment\")] void main() {}\n",
        "",
        "LiveD3D11Shader",
        "opaque",
        3,
        shader_uuid=shader_uuid,
    )
    assert phase is not None

    shader = tgfx.TcShader.from_uuid(shader_uuid)
    assert shader.is_valid
    shader.set_language(tgfx.ShaderLanguage.SLANG)
    shader.set_artifact_policy(tgfx.ShaderArtifactPolicy.REQUIRED)

    _write_json(
        project / "Main.scene",
        {
            "uuid": "scene-uuid",
            "entities": [
                {
                    "uuid": "entity-uuid",
                    "components": [
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "material": {
                                    "uuid": material_uuid,
                                    "name": "Live D3D11 Material",
                                    "type": "uuid",
                                },
                            },
                        }
                    ],
                }
            ],
        },
    )

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "package",
        shader_compiler=_write_target_marking_shader_compiler(tmp_path),
        shader_targets=("vulkan", "opengl", "d3d11"),
    )

    shader_data = json.loads((result.package_dir / "shaders" / f"{shader_uuid}.shader.json").read_text(encoding="utf-8"))
    assert shader_data["artifacts"] == {
        "vulkan": {
            "vertex": f"shaders/vulkan/{shader_uuid}.vert.spv",
            "fragment": f"shaders/vulkan/{shader_uuid}.frag.spv",
        },
        "opengl": {
            "vertex": f"shaders/opengl/{shader_uuid}.vert.glsl",
            "fragment": f"shaders/opengl/{shader_uuid}.frag.glsl",
        },
        "d3d11": {
            "vertex": f"shaders/d3d11/{shader_uuid}.vs.cso",
            "fragment": f"shaders/d3d11/{shader_uuid}.ps.cso",
        },
    }
    assert (result.package_dir / "shaders" / "d3d11" / f"{shader_uuid}.vs.cso").read_bytes() == b"ARTIFACT-d3d11"
    assert (result.package_dir / "shaders" / "d3d11" / f"{shader_uuid}.ps.cso").read_bytes() == b"ARTIFACT-d3d11"

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["target_requirements"]["shader_targets"] == ["vulkan", "opengl", "d3d11"]

    calls = [
        json.loads(line)
        for line in (tmp_path / "target_shaderc_calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert "d3d11" in {call[call.index("--target") + 1] for call in calls}
    assert result.diagnostics == []


def test_build_android_project_exports_package_and_copies_apk(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "AndroidGame"
    project.mkdir()
    _write_json(project / "AndroidGame.terminproj", {"version": 1, "name": "AndroidGame"})
    _write_json(project / "Main.scene", {"uuid": "root-scene", "entities": []})

    termin_root = tmp_path / "termin-root"
    apk_source = termin_root / "build" / "android-gradle" / "app" / "outputs" / "apk" / "debug" / "app-debug.apk"
    (termin_root / "sdk" / "android" / "arm64-v8a" / "lib").mkdir(parents=True)
    build_script = termin_root / ("build-android-apk.cmd" if os.name == "nt" else "build-android-apk.sh")
    marker_script = termin_root / "build-android-apk.sh"
    build_script.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        marker_script.write_text("# marker for termin root discovery\n", encoding="utf-8")
        build_script.write_text(
            "@echo off\n"
            f"mkdir \"{apk_source.parent}\" >NUL 2>NUL\n"
            f"<NUL set /p dummy=APK>\"{apk_source}\"\n"
            "echo %*\n",
            encoding="utf-8",
        )
    else:
        build_script.write_text(
            "#!/bin/sh\n"
            "set -e\n"
            f"mkdir -p '{apk_source.parent}'\n"
            f"printf APK > '{apk_source}'\n"
            "printf '%s\\n' \"$@\"\n",
            encoding="utf-8",
        )
    build_script.chmod(0o755)
    fake_gradle = tmp_path / "fake-gradle"
    fake_gradle.write_text("# fake gradle\n", encoding="utf-8")
    fake_gradle.chmod(0o755)

    validation_diagnostic = RuntimePackageExportDiagnostic(
        "warning",
        "manifest.json",
        "synthetic validator diagnostic",
    )
    validated_package_dirs: list[Path] = []

    def fake_validate_runtime_package(package_dir: Path) -> list[RuntimePackageExportDiagnostic]:
        validated_package_dirs.append(package_dir)
        return [validation_diagnostic]

    monkeypatch.setattr(android_build, "validate_runtime_package", fake_validate_runtime_package)

    result = android_build.build_android_project(
        project_root=project,
        entry_scene="Main.scene",
        termin_root=termin_root,
        build_script=build_script,
        gradle=fake_gradle,
        shader_compiler=_write_fake_shader_compiler(tmp_path),
    )

    assert result.apk_path == project / "dist" / "android" / "AndroidGame" / "apk" / "AndroidGame-debug.apk"
    assert result.apk_path.read_bytes() == b"APK"
    assert result.application_id == "org.termin.builds.androidgame"
    assert result.launch_activity == "org.termin.android.TerminActivity"
    assert result.package_result.manifest_path.exists()
    log_text = result.log_path.read_text(encoding="utf-8")
    assert "--assets-dir" in log_text
    assert str(result.package_result.package_dir) in log_text
    assert "--sdk-root" in log_text
    assert str(termin_root / "sdk" / "android") in log_text
    assert "--application-id" in log_text
    assert "org.termin.builds.androidgame" in log_text
    assert "--app-label" in log_text
    assert "AndroidGame" in log_text
    assert validated_package_dirs == [result.package_result.package_dir]
    assert validation_diagnostic in result.diagnostics


def test_build_quest_openxr_project_exports_package_and_copies_apk(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "QuestGame"
    project.mkdir()
    _write_json(project / "QuestGame.terminproj", {"version": 1, "name": "QuestGame"})
    _write_json(project / "Main.scene", {"uuid": "root-scene", "entities": []})

    termin_root = tmp_path / "termin-root"
    apk_source = (
        termin_root
        / "build"
        / "android-gradle-openxr"
        / "app"
        / "outputs"
        / "apk"
        / "debug"
        / "app-debug.apk"
    )
    sdk_config = (
        termin_root
        / "sdk"
        / "android"
        / "arm64-v8a"
        / "lib"
        / "cmake"
        / "termin_openxr"
        / "termin_openxrConfig.cmake"
    )
    sdk_config.parent.mkdir(parents=True)
    sdk_config.write_text("# fake OpenXR CMake package\n", encoding="utf-8")

    build_script = termin_root / ("build-quest-openxr-apk.cmd" if os.name == "nt" else "build-quest-openxr-apk.sh")
    if os.name == "nt":
        build_script.write_text(
            "@echo off\n"
            f"mkdir \"{apk_source.parent}\" >NUL 2>NUL\n"
            f"<NUL set /p dummy=QUESTAPK>\"{apk_source}\"\n"
            "echo %*\n",
            encoding="utf-8",
        )
    else:
        build_script.write_text(
            "#!/bin/sh\n"
            "set -e\n"
            f"mkdir -p '{apk_source.parent}'\n"
            f"printf QUESTAPK > '{apk_source}'\n"
            "printf '%s\\n' \"$@\"\n",
            encoding="utf-8",
        )
    build_script.chmod(0o755)
    fake_gradle = tmp_path / "fake-gradle"
    fake_gradle.write_text("# fake gradle\n", encoding="utf-8")
    fake_gradle.chmod(0o755)

    validation_diagnostic = RuntimePackageExportDiagnostic(
        "warning",
        "manifest.json",
        "synthetic quest validator diagnostic",
    )
    validated_package_dirs: list[Path] = []

    def fake_validate_runtime_package(package_dir: Path) -> list[RuntimePackageExportDiagnostic]:
        validated_package_dirs.append(package_dir)
        return [validation_diagnostic]

    monkeypatch.setattr(quest_openxr_build, "validate_runtime_package", fake_validate_runtime_package)

    result = quest_openxr_build.build_quest_openxr_project(
        project_root=project,
        entry_scene="Main.scene",
        termin_root=termin_root,
        build_script=build_script,
        gradle=fake_gradle,
        shader_compiler=_write_fake_shader_compiler(tmp_path),
    )

    assert result.apk_path == project / "dist" / "quest_openxr" / "QuestGame" / "apk" / "QuestGame-quest-openxr-debug.apk"
    assert result.apk_path.read_bytes() == b"QUESTAPK"
    assert result.application_id == "org.termin.openxr"
    assert result.launch_activity == "android.app.NativeActivity"
    assert result.package_result.manifest_path.exists()
    log_text = result.log_path.read_text(encoding="utf-8")
    assert "--assets-dir" in log_text
    assert str(result.package_result.package_dir) in log_text
    assert "--sdk-root" in log_text
    assert str(termin_root / "sdk" / "android") in log_text
    assert validated_package_dirs == [result.package_result.package_dir]
    assert validation_diagnostic in result.diagnostics
