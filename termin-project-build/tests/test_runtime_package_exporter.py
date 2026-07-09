import json
from pathlib import Path

import numpy as np
import pytest

from termin.project_build import build_desktop_project, export_runtime_package
from termin.project_build.desktop_runtime_packager import package_desktop_runtime
from termin.project_build.runtime_package_exporter import (
    ENGINE_TEXT3D_SHADER_UUID,
    _default_pipeline_engine_shaders,
    _material_textures_to_json,
)
from termin.project_build.runtime_package.scene_refs import collect_runtime_refs

full_runtime_package_exporter = pytest.mark.full(
    reason="runtime package export/build scenarios spawn shader compiler subprocesses"
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_fake_shader_compiler(tmp_path: Path) -> Path:
    compiler = tmp_path / "fake_termin_shaderc.py"
    compiler.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        "inp = pathlib.Path(sys.argv[sys.argv.index('--input') + 1])\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
        "out.parent.mkdir(parents=True, exist_ok=True)\n"
        "out.write_bytes(b'SPIRV')\n"
        "source = inp.read_text(encoding='utf-8') if inp.exists() else ''\n"
        "resources = []\n"
        "if 'ConstantBuffer<PerFrame> per_frame' in source:\n"
        "    resources.append({'name': 'per_frame', 'kind': 'constant_buffer', 'scope': 'frame'})\n"
        "if 'ConstantBuffer<ShadowPushData> shadow_draw' in source:\n"
        "    resources.append({'name': 'shadow_draw', 'kind': 'constant_buffer', 'scope': 'draw'})\n"
        "if 'ConstantBuffer<MaterialParams> material' in source:\n"
        "    resources.append({'name': 'material', 'kind': 'constant_buffer', 'scope': 'material'})\n"
        "if 'Sampler2D u_input' in source:\n"
        "    resources.append({'name': 'u_input', 'kind': 'texture', 'scope': 'transient'})\n"
        "layout = {'version': 1, 'resources': resources}\n"
        "pathlib.Path(str(out) + '.layout.json').write_text(json.dumps(layout, indent=2), encoding='utf-8')\n",
        encoding="utf-8",
    )
    compiler.chmod(0o755)
    return compiler




def _write_fake_player_runtime_distributions(site_packages: Path) -> None:
    distributions: dict[str, tuple[dict[str, str], list[str]]] = {
        "termin-player": ({"termin/player/__init__.py": "VALUE = 'player seed'\n"}, ["termin-mcp"]),
        "termin-mcp": ({"termin/mcp/__init__.py": "VALUE = 'mcp seed'\n"}, []),
        "termin-nanobind": ({"termin_nanobind/__init__.py": "VALUE = 'nanobind seed'\n"}, []),
        "tcbase": ({"tcbase/__init__.py": "VALUE = 'runtime seed'\n"}, []),
        "termin-assets": ({"termin_assets_seed/__init__.py": "VALUE = 'assets seed'\n"}, []),
        "termin-default-assets": ({"termin/default_assets/__init__.py": "VALUE = 'default assets seed'\n"}, []),
        "termin-stdlib": (
            {
                "termin/stdlib/__init__.py": "VALUE = 'stdlib seed'\n",
                "termin/stdlib/resources/materials/BlinnPhong.material": "{}\n",
            },
            [],
        ),
        "termin-prefab": ({"termin/prefab_seed/__init__.py": "VALUE = 'prefab seed'\n"}, []),
        "termin-glb": ({"termin/glb/__init__.py": "VALUE = 'glb seed'\n"}, ["termin-skeleton", "termin-animation"]),
        "termin-tween": ({"termin/tween/__init__.py": "VALUE = 'tween seed'\n"}, []),
        "termin-components-tween": ({"termin/tween_components/__init__.py": "VALUE = 'tween components seed'\n"}, []),
        "termin-components-kinematic": (
            {
                "termin/kinematic/__init__.py": "VALUE = 'kinematic seed'\n",
                "termin/kinematic/kinematic_components.py": "VALUE = 'kinematic components seed'\n",
                "termin_kinematic_component_specs/__init__.py": "COMPONENT_SPECS = ()\n",
            },
            [],
        ),
        "termin-audio": ({"termin/audio/__init__.py": "VALUE = 'audio seed'\n"}, []),
        "termin-voxels": ({"termin/voxels/__init__.py": "VALUE = 'voxels seed'\n"}, []),
        "termin-components-voxels": ({"termin/voxel_components/__init__.py": "VALUE = 'voxel components seed'\n"}, []),
        "termin-components-physics": ({"termin/physics_components/__init__.py": "VALUE = 'physics components seed'\n"}, []),
        "termin-components-ui": ({"termin/ui_components/__init__.py": "VALUE = 'ui components seed'\n"}, []),
        "termin-materials": ({"termin/materials/__init__.py": "VALUE = 'materials seed'\n"}, []),
        "termin-shader-runtime": (
            {
                "termin/shader_tools.py": "VALUE = 'shader tools seed'\n",
                "termin/shader_runtime.py": "VALUE = 'shader runtime seed'\n",
            },
            [],
        ),
        "termin-render-passes": ({"termin/render_passes/__init__.py": "VALUE = 'render passes seed'\n"}, []),
        "termin-modules": ({"termin_modules/__init__.py": "VALUE = 'modules seed'\n"}, []),
        "termin-project": ({"termin/project/__init__.py": "VALUE = 'project seed'\n"}, []),
        "termin-project-modules": (
            {"termin/project_modules/__init__.py": "VALUE = 'project modules seed'\n"},
            ["termin-engine", "termin-project", "termin-modules"],
        ),
        "termin-scene": ({"termin/scene/__init__.py": "VALUE = 'scene seed'\n"}, []),
        "termin-display": (
            {
                "termin/display/__init__.py": "VALUE = 'display seed'\n",
                "termin/viewport/__init__.py": "VALUE = 'viewport seed'\n",
            },
            ["termin-image", "optional-extra; extra == 'debug'"],
        ),
        "termin-engine": ({"termin/engine/__init__.py": "VALUE = 'engine seed'\n"}, []),
        "termin-render": ({"termin/render/__init__.py": "VALUE = 'render seed'\n"}, []),
        "termin-components-render": ({"termin/render_components/__init__.py": "VALUE = 'render components seed'\n"}, []),
        "termin-input": ({"termin/input/__init__.py": "VALUE = 'input seed'\n"}, []),
        "termin-inspect": ({"termin/inspect/__init__.py": "VALUE = 'inspect seed'\n"}, []),
        "termin-collision": ({"termin/collision/__init__.py": "VALUE = 'collision seed'\n"}, []),
        "termin-physics": ({"termin/physics/__init__.py": "VALUE = 'physics seed'\n"}, []),
        "termin-physics-fem": ({"termin/physics_fem/__init__.py": "VALUE = 'physics fem seed'\n"}, ["termin-qopt"]),
        "termin-navmesh": ({"termin/navmesh/__init__.py": "VALUE = 'navmesh seed'\n"}, []),
        "termin-lighting": ({"termin/lighting/__init__.py": "VALUE = 'lighting seed'\n"}, []),
        "tmesh": ({"tmesh/__init__.py": "VALUE = 'tmesh seed'\n"}, []),
        "tgfx": ({"tgfx/__init__.py": "VALUE = 'tgfx seed'\n"}, []),
        "tcgui": ({"tcgui/__init__.py": "VALUE = 'tcgui seed'\n"}, []),
        "numpy": ({"numpy/__init__.py": "VALUE = 'numpy seed'\n"}, []),
        "termin-image": ({"termin/image/__init__.py": "VALUE = 'image seed'\n"}, []),
        "scipy": ({"scipy/__init__.py": "VALUE = 'scipy dependency'\n"}, []),
        "termin-qopt": ({"termin/fem/__init__.py": "VALUE = 'qopt fem seed'\n"}, ["scipy"]),
        "termin-skeleton": ({"termin/skeleton/__init__.py": "VALUE = 'skeleton seed'\n"}, []),
        "termin-animation": ({"termin/animation/__init__.py": "VALUE = 'animation seed'\n"}, []),
        "optional-extra": ({"optional_extra/__init__.py": "VALUE = 'optional extra'\n"}, []),
        "termin-build-tools": ({"termin_build/__init__.py": "VALUE = 'build tools'\n"}, ["setuptools"]),
    }
    for distribution, (files, requires) in distributions.items():
        _write_fake_distribution(site_packages, distribution, files, requires=requires)

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
    _write_fake_player_runtime_distributions(site_packages)
    (python_overlay / "termin" / "player").mkdir(parents=True)
    (python_overlay / "termin" / "__init__.py").write_text("", encoding="utf-8")
    (python_overlay / "termin" / "player" / "__main__.py").write_text(
        "# fresh player overlay\n",
        encoding="utf-8",
    )
    (share_dir / "termin_prelude.slang").write_text("// prelude\n", encoding="utf-8")
    return sdk


