import json
from pathlib import Path

from termin.project_build import build_android_project, export_runtime_package


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


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
    )

    assert result.manifest_path.exists()
    assert result.scene_path.exists()
    assert (result.package_dir / "meshes" / "mesh-uuid.tmesh.json").exists()
    assert (result.package_dir / "materials" / "material-uuid.tmat.json").exists()
    assert (result.package_dir / "shaders" / "termin-runtime-default-color.shader.json").exists()
    assert (result.package_dir / "shaders" / "vulkan" / "termin-runtime-default-color.vert.spv").exists()
    assert (result.package_dir / "shaders" / "vulkan" / "termin-runtime-default-color.frag.spv").exists()

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
    assert [diagnostic["level"] for diagnostic in manifest["diagnostics"]] == [
        "warning",
        "warning",
    ]


def test_export_runtime_package_accepts_root_scene_json(tmp_path: Path) -> None:
    project = tmp_path / "RootSceneGame"
    project.mkdir()
    scene_path = project / "Main.scene"
    _write_json(scene_path, {"uuid": "root-scene", "entities": []})

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "android" / "RootSceneGame" / "package",
    )

    scene_data = json.loads(result.scene_path.read_text(encoding="utf-8"))
    assert scene_data == {"uuid": "root-scene", "entities": []}


def test_build_android_project_exports_package_and_copies_apk(tmp_path: Path) -> None:
    project = tmp_path / "AndroidGame"
    project.mkdir()
    _write_json(project / "AndroidGame.terminproj", {"version": 1, "name": "AndroidGame"})
    _write_json(project / "Main.scene", {"uuid": "root-scene", "entities": []})

    termin_root = tmp_path / "termin-root"
    apk_source = termin_root / "build" / "android-gradle" / "app" / "outputs" / "apk" / "debug" / "app-debug.apk"
    build_script = termin_root / "build-android-apk.sh"
    build_script.parent.mkdir(parents=True)
    build_script.write_text(
        "#!/bin/sh\n"
        "set -e\n"
        f"mkdir -p '{apk_source.parent}'\n"
        f"printf APK > '{apk_source}'\n"
        "printf '%s\\n' \"$@\"\n",
        encoding="utf-8",
    )
    build_script.chmod(0o755)

    result = build_android_project(
        project_root=project,
        entry_scene="Main.scene",
        termin_root=termin_root,
        build_script=build_script,
        gradle="/tmp/fake-gradle",
    )

    assert result.apk_path == project / "dist" / "android" / "AndroidGame" / "apk" / "AndroidGame-debug.apk"
    assert result.apk_path.read_bytes() == b"APK"
    assert result.package_result.manifest_path.exists()
    log_text = result.log_path.read_text(encoding="utf-8")
    assert "--assets-dir" in log_text
    assert str(result.package_result.package_dir) in log_text
