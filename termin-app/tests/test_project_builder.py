import json
import inspect
from pathlib import Path

from termin.project_build import profile_build
from termin.project_builder.builder import build_project
from termin.project_builder.__main__ import main as project_builder_main
from termin.project_builder.legacy_project_export import export_legacy_project


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_build_project_writes_manifest_and_copies_resources(tmp_path: Path) -> None:
    project = tmp_path / "SampleGame"
    project.mkdir()
    _write_json(project / "sample.terminproj", {"version": 1, "name": "SampleGame"})
    _write_json(
        project / "Scenes" / "Main.scene",
        {
            "version": "1.0",
            "scene": {
                "uuid": "scene-uuid",
                "entities": [],
            },
        },
    )
    texture = project / "Textures" / "Albedo.png"
    texture.parent.mkdir()
    texture.write_bytes(b"png")
    _write_json(texture.with_name(texture.name + ".meta"), {"uuid": "texture-uuid"})
    audio = project / "Audio" / "Hit.wav"
    audio.parent.mkdir()
    audio.write_bytes(b"wav")
    _write_json(audio.with_name(audio.name + ".meta"), {"uuid": "audio-uuid"})
    shader = project / "stdlib" / "shaders" / "StandardShader.shader"
    shader.parent.mkdir(parents=True)
    shader.write_text("shader", encoding="utf-8")
    _write_json(shader.with_name(shader.name + ".meta"), {"uuid": "shader-uuid"})
    material = project / "Materials" / "Default.material"
    _write_json(material, {"uuid": "material-uuid", "shader": "StandardShader"})
    pipeline = project / "Pipelines" / "Main.pipeline"
    _write_json(pipeline, {"nodes": []})
    _write_json(pipeline.with_name(pipeline.name + ".meta"), {"uuid": "pipeline-uuid"})
    scene_pipeline = project / "Pipelines" / "Scene.scene_pipeline"
    _write_json(scene_pipeline, {"nodes": []})
    _write_json(scene_pipeline.with_name(scene_pipeline.name + ".meta"), {"uuid": "scene-pipeline-uuid"})
    prefab = project / "Prefabs" / "Enemy.prefab"
    _write_json(prefab, {"uuid": "prefab-uuid", "entities": []})
    navmesh = project / "Nav" / "Level.navmesh"
    navmesh.parent.mkdir()
    navmesh.write_bytes(b"navmesh")
    _write_json(navmesh.with_name(navmesh.name + ".meta"), {"uuid": "navmesh-uuid"})
    voxels = project / "Voxels" / "Level.voxels"
    voxels.parent.mkdir()
    voxels.write_bytes(b"voxels")
    _write_json(voxels.with_name(voxels.name + ".meta"), {"uuid": "voxel-grid-uuid"})
    ui = project / "UI" / "Hud.uiscript"
    ui.parent.mkdir()
    ui.write_text("ui", encoding="utf-8")
    _write_json(ui.with_name(ui.name + ".meta"), {"uuid": "ui-uuid"})
    glb = project / "Models" / "Robot.glb"
    glb.parent.mkdir()
    glb.write_bytes(b"glb")
    _write_json(glb.with_name(glb.name + ".meta"), {"uuid": "glb-uuid"})

    result = build_project(
        project_root=project,
        entry_scene=Path("Scenes") / "Main.scene",
        output_dir=project / "dist" / "SampleGame",
    )

    assert result.build_json_path.exists()
    assert result.manifest_json_path.exists()
    assert (result.output_dir / "assets" / "Scenes" / "Main.scene").exists()
    assert (result.output_dir / "assets" / "Textures" / "Albedo.png").exists()
    assert (result.output_dir / "assets" / "Textures" / "Albedo.png.meta").exists()
    assert (result.output_dir / "stdlib" / "shaders" / "StandardShader.shader").exists()

    manifest_data = json.loads(result.manifest_json_path.read_text(encoding="utf-8"))
    resources = manifest_data["resources"]
    by_source = {resource["source_path"]: resource for resource in resources}

    assert by_source["Scenes/Main.scene"]["uuid"] == "scene-uuid"
    assert by_source["Scenes/Main.scene"]["type"] == "scene"
    assert by_source["Textures/Albedo.png"]["uuid"] == "texture-uuid"
    assert by_source["Audio/Hit.wav"]["type"] == "audio_clip"
    assert by_source["Audio/Hit.wav"]["uuid"] == "audio-uuid"
    assert by_source["Materials/Default.material"]["type"] == "material"
    assert by_source["Materials/Default.material"]["uuid"] == "material-uuid"
    assert by_source["stdlib/shaders/StandardShader.shader"]["type"] == "shader"
    assert by_source["stdlib/shaders/StandardShader.shader"]["uuid"] == "shader-uuid"
    assert by_source["Pipelines/Main.pipeline"]["type"] == "pipeline"
    assert by_source["Pipelines/Main.pipeline"]["uuid"] == "pipeline-uuid"
    assert by_source["Pipelines/Scene.scene_pipeline"]["type"] == "scene_pipeline"
    assert by_source["Pipelines/Scene.scene_pipeline"]["uuid"] == "scene-pipeline-uuid"
    assert by_source["Prefabs/Enemy.prefab"]["type"] == "prefab"
    assert by_source["Prefabs/Enemy.prefab"]["uuid"] == "prefab-uuid"
    assert by_source["Nav/Level.navmesh"]["type"] == "navmesh"
    assert by_source["Nav/Level.navmesh"]["uuid"] == "navmesh-uuid"
    assert by_source["Voxels/Level.voxels"]["type"] == "voxel_grid"
    assert by_source["Voxels/Level.voxels"]["uuid"] == "voxel-grid-uuid"
    assert by_source["UI/Hud.uiscript"]["type"] == "ui"
    assert by_source["UI/Hud.uiscript"]["uuid"] == "ui-uuid"
    assert by_source["Models/Robot.glb"]["type"] == "glb"
    assert by_source["Models/Robot.glb"]["uuid"] == "glb-uuid"
    assert by_source["stdlib/shaders/StandardShader.shader"]["build_path"] == "stdlib/shaders/StandardShader.shader"

    build_data = json.loads(result.build_json_path.read_text(encoding="utf-8"))
    assert build_data["project_name"] == "SampleGame"
    assert build_data["entry_scene"] == "assets/Scenes/Main.scene"
    assert build_data["asset_manifest"] == "assets/manifest.json"