def test_legacy_app_runtime_lists_do_not_shadow_manifest_python_packages() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    cmake_install = (repo_root / "termin-app" / "CMakeLists.txt").read_text(encoding="utf-8")
    legacy_build = (repo_root / "termin-app" / "build.sh").read_text(encoding="utf-8")
    cpp_cmake = (repo_root / "termin-app" / "cpp" / "CMakeLists.txt").read_text(encoding="utf-8")

    assert "\n        scipy\n" not in cmake_install
    assert "foreach(pkg numpy scipy" not in cmake_install
    assert "termin-physics-fem" not in legacy_build
    assert "termin-physics-fem" not in cpp_cmake
    assert "TERMIN_SDK_PYTHON_PACKAGE_DIRS" not in cpp_cmake
    assert "../termin-assets/termin_assets" not in cpp_cmake
    assert "../termin-gui/python/tcgui" not in cpp_cmake
    assert "../termin-nodegraph/python/tcnodegraph" not in cpp_cmake


def _write_fake_windows_desktop_sdk(tmp_path: Path) -> Path:
    sdk = tmp_path / "fake-windows-sdk"
    bin_dir = sdk / "bin"
    lib_dir = sdk / "lib"
    python_lib = sdk / "python" / "Lib"
    python_dlls = sdk / "python" / "DLLs"
    site_packages = python_lib / "site-packages"
    python_overlay = lib_dir / "python"
    share_dir = sdk / "share" / "termin" / "builtin_shaders"

    bin_dir.mkdir(parents=True)
    lib_dir.mkdir(parents=True)
    site_packages.mkdir(parents=True)
    python_dlls.mkdir(parents=True)
    share_dir.mkdir(parents=True)

    (bin_dir / "termin_player.exe").write_bytes(b"player")
    (bin_dir / "termin_base.dll").write_bytes(b"termin")
    (bin_dir / "python312.dll").write_bytes(b"python")
    (sdk / "python" / "python.exe").write_bytes(b"python cli")
    (sdk / "python" / "python312.dll").write_bytes(b"python")
    (python_lib / "os.py").write_text("", encoding="utf-8")
    (python_dlls / "_ctypes.pyd").write_bytes(b"ctypes extension")
    (python_dlls / "libffi-8.dll").write_bytes(b"libffi")
    (site_packages / "termin").mkdir()
    (site_packages / "termin" / "__init__.py").write_text("", encoding="utf-8")
    _write_fake_player_runtime_distributions(site_packages)
    (python_overlay / "termin" / "player").mkdir(parents=True)
    (python_overlay / "termin" / "__init__.py").write_text("", encoding="utf-8")
    (python_overlay / "termin" / "player" / "__main__.py").write_text(
        "# fresh player overlay\n",
        encoding="utf-8",
    )
    (share_dir / "termin_prelude.slang").write_text("// prelude\n", encoding="utf-8")
    return sdk


