import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from termin.project import make_default_scene
from termin.project_build import export_runtime_package
from termin.project_build.runtime_package_exporter import (
    ENGINE_TEXT3D_SHADER_UUID,
    _builtin_pipeline_names,
    _default_pipeline_engine_shaders,
    _material_textures_to_json,
)
from termin.project_build.runtime_package.models import ShaderSpec
from termin.project_build.runtime_package.materials import _shader_source_identity
from termin.project_build.runtime_package.shaders import (
    ENGINE_MULTIVIEW_TONEMAP_SHADER_UUID,
    EngineShaderArtifact,
    artifact_path_text,
    compile_shader_stage,
    copy_prebuilt_engine_shader_artifacts,
    normalize_shader_targets,
    write_shader,
)
from termin.project_build.runtime_package.scene_refs import collect_runtime_refs
from termin.project_build.runtime_package.sprites import write_sprites
from termin.project_build.runtime_package.ui_documents import (
    stage_ui_documents_for_scene_analysis,
    write_ui_documents,
)

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
        "target = sys.argv[sys.argv.index('--target') + 1]\n"
        "stage = sys.argv[sys.argv.index('--stage') + 1]\n"
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
        "layout = {'version': 3 if target == 'webgpu' else 1, "
        "          'target': target, 'stage': stage, 'resources': resources}\n"
        "pathlib.Path(str(out) + '.layout.json').write_text(json.dumps(layout, indent=2), encoding='utf-8')\n",
        encoding="utf-8",
    )
    compiler.chmod(0o755)
    return compiler


def _write_counting_shader_compiler(tmp_path: Path) -> tuple[Path, Path]:
    compiler = tmp_path / "counting_termin_shaderc.py"
    calls = tmp_path / "shaderc-calls.txt"
    compiler.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        f"calls = pathlib.Path({str(calls)!r})\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
        "target = sys.argv[sys.argv.index('--target') + 1]\n"
        "stage = sys.argv[sys.argv.index('--stage') + 1]\n"
        "out.parent.mkdir(parents=True, exist_ok=True)\n"
        "out.write_text('compiled-' + target, encoding='utf-8')\n"
        "layout = {'version': 3 if target == 'webgpu' else 1, 'target': target, 'stage': stage, 'resources': []}\n"
        "pathlib.Path(str(out) + '.layout.json').write_text(json.dumps(layout), encoding='utf-8')\n"
        "with calls.open('a', encoding='utf-8') as stream: stream.write('call\\n')\n",
        encoding="utf-8",
    )
    compiler.chmod(0o755)
    return compiler, calls


def test_sprite_asset_ref_and_texture_are_exported_together(tmp_path: Path) -> None:
    project = tmp_path / "SpriteGame"
    package = tmp_path / "package"
    sprite_uuid = "sprite-uuid"
    texture_uuid = "texture-uuid"
    sprite_path = project / "Assets" / "hero.sprite"
    _write_json(
        sprite_path,
        {
            "format": "termin.sprite",
            "version": 1,
            "texture": {"uuid": texture_uuid, "name": "atlas"},
            "region": [4, 8, 16, 24],
            "source_size": [64, 64],
            "pivot": [0.5, 0.0],
            "pixels_per_unit": 16.0,
            "sampling": "nearest",
        },
    )
    _write_json(Path(f"{sprite_path}.meta"), {"uuid": sprite_uuid})
    refs = collect_runtime_refs(
        {
            "components": [
                {
                    "type": "SpriteRenderer2D",
                    "data": {
                        "sprite": {
                            "type": "uuid",
                            "kind": "sprite_asset",
                            "role": "sprite",
                            "uuid": sprite_uuid,
                        }
                    },
                }
            ]
        }
    )
    assert refs.sprites == {sprite_uuid: sprite_uuid}

    resources: list[dict[str, str]] = []
    diagnostics = []
    write_sprites(
        project,
        package,
        refs.sprites,
        refs.textures,
        resources,
        diagnostics,
    )

    assert diagnostics == []
    assert refs.textures == {texture_uuid: "atlas"}
    assert resources == [
        {
            "type": "sprite_asset",
            "uuid": sprite_uuid,
            "name": sprite_uuid,
            "path": f"sprites/{sprite_uuid}.sprite.json",
        }
    ]
    packaged = json.loads((package / "sprites" / f"{sprite_uuid}.sprite.json").read_text(encoding="utf-8"))
    assert packaged["texture"]["uuid"] == texture_uuid


