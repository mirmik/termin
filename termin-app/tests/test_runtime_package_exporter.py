import json
from pathlib import Path

import numpy as np

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
    assert shader_data["uuid"] == shader_uuid
    assert (result.package_dir / "shaders" / "vulkan" / f"{shader_uuid}.vert.spv").read_bytes() == b"SPIRV"
    assert (result.package_dir / "shaders" / "vulkan" / f"{shader_uuid}.frag.spv").read_bytes() == b"SPIRV"
    assert result.diagnostics == []


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
    assert result.application_id == "org.termin.builds.androidgame"
    assert result.launch_activity == "org.termin.android.TerminActivity"
    assert result.package_result.manifest_path.exists()
    log_text = result.log_path.read_text(encoding="utf-8")
    assert "--assets-dir" in log_text
    assert str(result.package_result.package_dir) in log_text
    assert "--application-id" in log_text
    assert "org.termin.builds.androidgame" in log_text
    assert "--app-label" in log_text
    assert "AndroidGame" in log_text