def test_export_legacy_project_is_canonical_name_for_broad_copy_path(tmp_path: Path) -> None:
    project = tmp_path / "LegacyGame"
    project.mkdir()
    _write_json(project / "legacy.terminproj", {"version": 1, "name": "LegacyGame"})
    _write_json(project / "Main.scene", {"scene": {"uuid": "scene-uuid"}})

    result = export_legacy_project(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "LegacyGame",
        copy_files=False,
    )

    assert result.build_json_path == project / "dist" / "LegacyGame" / "build.json"
    assert result.manifest_json_path == project / "dist" / "LegacyGame" / "assets" / "manifest.json"
    assert result.build_json_path.exists()


def test_project_builder_cli_uses_explicit_legacy_dev_export_command(tmp_path: Path, capsys) -> None:
    project = tmp_path / "CliLegacyGame"
    project.mkdir()
    _write_json(project / "cli.terminproj", {"version": 1, "name": "CliLegacyGame"})
    _write_json(project / "Main.scene", {"scene": {"uuid": "scene-uuid"}})
    output_dir = project / "dist" / "CliLegacyGame"

    assert project_builder_main(
        [
            "legacy-dev-export",
            str(project),
            "--scene",
            "Main.scene",
            "--out",
            str(output_dir),
            "--manifest-only",
        ]
    ) == 0

    captured = capsys.readouterr()
    assert "Legacy dev export:" in captured.out
    assert "build.json" in captured.out
    assert captured.err == ""
    assert (output_dir / "build.json").exists()