def test_native_ui_document_ref_is_compiled_for_runtime(tmp_path: Path) -> None:
    project = tmp_path / "UiGame"
    package = tmp_path / "package"
    uuid_value = "native-ui-uuid"
    source = project / "UI" / "hud.uiscript"
    source.parent.mkdir(parents=True)
    source.write_text(
        "uiscript: 2\n"
        "root:\n"
        "  type: termin.gui.ScrollArea\n"
        "  name: hud\n"
        "  horizontal_scroll: false\n"
        "  children:\n"
        "    - type: termin.gui.GridLayout\n"
        "      columns:\n"
        "        - policy: stretch\n"
        "      rows:\n"
        "        - policy: stretch\n"
        "      children:\n"
        "        - type: termin.gui.Panel\n"
        "          row: 0\n"
        "          column: 0\n"
        "          background_color: [0.1, 0.2, 0.3, 1]\n",
        encoding="utf-8",
    )
    _write_json(Path(f"{source}.meta"), {"uuid": uuid_value})
    refs = collect_runtime_refs(
        {
            "ui_layout": {
                "type": "uuid",
                "kind": "ui_document",
                "uuid": uuid_value,
                "name": "hud",
            }
        }
    )
    assert refs.ui_documents == {uuid_value: "hud"}

    resources: list[dict[str, str]] = []
    diagnostics = []
    write_ui_documents(
        project,
        package,
        refs.ui_documents,
        resources,
        diagnostics,
    )

    assert diagnostics == []
    assert resources == [
        {
            "type": "ui_document",
            "uuid": uuid_value,
            "name": "hud",
            "path": f"ui/{uuid_value}.ui-document.json",
        }
    ]
    payload = json.loads((package / "ui" / f"{uuid_value}.ui-document.json").read_text(encoding="utf-8"))
    assert payload["ui_document_asset"] == 1
    assert payload["uuid"] == uuid_value
    assert payload["type_dependencies"] == [
        "termin.gui.ScrollArea",
        "termin.gui.GridLayout",
        "termin.gui.Panel",
    ]
    assert payload["recipe"]["uiscript"] == 2
    from termin.gui_native import UiDocumentAsset

    assert not UiDocumentAsset.from_uuid(uuid_value).valid
    temporary = stage_ui_documents_for_scene_analysis(
        package,
        resources,
        diagnostics,
    )
    assert diagnostics == []
    assert len(temporary) == 1
    assert temporary[0].valid
    assert UiDocumentAsset.from_uuid(uuid_value).valid
    assert temporary[0].remove()
    assert not UiDocumentAsset.from_uuid(uuid_value).valid


def _write_fake_player_runtime_distributions(site_packages: Path) -> None:
    distributions: dict[str, tuple[dict[str, str], list[str]]] = {
        "termin-player": ({"termin/player/__init__.py": "VALUE = 'player seed'\n"}, ["termin-mcp"]),
        "termin-mcp": ({"termin/mcp/__init__.py": "VALUE = 'mcp seed'\n"}, []),
        "termin-nanobind": ({"termin_nanobind/__init__.py": "VALUE = 'nanobind seed'\n"}, []),
        "termin-base": ({"termin/base/__init__.py": "VALUE = 'runtime seed'\n"}, []),
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
            ["termin-scene", "termin-inspect", "termin-robotics"],
        ),
        "termin-audio": ({"termin/audio/__init__.py": "VALUE = 'audio seed'\n"}, []),
        "termin-voxels": ({"termin/voxels/__init__.py": "VALUE = 'voxels seed'\n"}, []),
        "termin-components-voxels": ({"termin/voxel_components/__init__.py": "VALUE = 'voxel components seed'\n"}, []),
        "termin-components-physics": (
            {"termin/physics_components/__init__.py": "VALUE = 'physics components seed'\n"},
            [],
        ),
        "termin-components-ui": (
            {"termin/ui_components/__init__.py": "VALUE = 'ui components seed'\n"},
            ["termin-gui-native"],
        ),
        "termin-gui-native": (
            {"termin/gui_native/__init__.py": "VALUE = 'native ui dependency'\n"},
            [],
        ),
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
        "termin-components-render": (
            {"termin/render_components/__init__.py": "VALUE = 'render components seed'\n"},
            [],
        ),
        "termin-input": ({"termin/input/__init__.py": "VALUE = 'input seed'\n"}, []),
        "termin-inspect": ({"termin/inspect/__init__.py": "VALUE = 'inspect seed'\n"}, []),
        "termin-collision": ({"termin/collision/__init__.py": "VALUE = 'collision seed'\n"}, []),
        "termin-physics": ({"termin/physics/__init__.py": "VALUE = 'physics seed'\n"}, []),
        "termin-robotics": ({"termin/robotics/__init__.py": "VALUE = 'robotics seed'\n"}, []),
        "termin-physics-fem": ({"termin/physics_fem/__init__.py": "VALUE = 'physics fem seed'\n"}, ["termin-qopt"]),
        "termin-navmesh": ({"termin/navmesh/__init__.py": "VALUE = 'navmesh seed'\n"}, []),
        "termin-lighting": ({"termin/lighting/__init__.py": "VALUE = 'lighting seed'\n"}, []),
        "termin-mesh": ({"termin/mesh/__init__.py": "VALUE = 'mesh seed'\n"}, []),
        "termin-graphics-core": (
            {"termin/graphics/__init__.py": "VALUE = 'graphics seed'\n"},
            [],
        ),
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