def _write_fake_distribution(
    site_packages: Path,
    distribution: str,
    files: dict[str, str],
    requires: list[str] | None = None,
    version: str = "1.0",
) -> None:
    normalized = distribution.replace("-", "_")
    dist_info = site_packages / f"{normalized}-{version}.dist-info"
    dist_info.mkdir(parents=True)
    metadata_lines = [
        "Metadata-Version: 2.1",
        f"Name: {distribution}",
        f"Version: {version}",
    ]
    for requirement in requires or []:
        metadata_lines.append(f"Requires-Dist: {requirement}")
    (dist_info / "METADATA").write_text("\n".join(metadata_lines) + "\n", encoding="utf-8")

    record_paths: list[str] = []
    for rel_path, text in files.items():
        path = site_packages / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        record_paths.append(rel_path)
    record_paths.append(f"{dist_info.name}/METADATA")
    record_paths.append(f"{dist_info.name}/RECORD")
    (dist_info / "RECORD").write_text(
        "".join(f"{path},,\n" for path in record_paths),
        encoding="utf-8",
    )


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


def test_collect_runtime_refs_accepts_explicit_mesh_material_metadata() -> None:
    diagnostics = []

    refs = collect_runtime_refs(
        {
            "components": [
                {
                    "mesh_ref": {
                        "uuid": "typed-mesh",
                        "name": "Typed Mesh",
                        "type": "uuid",
                        "kind": "tc_mesh",
                    },
                },
                {
                    "material_ref": {
                        "uuid": "typed-material",
                        "name": "Typed Material",
                        "type": "uuid",
                        "role": "material",
                    },
                },
            ],
        },
        diagnostics,
    )

    assert refs.meshes == {"typed-mesh": "Typed Mesh"}
    assert refs.materials == {"typed-material": "Typed Material"}
    assert diagnostics == []


def test_collect_runtime_refs_reports_legacy_mesh_material_inference() -> None:
    diagnostics = []

    refs = collect_runtime_refs(
        {
            "components": [
                {
                    "mesh": {
                        "uuid": "field-mesh",
                        "name": "Field Mesh",
                        "type": "uuid",
                    },
                },
                {
                    "resource_ref": {
                        "uuid": "name-material",
                        "name": "Name Material",
                        "type": "uuid",
                    },
                },
            ],
        },
        diagnostics,
    )

    assert refs.meshes == {"field-mesh": "Field Mesh"}
    assert refs.materials == {"name-material": "Name Material"}
    assert [
        (diagnostic.level, diagnostic.path, diagnostic.message)
        for diagnostic in diagnostics
    ] == [
        (
            "warning",
            "scene.json",
            "Runtime exporter inferred mesh resource ref from legacy field name "
            "at $.components[0].mesh; add kind='tc_mesh' or role='mesh' to the uuid ref",
        ),
        (
            "warning",
            "scene.json",
            "Runtime exporter inferred material resource ref from legacy resource name "
            "at $.components[1].resource_ref; add kind='tc_material' or role='material' "
            "to the uuid ref",
        ),
    ]


@full_runtime_package_exporter
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


@full_runtime_package_exporter
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