def test_packaged_profile_backend_does_not_import_legacy_project_builder() -> None:
    source = inspect.getsource(profile_build)

    assert "termin.project_builder" not in source


def test_build_project_excludes_output_directory(tmp_path: Path) -> None:
    project = tmp_path / "Game"
    project.mkdir()
    _write_json(project / "game.terminproj", {"version": 1, "name": "Game"})
    _write_json(project / "Main.scene", {"scene": {"uuid": "scene-uuid"}})
    old_output_scene = project / "dist" / "Game" / "assets" / "Old.scene"
    _write_json(old_output_scene, {"scene": {"uuid": "old-scene"}})

    result = build_project(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "Game",
        copy_files=False,
    )

    source_paths = {resource.source_path for resource in result.manifest.resources}
    assert "Main.scene" in source_paths
    assert "dist/Game/assets/Old.scene" not in source_paths


def test_build_project_excludes_service_termin_directory(tmp_path: Path) -> None:
    project = tmp_path / "Game"
    project.mkdir()
    _write_json(project / "game.terminproj", {"version": 1, "name": "Game"})
    _write_json(project / "Main.scene", {"scene": {"uuid": "scene-uuid"}})
    artifact = project / ".termin" / "shader-artifacts" / "shaders" / "opengl" / "Generated.glsl"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("glsl", encoding="utf-8")
    artifact.with_name(artifact.name + ".artifact").write_text(
        "artifact_metadata_schema=1\n",
        encoding="utf-8",
    )

    result = build_project(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "Game",
        copy_files=False,
    )

    source_paths = {resource.source_path for resource in result.manifest.resources}
    assert "Main.scene" in source_paths
    assert ".termin/shader-artifacts/shaders/opengl/Generated.glsl" not in source_paths
    assert ".termin/shader-artifacts/shaders/opengl/Generated.glsl.artifact" not in source_paths


def test_build_project_excludes_project_ignored_resource_paths(tmp_path: Path) -> None:
    project = tmp_path / "Game"
    project.mkdir()
    _write_json(project / "game.terminproj", {"version": 1, "name": "Game"})
    _write_json(
        project / "project_settings" / "project.json",
        {
            "ignored_resource_paths": [
                "Generated",
                "LooseIgnored.png",
            ],
        },
    )
    _write_json(project / "Main.scene", {"scene": {"uuid": "scene-uuid"}})

    generated_scene = project / "Generated" / "Generated.scene"
    _write_json(generated_scene, {"scene": {"uuid": "generated-scene-uuid"}})
    loose_ignored = project / "LooseIgnored.png"
    loose_ignored.write_bytes(b"png")
    _write_json(loose_ignored.with_name(loose_ignored.name + ".meta"), {"uuid": "ignored-texture-uuid"})

    result = build_project(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "Game",
        copy_files=False,
    )

    source_paths = {resource.source_path for resource in result.manifest.resources}
    assert "Main.scene" in source_paths
    assert "project_settings/project.json" in source_paths
    assert "Generated/Generated.scene" not in source_paths
    assert "LooseIgnored.png" not in source_paths
    assert "LooseIgnored.png.meta" not in source_paths


