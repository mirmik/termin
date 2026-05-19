import json
from pathlib import Path

from termin.project_builder import build_project


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
    assert by_source["stdlib/shaders/StandardShader.shader"]["build_path"] == "stdlib/shaders/StandardShader.shader"

    build_data = json.loads(result.build_json_path.read_text(encoding="utf-8"))
    assert build_data["project_name"] == "SampleGame"
    assert build_data["entry_scene"] == "assets/Scenes/Main.scene"
    assert build_data["asset_manifest"] == "assets/manifest.json"


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
