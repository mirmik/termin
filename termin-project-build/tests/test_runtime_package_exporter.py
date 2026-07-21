import json
from pathlib import Path

import pytest

from termin.project_build import export_runtime_package
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


def test_collect_runtime_refs_accepts_canonical_pipeline_template_mount() -> None:
    refs = collect_runtime_refs(
        {
            "extensions": {
                "render_mount": {
                    "pipeline_templates": [
                        {"uuid": "compiled-pipeline-uuid", "name": "Main Pipeline"}
                    ]
                }
            }
        }
    )

    assert refs.pipelines == {"compiled-pipeline-uuid": "Main Pipeline"}


def test_collect_runtime_refs_rejects_legacy_mesh_material_inference() -> None:
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

    assert refs.meshes == {}
    assert refs.materials == {}
    assert [
        (diagnostic.level, diagnostic.path, diagnostic.message)
        for diagnostic in diagnostics
    ] == [
        (
            "error",
            "scene.json",
            "Runtime exporter rejected legacy mesh resource ref from legacy field name "
            "at $.components[0].mesh; add kind='tc_mesh' or role='mesh' to the uuid ref",
        ),
        (
            "error",
            "scene.json",
            "Runtime exporter rejected legacy material resource ref from legacy resource name "
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
                                        "kind": "tc_mesh",
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
                                        "kind": "tc_material",
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
    assert "shader_artifact_root" not in manifest
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
                                    "kind": "tc_mesh",
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
                                    "kind": "tc_mesh",
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
                                    "kind": "tc_mesh",
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