def test_build_project_includes_python_module_descriptor_and_packages(tmp_path: Path) -> None:
    project = tmp_path / "PythonGame"
    project.mkdir()
    _write_json(project / "game.terminproj", {"version": 1, "name": "PythonGame"})
    _write_json(project / "Main.scene", {"scene": {"uuid": "scene-uuid"}})
    _write_json(
        project / "game.pymodule",
        {
            "name": "game",
            "type": "python",
            "root": ".",
            "packages": ["Scripts"],
            "requirements": ["python-chess"],
        },
    )
    scripts = project / "Scripts"
    scripts.mkdir()
    (scripts / "__init__.py").write_text("from Scripts.Controller import Controller\n", encoding="utf-8")
    (scripts / "Controller.py").write_text("class Controller:\n    pass\n", encoding="utf-8")
    pycache = scripts / "__pycache__"
    pycache.mkdir()
    (pycache / "Controller.cpython-310.pyc").write_bytes(b"pyc")

    result = build_project(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "PythonGame",
    )

    source_paths = {resource.source_path for resource in result.manifest.resources}
    by_source = {resource.source_path: resource for resource in result.manifest.resources}

    assert "game.pymodule" in source_paths
    assert "Scripts/__init__.py" in source_paths
    assert "Scripts/Controller.py" in source_paths
    assert "Scripts/__pycache__/Controller.cpython-310.pyc" not in source_paths
    assert by_source["game.pymodule"].kind == "module"
    assert by_source["game.pymodule"].type == "module"
    assert by_source["Scripts/Controller.py"].kind == "module"
    assert by_source["Scripts/Controller.py"].type == "module_source"
    assert by_source["Scripts/Controller.py"].build_path == "Scripts/Controller.py"

    assert (result.output_dir / "game.pymodule").exists()
    assert (result.output_dir / "Scripts" / "__init__.py").exists()
    assert (result.output_dir / "Scripts" / "Controller.py").exists()
    assert not (result.output_dir / "Scripts" / "__pycache__").exists()
    assert result.manifest.diagnostics == []


class _FakeShader:
    is_valid = True
    uuid = "shader-phase-uuid"
    name = "TestShader"
    vertex_source = "#version 450\nvoid main() {}\n"
    fragment_source = "#version 450\nlayout(location=0) out vec4 c; void main() { c = vec4(1); }\n"
    geometry_source = ""


class _FakeSlangShader:
    is_valid = True
    uuid = "slang-shader-phase-uuid"
    name = "TestSlangShader"
    language = "slang"
    vertex_source = "[shader(\"vertex\")] void main() {}\n"
    fragment_source = "[shader(\"fragment\")] void main() {}\n"
    geometry_source = ""


def test_build_project_compiles_shader_usages(tmp_path: Path) -> None:
    project = tmp_path / "ShaderGame"
    project.mkdir()
    _write_json(project / "game.terminproj", {"version": 1, "name": "ShaderGame"})
    _write_json(project / "Main.scene", {"scene": {"uuid": "scene-uuid"}})

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

    result = build_project(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "ShaderGame",
        compile_shaders=True,
        shader_usages=[_FakeShader()],
        shader_compiler=compiler,
    )

    source_root = result.output_dir / ".build" / "shaders" / "source"
    artifact_root = result.output_dir / "assets" / "shaders" / "vulkan"
    assert (source_root / "shader-phase-uuid.vert.glsl").exists()
    assert (source_root / "shader-phase-uuid.frag.glsl").exists()
    assert (artifact_root / "shader-phase-uuid.vert.spv").read_bytes() == b"SPIRV"
    assert (artifact_root / "shader-phase-uuid.frag.spv").read_bytes() == b"SPIRV"

    resources = result.manifest.resources
    shader_resources = [resource for resource in resources if resource.type == "shader_spirv"]
    assert {resource.build_path for resource in shader_resources} == {
        "assets/shaders/vulkan/shader-phase-uuid.vert.spv",
        "assets/shaders/vulkan/shader-phase-uuid.frag.spv",
    }