def test_legacy_app_build_entrypoints_do_not_shadow_sdk_manifest() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_root = repo_root / "termin-app"
    cpp_cmake = (repo_root / "termin-app" / "cpp" / "CMakeLists.txt").read_text(encoding="utf-8")

    assert not (app_root / "CMakeLists.txt").exists()
    assert not (app_root / "build.sh").exists()
    assert not (app_root / "build.ps1").exists()
    assert "termin-physics-fem" not in cpp_cmake
    assert "TERMIN_SDK_PYTHON_PACKAGE_DIRS" not in cpp_cmake
    assert "../termin-assets/termin_assets" not in cpp_cmake
    assert "../termin-nodegraph/python/termin.nodegraph" not in cpp_cmake


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
    assert ENGINE_MULTIVIEW_TONEMAP_SHADER_UUID in shader_uuids


def test_builtin_shader_program_artifact_stages_match_material_parser() -> None:
    from termin.materials import parse_shader_text

    source_root = Path(__file__).resolve().parents[3] / "graphics/termin-graphics/resources/builtin_shaders"
    catalog = json.loads((source_root / "engine-shader-catalog.json").read_text(encoding="utf-8"))
    program_entries = [entry for entry in catalog["shaders"] if entry["language"] == "shader"]
    assert program_entries
    for entry in program_entries:
        program = parse_shader_text((source_root / entry["program"]["path"]).read_text(encoding="utf-8"))
        assert len(program.phases) == 1
        for stage_name, artifact_stage in entry["artifact_stages"].items():
            assert (source_root / artifact_stage["path"]).read_text(encoding="utf-8") == program.phases[0].stages[
                stage_name
            ].source