@full_runtime_package_exporter
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
                            "type": "MeshComponent",
                            "data": {
                                "mesh": {
                                    "uuid": "missing-mesh",
                                    "name": "MissingMesh",
                                    "type": "uuid",
                                },
                            },
                        },
                        {
                            "type": "MeshRenderer",
                            "data": {
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


@full_runtime_package_exporter
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
                            "type": "MeshComponent",
                            "data": {
                                "mesh": {
                                    "uuid": mesh_uuid,
                                    "name": "Triangle",
                                    "type": "uuid",
                                },
                            },
                        },
                        {
                            "type": "MeshRenderer",
                            "data": {
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


@full_runtime_package_exporter
def test_export_runtime_package_reports_malformed_mesh_meta_before_dev_smoke_fallback(tmp_path: Path) -> None:
    project = tmp_path / "MalformedMeshMetaGame"
    project.mkdir()
    mesh_uuid = "broken-meta-mesh-uuid"

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
    Path(str(mesh_path) + ".meta").write_text("{", encoding="utf-8")
    _write_json(
        project / "Main.scene",
        {
            "uuid": "scene-uuid",
            "entities": [
                {
                    "uuid": "entity-uuid",
                    "components": [
                        {
                            "type": "MeshComponent",
                            "data": {
                                "mesh": {
                                    "uuid": mesh_uuid,
                                    "name": "Triangle",
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
        output_dir=project / "dist" / "dev_smoke" / "MalformedMeshMetaGame" / "package",
        shader_compiler=_write_fake_shader_compiler(tmp_path),
        resource_policy="dev_smoke",
    )

    assert (result.package_dir / "meshes" / f"{mesh_uuid}.tmesh.json").exists()
    diagnostics = [(diagnostic.path, diagnostic.message) for diagnostic in result.diagnostics]
    assert any(
        path == "Models/Triangle.obj.meta"
        and message.startswith("Runtime exporter failed to inspect mesh metadata:")
        for path, message in diagnostics
    )
    assert any(
        path == f"meshes/{mesh_uuid}.tmesh.json"
        and message == "Runtime exporter used fallback mesh because registry entry is unavailable"
        for path, message in diagnostics
    )


@full_runtime_package_exporter
def test_build_desktop_project_writes_bundle_contract(tmp_path: Path) -> None:
    project = tmp_path / "DesktopGame"
    project.mkdir()
    _write_json(
        project / "project_settings" / "project.json",
        {"player_window": {"width": 1366, "height": 768, "fullscreen": False}},
    )
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
    assert result.runtime_result.python_package_policy == "minimal_strict"
    assert result.runtime_result.python_runtime_manifest_path == result.dist_dir / "python-runtime.json"
    assert result.app_manifest_path.exists()
    app_manifest = json.loads(result.app_manifest_path.read_text(encoding="utf-8"))
    assert app_manifest["runtime"]["window"] == {
        "width": 1366,
        "height": 768,
        "fullscreen": False,
    }
    assert result.package_result.manifest_path.exists()
    assert result.python_result.manifest_path.exists()
    assert result.runtime_result.python_runtime_manifest_path.exists()
    assert not (result.dist_dir / "build.json").exists()
    assert not (result.dist_dir / "assets").exists()
    assert (result.dist_dir / "package" / "python" / "game.pymodule").exists()
    assert (result.dist_dir / "package" / "python" / "Scripts" / "__init__.py").exists()
    assert (result.dist_dir / "package" / "python" / "Scripts" / "Controller.py").exists()
    assert not (result.dist_dir / "package" / "python" / "Scripts" / "__pycache__").exists()
    assert result.runtime_result.launcher_path == result.dist_dir / "DesktopGame"
    assert (result.dist_dir / "DesktopGame").exists()
    assert not (result.dist_dir / "bin" / "termin_player").exists()
    assert (result.dist_dir / "lib" / "libpython3.10.so").exists()
    assert (result.dist_dir / "lib" / "libtermin_base.so").exists()
    assert (result.dist_dir / "lib" / "python3.10" / "os.py").exists()
    assert (result.dist_dir / "lib" / "python3.10" / "site-packages" / "termin" / "__init__.py").exists()
    assert (result.dist_dir / "lib" / "python3.10" / "site-packages" / "termin" / "display" / "__init__.py").exists()
    assert (result.dist_dir / "lib" / "python3.10" / "site-packages" / "termin" / "viewport" / "__init__.py").exists()
    assert (result.dist_dir / "lib" / "python3.10" / "site-packages" / "termin" / "skeleton" / "__init__.py").exists()
    assert (result.dist_dir / "lib" / "python3.10" / "site-packages" / "termin" / "kinematic" / "__init__.py").exists()
    assert (
        result.dist_dir
        / "lib"
        / "python3.10"
        / "site-packages"
        / "termin_kinematic_component_specs"
        / "__init__.py"
    ).exists()
    assert (result.dist_dir / "lib" / "python3.10" / "site-packages" / "tcbase" / "__init__.py").exists()
    assert (result.dist_dir / "lib" / "python3.10" / "site-packages" / "termin" / "image" / "__init__.py").exists()
    assert not (result.dist_dir / "lib" / "python3.10" / "site-packages" / "termin_build").exists()
    assert not (result.dist_dir / "lib" / "python3.10" / "site-packages" / "optional_extra").exists()
    assert not (result.dist_dir / "lib" / "python3.10" / "site-packages" / "termin" / "physics_fem").exists()
    assert not (result.dist_dir / "lib" / "python3.10" / "site-packages" / "termin" / "fem").exists()
    assert not (result.dist_dir / "lib" / "python3.10" / "site-packages" / "scipy").exists()
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
            "launcher": "DesktopGame",
            "python": {
                "enabled": True,
                "home": "lib/python3.10",
                "package_policy": "minimal_strict",
                "runtime_manifest": "python-runtime.json",
                "project_modules": "package/python",
                "module_manifest": "package/python/modules.json",
                "descriptors": [
                    "package/python/game.pymodule",
                ],
            },
            "native_library_dirs": [
                "lib",
            ],
            "window": {
                "width": 1366,
                "height": 768,
                "fullscreen": False,
            },
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
    runtime_manifest = json.loads(
        result.runtime_result.python_runtime_manifest_path.read_text(encoding="utf-8")
    )
    assert runtime_manifest["package_policy"] == "minimal_strict"
    assert {
        "name": "tcbase",
        "version": "1.0",
        "source": "termin-runtime",
    } in runtime_manifest["distributions"]
    assert {
        "name": "termin-image",
        "version": "1.0",
        "source": "termin-runtime",
    } in runtime_manifest["distributions"]
    assert {
        "name": "termin-display",
        "version": "1.0",
        "source": "termin-runtime",
    } in runtime_manifest["distributions"]
    assert {
        "name": "termin-skeleton",
        "version": "1.0",
        "source": "termin-runtime",
    } in runtime_manifest["distributions"]


def test_desktop_runtime_packager_accepts_windows_sdk_layout(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist" / "WindowsGame"

    result = package_desktop_runtime(
        dist_dir=dist_dir,
        requirements=[],
        sdk_root=_write_fake_windows_desktop_sdk(tmp_path),
    )

    assert result.diagnostics == []
    assert result.python_home == dist_dir.resolve() / "python"
    assert result.python_site_packages == dist_dir.resolve() / "python" / "Lib" / "site-packages"
    assert result.python_package_policy == "minimal_strict"
    assert result.python_runtime_manifest_path == dist_dir.resolve() / "python-runtime.json"
    assert result.launcher_path == dist_dir.resolve() / "WindowsGame.exe"
    assert (dist_dir / "WindowsGame.exe").exists()
    assert (dist_dir / "termin_base.dll").exists()
    assert (dist_dir / "python312.dll").exists()
    assert not (dist_dir / "bin" / "termin_player.exe").exists()
    assert (dist_dir / "python" / "python.exe").exists()
    assert (dist_dir / "python" / "python312.dll").exists()
    assert (dist_dir / "python" / "Lib" / "os.py").exists()
    assert (dist_dir / "python" / "DLLs" / "_ctypes.pyd").exists()
    assert (dist_dir / "python" / "DLLs" / "libffi-8.dll").exists()
    assert (dist_dir / "python" / "Lib" / "site-packages" / "termin" / "__init__.py").exists()
    assert (dist_dir / "python" / "Lib" / "site-packages" / "termin" / "display" / "__init__.py").exists()
    assert (dist_dir / "python" / "Lib" / "site-packages" / "termin" / "viewport" / "__init__.py").exists()
    assert (dist_dir / "python" / "Lib" / "site-packages" / "termin" / "skeleton" / "__init__.py").exists()
    assert (dist_dir / "python" / "Lib" / "site-packages" / "termin" / "kinematic" / "__init__.py").exists()
    assert (
        dist_dir
        / "python"
        / "Lib"
        / "site-packages"
        / "termin_kinematic_component_specs"
        / "__init__.py"
    ).exists()
    assert (dist_dir / "python" / "Lib" / "site-packages" / "tcbase" / "__init__.py").exists()
    assert (dist_dir / "python" / "Lib" / "site-packages" / "termin" / "image" / "__init__.py").exists()
    assert not (dist_dir / "python" / "Lib" / "site-packages" / "termin_build").exists()
    assert not (dist_dir / "python" / "Lib" / "site-packages" / "optional_extra").exists()
    assert not (dist_dir / "python" / "Lib" / "site-packages" / "termin" / "physics_fem").exists()
    assert not (dist_dir / "python" / "Lib" / "site-packages" / "termin" / "fem").exists()
    assert not (dist_dir / "python" / "Lib" / "site-packages" / "scipy").exists()
    assert (
        dist_dir
        / "python"
        / "Lib"
        / "site-packages"
        / "termin"
        / "player"
        / "__main__.py"
    ).exists()
    assert (dist_dir / "share" / "termin" / "builtin_shaders" / "termin_prelude.slang").exists()


def test_desktop_runtime_packager_refreshes_existing_windows_root_dlls(tmp_path: Path) -> None:
    sdk = _write_fake_windows_desktop_sdk(tmp_path)
    runtime_dll = sdk / "bin" / "termin_render_passes.dll"
    runtime_dll.write_bytes(b"old runtime")
    dist_dir = tmp_path / "dist" / "WindowsGame"

    first_result = package_desktop_runtime(
        dist_dir=dist_dir,
        requirements=[],
        sdk_root=sdk,
    )
    assert first_result.diagnostics == []
    assert (dist_dir / "termin_render_passes.dll").read_bytes() == b"old runtime"

    (dist_dir / "removed_runtime.dll").write_bytes(b"stale runtime")
    runtime_dll.write_bytes(b"new runtime")

    second_result = package_desktop_runtime(
        dist_dir=dist_dir,
        requirements=[],
        sdk_root=sdk,
    )

    assert second_result.diagnostics == []
    assert (dist_dir / "termin_render_passes.dll").read_bytes() == b"new runtime"
    assert not (dist_dir / "removed_runtime.dll").exists()


def test_desktop_runtime_packager_removes_stale_linux_root_libraries(tmp_path: Path) -> None:
    sdk = _write_fake_desktop_sdk(tmp_path)
    runtime_so = sdk / "lib" / "libtermin_render_passes.so"
    runtime_so.write_bytes(b"old runtime")
    dist_dir = tmp_path / "dist" / "LinuxGame"

    first_result = package_desktop_runtime(
        dist_dir=dist_dir,
        requirements=[],
        sdk_root=sdk,
    )
    assert first_result.diagnostics == []
    assert (dist_dir / "lib" / "libtermin_render_passes.so").read_bytes() == b"old runtime"

    (dist_dir / "libremoved_runtime.so").write_bytes(b"stale root runtime")
    (dist_dir / "libremoved_runtime.so.1").write_bytes(b"stale root runtime")
    (dist_dir / "bin" / "removed_runtime.dll").write_bytes(b"stale bin runtime")
    (dist_dir / "lib" / "removed_runtime.so").write_bytes(b"stale lib runtime")
    runtime_so.write_bytes(b"new runtime")

    second_result = package_desktop_runtime(
        dist_dir=dist_dir,
        requirements=[],
        sdk_root=sdk,
    )

    assert second_result.diagnostics == []
    assert (dist_dir / "lib" / "libtermin_render_passes.so").read_bytes() == b"new runtime"
    assert not (dist_dir / "libremoved_runtime.so").exists()
    assert not (dist_dir / "libremoved_runtime.so.1").exists()
    assert not (dist_dir / "bin" / "removed_runtime.dll").exists()
    assert not (dist_dir / "lib" / "removed_runtime.so").exists()


def test_desktop_runtime_packager_legacy_policy_copies_sdk_site_packages(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist" / "LegacyGame"

    result = package_desktop_runtime(
        dist_dir=dist_dir,
        requirements=[],
        sdk_root=_write_fake_desktop_sdk(tmp_path),
        python_package_policy="sdk_broad_copy",
    )

    assert result.diagnostics == []
    assert result.python_package_policy == "sdk_broad_copy"
    assert (dist_dir / "lib" / "python3.10" / "site-packages" / "scipy" / "__init__.py").exists()
    runtime_manifest = json.loads(
        result.python_runtime_manifest_path.read_text(encoding="utf-8")
    )
    assert runtime_manifest["package_policy"] == "sdk_broad_copy"


def test_desktop_runtime_packager_copies_requirements_from_project_venv(
    tmp_path: Path,
) -> None:
    source_site_packages = tmp_path / "project" / ".venv" / "Lib" / "site-packages"
    source_site_packages.mkdir(parents=True)
    _write_fake_distribution(
        source_site_packages,
        "python-chess",
        {},
        requires=["chess"],
    )
    _write_fake_distribution(
        source_site_packages,
        "chess",
        {
            "chess/__init__.py": "VALUE = 'copied from project venv'\n",
        },
    )
    dist_dir = tmp_path / "dist" / "RequirementGame"

    result = package_desktop_runtime(
        dist_dir=dist_dir,
        requirements=["python-chess"],
        sdk_root=_write_fake_windows_desktop_sdk(tmp_path),
        requirement_search_paths=[source_site_packages],
    )

    target_site_packages = dist_dir.resolve() / "python" / "Lib" / "site-packages"
    assert result.diagnostics == []
    assert (target_site_packages / "python_chess-1.0.dist-info" / "METADATA").exists()
    assert (target_site_packages / "chess" / "__init__.py").read_text(encoding="utf-8") == (
        "VALUE = 'copied from project venv'\n"
    )


def test_desktop_runtime_packager_rejects_requirement_version_mismatch(
    tmp_path: Path,
) -> None:
    source_site_packages = tmp_path / "project" / ".venv" / "Lib" / "site-packages"
    source_site_packages.mkdir(parents=True)
    _write_fake_distribution(
        source_site_packages,
        "python-chess",
        {
            "chess/__init__.py": "VALUE = 'too old'\n",
        },
        version="1.0",
    )
    dist_dir = tmp_path / "dist" / "RequirementVersionGame"

    result = package_desktop_runtime(
        dist_dir=dist_dir,
        requirements=["python-chess>=2"],
        sdk_root=_write_fake_desktop_sdk(tmp_path),
        requirement_search_paths=[source_site_packages],
    )

    target_site_packages = dist_dir.resolve() / "lib" / "python3.10" / "site-packages"
    diagnostic_messages = [diagnostic.message for diagnostic in result.diagnostics]
    assert any(
        message.startswith(
            "Installed Python requirement version does not satisfy python-chess>=2:"
        )
        and "python-chess 1.0" in message
        for message in diagnostic_messages
    )
    assert not (target_site_packages / "python_chess-1.0.dist-info" / "METADATA").exists()
    assert not (target_site_packages / "chess" / "__init__.py").exists()


def test_desktop_runtime_packager_uses_later_compatible_requirement_distribution(
    tmp_path: Path,
) -> None:
    sdk_root = _write_fake_desktop_sdk(tmp_path)
    sdk_site_packages = sdk_root / "lib" / "python3.10" / "site-packages"
    source_site_packages = tmp_path / "project" / ".venv" / "Lib" / "site-packages"
    source_site_packages.mkdir(parents=True)
    _write_fake_distribution(
        sdk_site_packages,
        "python-chess",
        {
            "chess/__init__.py": "VALUE = 'sdk old'\n",
        },
        version="1.0",
    )
    _write_fake_distribution(
        source_site_packages,
        "python-chess",
        {
            "chess/__init__.py": "VALUE = 'project compatible'\n",
        },
        version="2.0",
    )
    dist_dir = tmp_path / "dist" / "CompatibleRequirementGame"

    result = package_desktop_runtime(
        dist_dir=dist_dir,
        requirements=["python-chess>=2"],
        sdk_root=sdk_root,
        requirement_search_paths=[source_site_packages],
    )

    target_site_packages = dist_dir.resolve() / "lib" / "python3.10" / "site-packages"
    assert result.diagnostics == []
    assert (target_site_packages / "python_chess-2.0.dist-info" / "METADATA").exists()
    assert not (target_site_packages / "python_chess-1.0.dist-info" / "METADATA").exists()
    assert (target_site_packages / "chess" / "__init__.py").read_text(encoding="utf-8") == (
        "VALUE = 'project compatible'\n"
    )


def test_desktop_runtime_packager_includes_requested_extra_dependencies(
    tmp_path: Path,
) -> None:
    dist_dir = tmp_path / "dist" / "ExtraRequirementGame"

    result = package_desktop_runtime(
        dist_dir=dist_dir,
        requirements=["termin-display[debug]"],
        sdk_root=_write_fake_desktop_sdk(tmp_path),
    )

    target_site_packages = dist_dir.resolve() / "lib" / "python3.10" / "site-packages"
    assert result.diagnostics == []
    assert (target_site_packages / "optional_extra" / "__init__.py").exists()


def test_desktop_runtime_packager_skips_unrequested_extra_dependencies(
    tmp_path: Path,
) -> None:
    dist_dir = tmp_path / "dist" / "NoExtraRequirementGame"

    result = package_desktop_runtime(
        dist_dir=dist_dir,
        requirements=["termin-display"],
        sdk_root=_write_fake_desktop_sdk(tmp_path),
    )

    target_site_packages = dist_dir.resolve() / "lib" / "python3.10" / "site-packages"
    assert result.diagnostics == []
    assert not (target_site_packages / "optional_extra" / "__init__.py").exists()


def test_desktop_runtime_packager_processes_extras_for_already_copied_distribution(
    tmp_path: Path,
) -> None:
    source_site_packages = tmp_path / "project" / ".venv" / "Lib" / "site-packages"
    source_site_packages.mkdir(parents=True)
    _write_fake_distribution(
        source_site_packages,
        "toolkit",
        {
            "toolkit/__init__.py": "VALUE = 'toolkit'\n",
        },
        requires=["render-dep; extra == 'render'"],
    )
    _write_fake_distribution(
        source_site_packages,
        "render-dep",
        {
            "render_dep/__init__.py": "VALUE = 'render dep'\n",
        },
    )
    dist_dir = tmp_path / "dist" / "RepeatedExtraRequirementGame"

    result = package_desktop_runtime(
        dist_dir=dist_dir,
        requirements=["toolkit", "toolkit[render]"],
        sdk_root=_write_fake_desktop_sdk(tmp_path),
        requirement_search_paths=[source_site_packages],
    )

    target_site_packages = dist_dir.resolve() / "lib" / "python3.10" / "site-packages"
    assert result.diagnostics == []
    assert (target_site_packages / "toolkit" / "__init__.py").exists()
    assert (target_site_packages / "render_dep" / "__init__.py").exists()


def test_desktop_runtime_packager_prefers_newest_duplicate_distribution_metadata(
    tmp_path: Path,
) -> None:
    sdk_root = _write_fake_desktop_sdk(tmp_path)
    sdk_site_packages = sdk_root / "lib" / "python3.10" / "site-packages"
    _write_fake_distribution(
        sdk_site_packages,
        "numpy",
        {
            "numpy/__init__.py": "from ._expired_attrs_2_0 import VALUE\n",
        },
        version="1.26.4",
    )
    _write_fake_distribution(
        sdk_site_packages,
        "numpy",
        {
            "numpy/__init__.py": "from ._expired_attrs_2_0 import VALUE\n",
            "numpy/_expired_attrs_2_0.py": "VALUE = 2\n",
        },
        version="2.2.6",
    )
    dist_dir = tmp_path / "dist" / "DuplicateMetadataGame"

    result = package_desktop_runtime(
        dist_dir=dist_dir,
        requirements=[],
        sdk_root=sdk_root,
    )

    target_site_packages = dist_dir.resolve() / "lib" / "python3.10" / "site-packages"
    assert result.diagnostics == []
    assert (target_site_packages / "numpy-2.2.6.dist-info" / "METADATA").exists()
    assert (target_site_packages / "numpy" / "_expired_attrs_2_0.py").read_text(
        encoding="utf-8"
    ) == "VALUE = 2\n"


@full_runtime_package_exporter
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
            / "vulkan"
            / "termin-engine-tonemap.frag.spv.layout.json"
        ).read_text(encoding="utf-8")
    )
    assert {
        "name": "u_input",
        "kind": "texture",
        "scope": "transient",
    } in tonemap_layout["resources"]

    grayscale_layout = json.loads(
        (
            result.package_dir
            / "shaders"
            / "vulkan"
            / "termin-engine-grayscale.frag.spv.layout.json"
        ).read_text(encoding="utf-8")
    )
    assert {
        "name": "u_input",
        "kind": "texture",
        "scope": "transient",
    } in grayscale_layout["resources"]

    shadow_layout = json.loads(
        (
            result.package_dir
            / "shaders"
            / "vulkan"
            / "termin-engine-shadow.vert.spv.layout.json"
        ).read_text(encoding="utf-8")
    )
    assert {
        "name": "per_frame",
        "kind": "constant_buffer",
        "scope": "frame",
    } in shadow_layout["resources"]
    assert {
        "name": "shadow_draw",
        "kind": "constant_buffer",
        "scope": "draw",
    } in shadow_layout["resources"]

    skybox_layout = json.loads(
        (
            result.package_dir
            / "shaders"
            / "vulkan"
            / "termin-engine-skybox.frag.spv.layout.json"
        ).read_text(encoding="utf-8")
    )
    assert {
        "name": "material",
        "kind": "constant_buffer",
        "scope": "material",
    } in skybox_layout["resources"]
    assert not (result.package_dir / "shaders" / "layout").exists()


@full_runtime_package_exporter
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


@full_runtime_package_exporter
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
        "d3d11": {
            "vertex": "shaders/d3d11/termin-runtime-default-color.vs.cso",
            "fragment": "shaders/d3d11/termin-runtime-default-color.ps.cso",
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


@full_runtime_package_exporter
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


@full_runtime_package_exporter
def test_export_runtime_package_collects_pass_aware_pipeline_shader_usages(tmp_path: Path) -> None:
    from termin.bootstrap import bootstrap_player
    from termin.geombase import Vec3
    from termin.render_components import LineRenderMode, LineRenderer
    from termin.render_framework import RenderPipeline
    from termin.render_passes import ColorPass
    from termin.scene import TcScene

    bootstrap_player()

    project = tmp_path / "PipelineShaderUsageGame"
    project.mkdir()
    pipeline_uuid = "pipeline-shader-usage-uuid"

    scene = TcScene.create("pipeline-shader-usage-scene")
    pipeline = RenderPipeline("LinePipeline")
    try:
        entity = scene.create_entity("line")
        entity.add_component(
            LineRenderer(
                points=[Vec3(0, 0, 0), Vec3(1, 0, 0)],
                render_mode=LineRenderMode.WorldTube,
            )
        )
        scene_data = scene.serialize()
        scene_data["uuid"] = "scene-uuid"
        scene_data["render_mount"] = {
            "render_target_configs": [
                {
                    "name": "MainTarget",
                    "kind": "window",
                    "pipeline_uuid": pipeline_uuid,
                    "pipeline_name": "LinePipeline",
                    "enabled": True,
                }
            ],
        }
        _write_json(project / "Main.scene", scene_data)

        pipeline.add_pass(ColorPass(phase_mark="opaque"))
        _write_json(project / "LinePipeline.pipeline", pipeline.serialize())
        _write_json(project / "LinePipeline.pipeline.meta", {"uuid": pipeline_uuid})
    finally:
        pipeline.destroy()
        scene.destroy()

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "package",
        shader_compiler=_write_fake_shader_compiler(tmp_path),
    )

    shader_names = {
        json.loads(path.read_text(encoding="utf-8"))["name"]
        for path in (result.package_dir / "shaders").glob("*.shader.json")
    }
    assert "termin-engine-line-default" in shader_names
    assert "termin-engine-line-default_LineTubeBody" in shader_names
    assert "termin-engine-line-default_LineTubeCap" in shader_names
    assert not [diagnostic for diagnostic in result.diagnostics if diagnostic.level == "error"]


@full_runtime_package_exporter
def test_export_runtime_package_collects_non_color_skinned_pipeline_shader_usage(
    tmp_path: Path,
) -> None:
    import tgfx
    from termin.bootstrap import bootstrap_player
    from termin.materials import TcMaterial
    from termin.mesh import MeshComponent
    from termin.render_components import SkinnedMeshRenderer
    from termin.scene import TcScene
    from termin.skeleton import TcSkeleton
    from termin.skeleton_components import SkeletonController
    from tmesh import TcAttribType, TcDrawMode, TcMesh, TcVertexLayout

    bootstrap_player()

    project = tmp_path / "SkinnedDepthPipelineGame"
    project.mkdir()
    pipeline_uuid = "skinned-depth-pipeline-uuid"
    mesh_uuid = "skinned-depth-mesh-uuid"
    material_uuid = "skinned-depth-material-uuid"
    shader_uuid = "skinned-depth-shader-uuid"
    skeleton_uuid = "skinned-depth-skeleton-uuid"

    layout = TcVertexLayout()
    layout.add("position", 3, TcAttribType.FLOAT32, 0)
    layout.add("normal", 3, TcAttribType.FLOAT32, 1)
    vertices = np.array(
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
        ],
        dtype=np.float32,
    )
    indices = np.array([0, 1, 2], dtype=np.uint32)
    mesh = TcMesh.from_interleaved(
        vertices,
        3,
        indices,
        layout,
        "Skinned Depth Triangle",
        mesh_uuid,
        TcDrawMode.TRIANGLES,
    )
    assert mesh.is_valid

    material = TcMaterial.create("Skinned Depth Material", material_uuid)
    assert material.is_valid
    phase = material.add_phase_from_sources(
        '[shader("vertex")] void main() {}\n',
        '[shader("fragment")] void main() {}\n',
        "",
        "SkinnedDepthShader",
        "opaque",
        0,
        shader_uuid=shader_uuid,
    )
    assert phase is not None
    shader = tgfx.TcShader.from_uuid(shader_uuid)
    assert shader.is_valid
    shader.set_language(tgfx.ShaderLanguage.SLANG)
    shader.set_artifact_policy(tgfx.ShaderArtifactPolicy.REQUIRED)

    skeleton = TcSkeleton.create("Skinned Depth Skeleton", skeleton_uuid)
    skeleton.alloc_bones(1)
    bone = skeleton.get_bone(0)
    bone.name = "root"
    bone.index = 0
    bone.parent_index = -1
    bone.inverse_bind_matrix = [
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
    ]
    skeleton.rebuild_roots()

    scene = TcScene.create("skinned-depth-pipeline-scene")
    try:
        root = scene.create_entity("skinned")
        bone_entity = scene.create_entity("root_bone")
        controller = SkeletonController(skeleton, [bone_entity])
        root.add_component(controller)

        mesh_component = MeshComponent()
        mesh_component.set_mesh(mesh)
        root.add_component(mesh_component)
        root.add_component(SkinnedMeshRenderer(material, controller, True))

        scene_data = scene.serialize()
        scene_data["uuid"] = "scene-uuid"
        scene_data["render_mount"] = {
            "render_target_configs": [
                {
                    "name": "MainTarget",
                    "kind": "window",
                    "pipeline_uuid": pipeline_uuid,
                    "pipeline_name": "SkinnedDepthPipeline",
                    "enabled": True,
                }
            ],
        }
        _write_json(project / "Main.scene", scene_data)

        _write_json(
            project / "SkinnedDepthPipeline.pipeline",
            {
                "name": "SkinnedDepthPipeline",
                "passes": [
                    {
                        "type": "DepthPass",
                        "pass_name": "Depth",
                        "enabled": True,
                        "passthrough": False,
                        "viewport_name": "",
                        "data": {
                            "input_res": "empty_depth",
                            "output_res": "depth",
                            "camera_name": "",
                            "phase_mark": "opaque",
                            "depth_encoding": "linear",
                            "clear": True,
                        },
                    }
                ],
                "pipeline_specs": [],
            },
        )
        _write_json(project / "SkinnedDepthPipeline.pipeline.meta", {"uuid": pipeline_uuid})
    finally:
        scene.destroy()

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "package",
        shader_compiler=_write_fake_shader_compiler(tmp_path),
    )

    shader_specs = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (result.package_dir / "shaders").glob("*.shader.json")
    ]
    shader_names = {spec["name"] for spec in shader_specs}
    assert "SkinnedDepthShader" in shader_names
    skinned_depth_spec = next(
        (
            spec
            for spec in shader_specs
            if spec["name"].startswith("SkinnedDepthShader_Skinned_skinned_depth")
        ),
        None,
    )
    assert skinned_depth_spec is not None
    assert skinned_depth_spec["language"] == "slang"
    assert (
        result.package_dir / skinned_depth_spec["artifacts"]["vulkan"]["vertex"]
    ).read_bytes() == b"SPIRV"
    assert not [diagnostic for diagnostic in result.diagnostics if diagnostic.level == "error"]


@full_runtime_package_exporter
def test_export_runtime_package_reports_malformed_pipeline_meta(tmp_path: Path) -> None:
    project = tmp_path / "MalformedPipelineMetaGame"
    project.mkdir()
    pipeline_uuid = "pipeline-with-broken-meta"

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
    (project / "VrPipeline.pipeline.meta").write_text("{", encoding="utf-8")

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "quest_openxr" / "MalformedPipelineMetaGame" / "package",
        shader_compiler=_write_fake_shader_compiler(tmp_path),
    )

    assert (result.package_dir / "pipelines" / f"{pipeline_uuid}.pipeline.json").exists()
    assert any(
        diagnostic.path == "VrPipeline.pipeline.meta"
        and diagnostic.message.startswith("Runtime exporter failed to inspect pipeline metadata:")
        for diagnostic in result.diagnostics
    )


@full_runtime_package_exporter
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
                            "type": "MeshComponent",
                            "data": {
                                "mesh": {
                                    "uuid": mesh_uuid,
                                    "name": "Live Triangle",
                                    "type": "uuid",
                                    "kind": "tc_mesh",
                                },
                            },
                        },
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "material": {
                                    "uuid": material_uuid,
                                    "name": "Live Material",
                                    "type": "uuid",
                                    "kind": "tc_material",
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
    assert mesh_data["submeshes"] == [
        {
            "first_index": 0,
            "index_count": 3,
            "vertex_offset": 0,
            "material_slot": 0,
            "draw_mode": "triangles",
            "name": "Live Triangle",
        }
    ]
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


@full_runtime_package_exporter
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
                                    "kind": "tc_material",
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
        "d3d11": {
            "vertex": f"shaders/d3d11/{shader_uuid}.vs.cso",
            "fragment": f"shaders/d3d11/{shader_uuid}.ps.cso",
        },
    }
    assert (result.package_dir / "shaders" / "vulkan" / f"{shader_uuid}.vert.spv").read_bytes() == b"ARTIFACT-vulkan"
    assert (result.package_dir / "shaders" / "opengl" / f"{shader_uuid}.frag.glsl").read_bytes() == b"ARTIFACT-opengl"
    assert (result.package_dir / "shaders" / "d3d11" / f"{shader_uuid}.ps.cso").read_bytes() == b"ARTIFACT-d3d11"
    calls = [
        json.loads(line)
        for line in (tmp_path / "target_shaderc_calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert {call[call.index("--target") + 1] for call in calls} == {"vulkan", "opengl", "d3d11"}
    assert all("--layout-scheme" not in call for call in calls)
    assert result.diagnostics == []


@full_runtime_package_exporter
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
                                    "kind": "tc_material",
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