def test_build_project_compiles_slang_shader_usages_for_vulkan_and_opengl(tmp_path: Path) -> None:
    project = tmp_path / "SlangShaderGame"
    project.mkdir()
    _write_json(project / "game.terminproj", {"version": 1, "name": "SlangShaderGame"})
    _write_json(project / "Main.scene", {"scene": {"uuid": "scene-uuid"}})

    calls_path = tmp_path / "shaderc_calls.jsonl"
    compiler = tmp_path / "fake_termin_shaderc.py"
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

    result = build_project(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "SlangShaderGame",
        compile_shaders=True,
        shader_usages=[_FakeSlangShader()],
        shader_compiler=compiler,
    )

    source_root = result.output_dir / ".build" / "shaders" / "source"
    assert (source_root / "slang-shader-phase-uuid.vert.slang").exists()
    assert (source_root / "slang-shader-phase-uuid.frag.slang").exists()
    assert (
        result.output_dir / "assets" / "shaders" / "vulkan" / "slang-shader-phase-uuid.vert.spv"
    ).read_bytes() == b"ARTIFACT-vulkan"
    assert (
        result.output_dir / "assets" / "shaders" / "opengl" / "slang-shader-phase-uuid.frag.glsl"
    ).read_bytes() == b"ARTIFACT-opengl"

    by_type = {}
    for resource in result.manifest.resources:
        by_type.setdefault(resource.type, set()).add(resource.build_path)
    assert by_type["shader_spirv"] == {
        "assets/shaders/vulkan/slang-shader-phase-uuid.vert.spv",
        "assets/shaders/vulkan/slang-shader-phase-uuid.frag.spv",
    }
    assert by_type["shader_glsl"] == {
        "assets/shaders/opengl/slang-shader-phase-uuid.vert.glsl",
        "assets/shaders/opengl/slang-shader-phase-uuid.frag.glsl",
    }

    calls = [
        json.loads(line)
        for line in calls_path.read_text(encoding="utf-8").splitlines()
    ]
    assert all("--language" in call and call[call.index("--language") + 1] == "slang" for call in calls)
    assert {call[call.index("--target") + 1] for call in calls} == {"vulkan", "opengl"}
    assert all("--layout-scheme" not in call for call in calls)


def test_build_project_can_compile_slang_shader_usages_for_d3d11(tmp_path: Path) -> None:
    project = tmp_path / "D3D11ShaderGame"
    project.mkdir()
    _write_json(project / "game.terminproj", {"version": 1, "name": "D3D11ShaderGame"})
    _write_json(project / "Main.scene", {"scene": {"uuid": "scene-uuid"}})

    calls_path = tmp_path / "shaderc_calls.jsonl"
    compiler = tmp_path / "fake_termin_shaderc.py"
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

    result = build_project(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "D3D11ShaderGame",
        compile_shaders=True,
        shader_usages=[_FakeSlangShader()],
        shader_compiler=compiler,
        shader_targets=("vulkan", "opengl", "d3d11"),
    )

    assert (
        result.output_dir / "assets" / "shaders" / "d3d11" / "slang-shader-phase-uuid.vs.cso"
    ).read_bytes() == b"ARTIFACT-d3d11"
    assert (
        result.output_dir / "assets" / "shaders" / "d3d11" / "slang-shader-phase-uuid.ps.cso"
    ).read_bytes() == b"ARTIFACT-d3d11"

    by_type = {}
    for resource in result.manifest.resources:
        by_type.setdefault(resource.type, set()).add(resource.build_path)
    assert by_type["shader_dxbc"] == {
        "assets/shaders/d3d11/slang-shader-phase-uuid.vs.cso",
        "assets/shaders/d3d11/slang-shader-phase-uuid.ps.cso",
    }

    calls = [
        json.loads(line)
        for line in calls_path.read_text(encoding="utf-8").splitlines()
    ]
    assert {call[call.index("--target") + 1] for call in calls} == {
        "vulkan",
        "opengl",
        "d3d11",
    }


def test_build_project_writes_player_window_settings(tmp_path: Path) -> None:
    project = tmp_path / "WindowGame"
    project.mkdir()
    _write_json(project / "window.terminproj", {"version": 1, "name": "WindowGame"})
    _write_json(project / "Main.scene", {"scene": {"uuid": "scene-uuid"}})
    _write_json(
        project / "project_settings" / "project.json",
        {
            "player_window": {
                "width": 1024,
                "height": 768,
                "fullscreen": False,
            },
        },
    )

    result = build_project(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "WindowGame",
        copy_files=False,
    )

    build_data = json.loads(result.build_json_path.read_text(encoding="utf-8"))
    assert build_data["runtime"]["window"] == {
        "width": 1024,
        "height": 768,
        "fullscreen": False,
    }