def test_prebuilt_engine_shader_artifacts_are_verified_and_copied(
    tmp_path: Path,
) -> None:
    root = tmp_path / "prebuilt"
    catalog_path = root / "builtin_shaders/engine-shader-catalog.json"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_text('{"version": 1, "shaders": []}\n', encoding="utf-8")
    relative_artifact = "shaders/webgpu/engine-example.vert.wgsl"
    artifact = root / relative_artifact
    artifact.parent.mkdir(parents=True)
    artifact.write_text("@vertex fn main() {}", encoding="utf-8")
    layout = Path(f"{artifact}.layout.json")
    layout.write_text(
        json.dumps(
            {
                "version": 3,
                "target": "webgpu",
                "stage": "vertex",
                "resources": [],
            }
        ),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "catalog": "builtin_shaders/engine-shader-catalog.json",
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "targets": ["webgpu"],
        "artifacts": [
            {
                "uuid": "engine-example",
                "target": "webgpu",
                "stage": "vertex",
                "path": relative_artifact,
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "layout": f"{relative_artifact}.layout.json",
                "layout_sha256": hashlib.sha256(layout.read_bytes()).hexdigest(),
            }
        ],
    }
    _write_json(root / "builtin-shader-artifacts.json", manifest)
    package = tmp_path / "package"
    shaders = [
        EngineShaderArtifact(
            uuid="engine-example",
            name="Example",
            language="slang",
            vertex_source="source",
        )
    ]

    with pytest.raises(FileNotFoundError, match="manifest does not exist"):
        copy_prebuilt_engine_shader_artifacts(
            tmp_path / "missing-package",
            tmp_path / "missing-root",
            shaders,
            ("webgpu",),
        )

    copy_prebuilt_engine_shader_artifacts(package, root, shaders, ("webgpu",))

    copied = package / relative_artifact
    assert copied.read_bytes() == artifact.read_bytes()
    assert Path(f"{copied}.layout.json").read_bytes() == layout.read_bytes()

    artifact.write_text("corrupted", encoding="utf-8")
    with pytest.raises(ValueError, match="hash does not match"):
        copy_prebuilt_engine_shader_artifacts(tmp_path / "invalid-package", root, shaders, ("webgpu",))

    manifest["schema_version"] = 99
    _write_json(root / "builtin-shader-artifacts.json", manifest)
    with pytest.raises(ValueError, match="requires schema version 1"):
        copy_prebuilt_engine_shader_artifacts(tmp_path / "incompatible-package", root, shaders, ("webgpu",))


def test_shader_artifact_cache_hits_and_source_changes_invalidate(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compiler, calls = _write_counting_shader_compiler(tmp_path)
    builtin_root = tmp_path / "builtin-shaders"
    builtin_root.mkdir()
    builtin_source = builtin_root / "termin_prelude.slang"
    builtin_source.write_text("builtin-first", encoding="utf-8")
    monkeypatch.setenv("TGFX2_BUILTIN_SHADER_ROOT", str(builtin_root))
    source = tmp_path / "shader.slang"
    source.write_text("first", encoding="utf-8")
    cache = tmp_path / "cache"
    output = tmp_path / "one.spv"

    compile_shader_stage(
        compiler,
        "slang",
        "vulkan",
        "vertex",
        source,
        output,
        "cache-test",
        artifact_cache_dir=cache,
    )
    output.unlink()
    Path(f"{output}.layout.json").unlink()
    compile_shader_stage(
        compiler,
        "slang",
        "vulkan",
        "vertex",
        source,
        output,
        "cache-test",
        artifact_cache_dir=cache,
    )
    builtin_source.write_text("builtin-second", encoding="utf-8")
    compile_shader_stage(
        compiler,
        "slang",
        "vulkan",
        "vertex",
        source,
        tmp_path / "two.spv",
        "cache-test",
        artifact_cache_dir=cache,
    )
    source.write_text("second", encoding="utf-8")
    compile_shader_stage(
        compiler,
        "slang",
        "vulkan",
        "vertex",
        source,
        tmp_path / "three.spv",
        "cache-test",
        artifact_cache_dir=cache,
    )

    assert calls.read_text(encoding="utf-8").splitlines() == ["call", "call", "call"]
    output_text = capsys.readouterr().out
    assert "[ShaderArtifact] compiling" in output_text
    assert "[ShaderArtifact] cache hit" in output_text


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


def test_collect_runtime_refs_accepts_default_scene_contract() -> None:
    diagnostics = []

    refs = collect_runtime_refs(make_default_scene()["scene"], diagnostics)

    assert refs.meshes == {
        "00000000-0000-0000-0003-000000000001": "Cube",
        "00000000-0000-0000-0003-000000000003": "Plane",
    }
    assert refs.materials == {
        "00000000-0001-0000-0001-000000000003": "NormalizedPBR",
    }
    assert diagnostics == []


def test_builtin_pipeline_names_include_future_builtin_without_uuid() -> None:
    scene = {
        "extensions": {
            "render_mount": {
                "render_target_configs": [
                    {"pipeline_name": "Default"},
                    {"pipeline_name": "DeferredPrototype"},
                    {
                        "pipeline_name": "Authored",
                        "pipeline_uuid": "authored-pipeline-uuid",
                    },
                ]
            }
        }
    }

    assert _builtin_pipeline_names(scene) == {"Default", "DeferredPrototype"}


def test_surface_producer_shader_is_metadata_only(tmp_path: Path) -> None:
    compiler = tmp_path / "compiler-must-not-run"
    compiler.write_text("#!/bin/sh\nexit 97\n", encoding="utf-8")
    compiler.chmod(0o755)
    resources: list[dict[str, str]] = []
    shader = ShaderSpec(
        uuid="surface-producer",
        name="Surface Producer",
        source_path="Materials/Surface.shader",
        vertex_source="",
        fragment_source="TerminSurface evaluate_surface() {}",
        language="slang",
        surface_producer={
            "contract_id": "game.surface",
            "contract_version": 1,
            "surface_type_name": "TerminSurface",
            "evaluator_entry": "evaluate_surface",
            "evaluator_source": "TerminSurface evaluate_surface() {}",
            "source_identity": "evaluator:v1",
        },
        surface_interface_identity="interface:v1",
        source_identity="sha256:producer",
        artifact_role="surface_producer",
    )

    spec = write_shader(
        tmp_path / "package",
        resources,
        [],
        shader,
        compiler,
        ("vulkan", "opengl", "d3d11"),
    )

    assert "artifacts" not in spec
    assert spec["artifact_role"] == "surface_producer"
    assert spec["surface_contract"] == {
        "id": "game.surface",
        "version": 1,
        "interface_source_identity": "interface:v1",
    }
    assert resources == [
        {
            "type": "shader",
            "uuid": "surface-producer",
            "path": "shaders/surface-producer.shader.json",
        }
    ]
    assert not list((tmp_path / "package" / "shaders").rglob("*.spv"))
    assert not list((tmp_path / "package" / "shaders").rglob("*.cso"))


def test_composed_shader_identity_tracks_every_source_dependency() -> None:
    shader = SimpleNamespace(
        language="slang",
        vertex_entry="vertex_main",
        fragment_entry="fragment_main",
        geometry_entry="",
        vertex_source="// vertex-provider:v1",
        fragment_source=(
            '// interface:v1\n// evaluator:v1\n// consumer:v1\n[shader("fragment")] void fragment_main() {}'
        ),
        geometry_source="",
    )

    original = _shader_source_identity(shader, surface_interface_identity="interface:v1")
    evaluator_changed = SimpleNamespace(
        **{
            **vars(shader),
            "fragment_source": shader.fragment_source.replace("evaluator:v1", "evaluator:v2"),
        }
    )
    consumer_changed = SimpleNamespace(
        **{
            **vars(shader),
            "fragment_source": shader.fragment_source.replace("consumer:v1", "consumer:v2"),
        }
    )

    assert _shader_source_identity(shader, surface_interface_identity="interface:v2") != original
    assert _shader_source_identity(evaluator_changed, surface_interface_identity="interface:v1") != original
    assert _shader_source_identity(consumer_changed, surface_interface_identity="interface:v1") != original


def test_synthetic_surface_pass_variant_compiles_all_targets(tmp_path: Path) -> None:
    shader = ShaderSpec(
        uuid="shv_synthetic_surface",
        name="SyntheticSurface_GBuffer",
        source_path="runtime-registry",
        vertex_source='[shader("vertex")] void vertex_main() {}',
        fragment_source=(
            "// interface:project-v1\n"
            "// evaluator:project-v1\n"
            "// consumer:gbuffer-v1\n"
            '[shader("fragment")] void fragment_main() {}'
        ),
        language="slang",
        vertex_entry="vertex_main",
        fragment_entry="fragment_main",
        source_identity="sha256:synthetic-composed",
        artifact_role="pipeline_variant",
        register_in_runtime=False,
    )
    resources: list[dict[str, str]] = []
    package = tmp_path / "package"

    spec = write_shader(
        package,
        resources,
        [],
        shader,
        _write_fake_shader_compiler(tmp_path),
        ("vulkan", "opengl", "d3d11", "webgpu"),
    )

    assert list(spec["artifacts"]) == ["vulkan", "opengl", "d3d11", "webgpu"]
    assert all((package / path).is_file() for target in spec["artifacts"].values() for path in target.values())
    assert resources == []
    assert spec["artifacts"]["webgpu"] == {
        "vertex": "shaders/webgpu/shv_synthetic_surface.vert.wgsl",
        "fragment": "shaders/webgpu/shv_synthetic_surface.frag.wgsl",
    }
    for artifact in spec["artifacts"]["webgpu"].values():
        layout = json.loads(Path(f"{package / artifact}.layout.json").read_text(encoding="utf-8"))
        assert layout["version"] == 3
        assert layout["target"] == "webgpu"


def test_fragment_only_pipeline_variant_compiles_only_fragment_stage(
    tmp_path: Path,
) -> None:
    shader = ShaderSpec(
        uuid="shv_fragment_only",
        name="FragmentOnlyLineVariant",
        source_path="runtime-registry",
        vertex_source="",
        fragment_source='[shader("fragment")] void fragment_main() {}',
        language="slang",
        fragment_entry="fragment_main",
        source_identity="sha256:fragment-only",
        artifact_role="pipeline_variant",
        register_in_runtime=False,
    )
    resources: list[dict[str, str]] = []
    package = tmp_path / "package"

    spec = write_shader(
        package,
        resources,
        [],
        shader,
        _write_fake_shader_compiler(tmp_path),
        ("vulkan", "opengl", "d3d11", "webgpu"),
    )

    assert "vertex_source_path" not in spec
    assert "vertex_entry" not in spec
    assert all(set(artifacts) == {"fragment"} for artifacts in spec["artifacts"].values())
    assert not list((package / "shaders").rglob("shv_fragment_only.vert.*"))
    assert all((package / artifact["fragment"]).is_file() for artifact in spec["artifacts"].values())
    assert resources == []


def test_constrained_gl_shader_targets_have_distinct_package_paths() -> None:
    assert normalize_shader_targets(["OpenGL330", "webgl2"]) == (
        "opengl330",
        "webgl2",
    )
    assert artifact_path_text("shader-uuid", "opengl330", "vertex", "vert") == "shaders/opengl330/shader-uuid.vert.glsl"
    assert artifact_path_text("shader-uuid", "webgl2", "fragment", "frag") == "shaders/webgl2/shader-uuid.frag.glsl"


@full_runtime_package_exporter
def test_strict_runtime_export_accepts_default_scene_resources(tmp_path: Path) -> None:
    project = tmp_path / "DefaultSceneGame"
    project.mkdir()
    _write_json(project / "scene.scene", make_default_scene())

    result = export_runtime_package(
        project_root=project,
        entry_scene="scene.scene",
        output_dir=project / "dist" / "package",
        shader_compiler=_write_fake_shader_compiler(tmp_path),
    )

    assert [diagnostic for diagnostic in result.diagnostics if diagnostic.level == "error"] == []
    assert (result.package_dir / "meshes" / "00000000-0000-0000-0003-000000000001.tmesh.json").exists()
    assert (result.package_dir / "meshes" / "00000000-0000-0000-0003-000000000003.tmesh.json").exists()
    assert (result.package_dir / "materials" / "00000000-0001-0000-0001-000000000003.tmat.json").exists()


def test_collect_runtime_refs_accepts_canonical_pipeline_template_mount() -> None:
    refs = collect_runtime_refs(
        {
            "extensions": {
                "render_mount": {"pipeline_templates": [{"uuid": "compiled-pipeline-uuid", "name": "Main Pipeline"}]}
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
    assert [(diagnostic.level, diagnostic.path, diagnostic.message) for diagnostic in diagnostics] == [
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
    assert manifest["version"] == 3
    assert manifest["entry_scene"] == "Scenes/Main.scene"
    assert manifest["world_controller"] is None
    assert manifest["scenes"] == [
        {
            "identity": "Scenes/Main.scene",
            "path": "scenes/Scenes/Main.scene.json",
        }
    ]
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
    assert "Runtime exporter used fallback mesh because registry entry is unavailable" in diagnostic_messages
    assert "Runtime exporter used fallback material because registry entry is unavailable" in diagnostic_messages


@full_runtime_package_exporter
def test_export_runtime_package_emits_multi_scene_closure(tmp_path: Path) -> None:
    project = tmp_path / "MultiSceneGame"
    main_scene = project / "Scenes" / "Main.scene"
    menu_scene = project / "Scenes" / "Menu.scene"
    _write_json(
        project / "project_settings" / "project.json",
        {
            "world_controller": {
                "module": "game",
                "type": "game.ProjectDirector",
            }
        },
    )
    _write_json(
        main_scene,
        {
            "uuid": "main-scene",
            "entities": [
                {
                    "components": [
                        {
                            "data": {
                                "mesh": {
                                    "type": "uuid",
                                    "uuid": "main-mesh",
                                    "name": "Main Mesh",
                                    "kind": "tc_mesh",
                                }
                            }
                        }
                    ]
                }
            ],
        },
    )
    _write_json(
        menu_scene,
        {
            "uuid": "menu-scene",
            "entities": [
                {
                    "components": [
                        {
                            "data": {
                                "mesh": {
                                    "type": "uuid",
                                    "uuid": "menu-mesh",
                                    "name": "Menu Mesh",
                                    "kind": "tc_mesh",
                                }
                            }
                        }
                    ]
                }
            ],
        },
    )

    result = export_runtime_package(
        project_root=project,
        entry_scene=main_scene,
        scenes=(main_scene, menu_scene),
        output_dir=tmp_path / "bundle/package",
        shader_compiler=_write_fake_shader_compiler(tmp_path),
        resource_policy="dev_smoke",
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    shutil.rmtree(project)
    assert manifest["entry_scene"] == "Scenes/Main.scene"
    assert manifest["world_controller"] == {
        "module": "game",
        "type": "game.ProjectDirector",
    }
    assert manifest["scenes"] == [
        {
            "identity": "Scenes/Main.scene",
            "path": "scenes/Scenes/Main.scene.json",
        },
        {
            "identity": "Scenes/Menu.scene",
            "path": "scenes/Scenes/Menu.scene.json",
        },
    ]
    assert set(result.scene_paths) == {"Scenes/Main.scene", "Scenes/Menu.scene"}
    assert all(path.is_file() for path in result.scene_paths.values())
    assert (result.package_dir / "meshes/main-mesh.tmesh.json").is_file()
    assert (result.package_dir / "meshes/menu-mesh.tmesh.json").is_file()
    resource_uuids = {resource.get("uuid") for resource in manifest["resources"]}
    assert {"main-mesh", "menu-mesh"} <= resource_uuids


@full_runtime_package_exporter
def test_export_runtime_package_includes_project_material_assets(tmp_path: Path) -> None:
    import numpy as np

    from termin.image import write_png_rgba8_file

    project = tmp_path / "DynamicMaterialGame"
    project.mkdir()
    material_uuid = "dynamic-highlight-material"
    texture_uuid = "dynamic-highlight-texture"
    texture_path = project / "Textures" / "Highlight.png"
    texture_path.parent.mkdir()
    write_png_rgba8_file(
        texture_path,
        np.full((1, 1, 4), [255, 230, 26, 255], dtype=np.uint8),
    )
    _write_json(Path(f"{texture_path}.meta"), {"uuid": texture_uuid})
    _write_json(project / "Main.scene", {"uuid": "scene-uuid", "entities": []})
    _write_json(
        project / "Materials" / "Highlight.material",
        {
            "uuid": material_uuid,
            "shader": "CookTorrancePBR",
            "uniforms": {
                "u_color": [1.0, 0.9, 0.1, 1.0],
            },
            "textures": {
                "u_albedo_texture": texture_uuid,
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
    material_spec = json.loads(
        (result.package_dir / "materials" / f"{material_uuid}.tmat.json").read_text(encoding="utf-8")
    )
    assert material_spec["textures"]["u_albedo_texture"]["uuid"] == texture_uuid
    assert {
        "type": "texture",
        "uuid": texture_uuid,
        "path": f"textures/{texture_uuid}.texture.json",
    } in manifest["resources"]
    assert (result.package_dir / "textures" / f"{texture_uuid}.png").read_bytes() == (texture_path.read_bytes())


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
                        },
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
        (diagnostic.level, diagnostic.path) for diagnostic in result.diagnostics if diagnostic.level == "error"
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
                        },
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
        path == "Models/Triangle.obj.meta" and message.startswith("Runtime exporter failed to inspect mesh metadata:")
        for path, message in diagnostics
    )
    assert any(
        path == f"meshes/{mesh_uuid}.tmesh.json"
        and message == "Runtime exporter used fallback mesh because registry entry is unavailable"
        for path, message in diagnostics
    )
